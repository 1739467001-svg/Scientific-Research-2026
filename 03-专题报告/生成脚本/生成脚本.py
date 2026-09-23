"""《Claude Opus 5.5 与 Opus 5 能力对比》PDF 生成脚本
====================================================
MD 源文件是唯一的内容来源；本脚本负责排版（封面、指标卡、哑铃图、页脚页码）。
修改报告内容时只改 MD，再重新运行本脚本即可。

视觉识别取自中国科学院杭州医学研究所门禁卡：
  所徽藏青 #20396f · 天空蓝 #3685d8 · 红砖楼砖红 #9a3b33（色相保真、饱和度按印刷调校）
  楼体奶油白 #f5f1ea · 草坪绿 #4a6b2a
图表配色已用 dataviz 校验脚本验证（哑铃两端按有序编码全部通过；与砖红参照点全配对
色盲模拟 ΔE 14.5、常规视觉 ΔE 23.8）。

依赖：pip install markdown beautifulsoup4 playwright pypdfium2 pillow
      字体：文泉驿正黑（WenQuanYi Zen Hei）

用法：
  1) 从门禁卡照片生成封面横幅（照片按 .gitignore 规则不入库，需自备）：
       python 生成脚本.py banner <门禁卡照片> <输出横幅.jpg>
  2) 生成 PDF：
       python 生成脚本.py <报告.md> <横幅.jpg> <输出.pdf> <临时目录>

注意：本脚本中的指标卡（KPIS）与哑铃图数据（ROWS）为本报告专用；
      MD 里的数字若有改动，需同步修改这两处。
"""
import sys
if len(sys.argv) >= 2 and sys.argv[1] == "banner":
    from PIL import Image, ImageEnhance
    im = Image.open(sys.argv[2]).convert("RGB")
    crop = im.crop((22, 300, 1432, 872))  # 基于 1490×916 原图：钟楼顶端至大门，避开卡片圆角与右缘
    crop = ImageEnhance.Contrast(ImageEnhance.Color(crop).enhance(1.12)).enhance(1.06)
    crop.save(sys.argv[3], quality=90); print("banner ok:", crop.size); sys.exit(0)

import sys, base64, pathlib, markdown
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pypdfium2 as pdfium

SRC, BANNER, OUT, WORK = sys.argv[1:5]
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FONT = '"WenQuanYi Zen Hei", "Noto Sans CJK SC", sans-serif'

# ── 设计令牌 ──────────────────────────────────────────────
C = dict(navy="#20396f", navy2="#2d4d8e", navyL="#7d97cc", navyT="#c3cfe7",
         sky="#3685d8", brick="#9a3b33", brickT="#f6e9e7",
         cream="#f5f1ea", paper="#fbf9f5", line="#e4ddd1", zebra="#faf7f2",
         green="#4a6b2a", ink="#172033", ink2="#46506a", muted="#6b7280")

# ── 解析 Markdown ────────────────────────────────────────
md = pathlib.Path(SRC).read_text(encoding="utf-8")
soup = BeautifulSoup(markdown.markdown(md, extensions=["tables", "sane_lists"]), "html.parser")

h1 = soup.find("h1"); title_text = h1.get_text(); h1.decompose()
meta_tbl = soup.find("table"); meta = {}
for tr in meta_tbl.find_all("tr")[1:]:
    td = tr.find_all("td"); meta[td[0].get_text()] = td[1].decode_contents()
meta_tbl.decompose()

# ── 一页结论：表格 → 指标卡 + 结论卡 ─────────────────────
KPIS = [
    ("官方基准全部提升", "9 / 9", "每一项都高于 Opus 5", "navy"),
    ("单价降幅", "−20%", "缓存读取 −60%", "navy"),
    ("科研工作流基准", "29.0 → 58.7%", "翻倍；GPT-6 Astra 为 64.6%", "navy"),
    ("课题组可用性", "⚠ 受限", "中国大陆不在支持地区", "brick"),
]
h2_sum = next(h for h in soup.find_all("h2") if "一页结论" in h.get_text())
sum_tbl = h2_sum.find_next_sibling("table")
cards = []
for i, tr in enumerate(sum_tbl.find_all("tr")[1:], 1):
    cell = tr.find_all("td")[1]
    lead = cell.find("strong"); lead_html = lead.decode_contents() if lead else ""
    if lead: lead.decompose()
    tone = "brick" if "⚠" in lead_html or "无法" in lead_html else "navy"
    lead_html = lead_html.replace("⚠️", "").strip()
    cards.append(f'<div class="card {tone}"><div class="num">{i}</div>'
                 f'<div><div class="lead">{lead_html}</div><div class="body">{cell.decode_contents().strip().lstrip("：:，, ")}</div></div></div>')
kpi_html = "".join(f'<div class="kpi {t}"><div class="k-label">{l}</div><div class="k-value">{v}</div><div class="k-foot">{f}</div></div>'
                   for l, v, f, t in KPIS)
sum_tbl.replace_with(BeautifulSoup(f'<div class="kpis">{kpi_html}</div><div class="cards">{"".join(cards)}</div>', "html.parser"))

# ── 哑铃图（内联 SVG）────────────────────────────────────
ROWS = [  # 名称, 说明, Opus5, Opus5.5, GPT-6 Astra(仅标其领先项)
    ("Terminal-Bench-Science", "真实科研计算工作流", 29.0, 58.7, 64.6),
    ("Terminal-Bench 4.0", "终端环境智能体编程", 52.3, 66.4, None),
    ("AutomationBench", "业务流程自动化", 26.9, 40.0, 41.4),
    ("CursorBench 4.0", "真实代码编辑", 46.6, 57.8, None),
    ("OSWorld 2.0", "操作电脑界面（部分得分）", 74.0, 81.8, None),
    ("FrontierCode v1.1", "前沿编程难题", 48.0, 54.4, None),
    ("Chartography", "图表理解（含工具）", 83.4, 89.0, None),
    ("Humanity's Last Exam", "跨学科专家级难题（含工具）", 63.6, 67.7, None),
]
W, LBL, PX0, PW, VCOL, DCOL = 680, 188, 196, 360, 580, 640
TOP, RH = 44, 38
H = TOP + RH * len(ROWS) + 30
x = lambda v: PX0 + PW * v / 100
s = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family=\'{FONT}\'>']
# 图例（≥2 系列必须有图例）
lg = [(C["navyL"], "circle", "Opus 5"), (C["navy"], "circle", "Opus 5.5"), (C["brick"], "diamond", "GPT-6 Astra（仅标出其领先的两项）")]
lx = 0
for col, shape, lab in lg:
    if shape == "circle": s.append(f'<circle cx="{lx+6}" cy="12" r="5.5" fill="{col}"/>')
    else: s.append(f'<rect x="{lx+1.5}" y="7.5" width="9" height="9" fill="{col}" transform="rotate(45 {lx+6} 12)"/>')
    s.append(f'<text x="{lx+16}" y="16" font-size="11" fill="{C["ink2"]}">{lab}</text>')
    lx += 16 + len(lab) * 8.2 + 26
# 列标题
s.append(f'<text x="{VCOL}" y="{TOP-10}" font-size="10" fill="{C["muted"]}" text-anchor="end">Opus 5.5</text>')
s.append(f'<text x="{DCOL}" y="{TOP-10}" font-size="10" fill="{C["muted"]}" text-anchor="end">提升</text>')
# 网格：实线细线，比底色深一档
for t in range(0, 101, 20):
    gx = x(t)
    s.append(f'<line x1="{gx}" y1="{TOP-4}" x2="{gx}" y2="{TOP+RH*len(ROWS)}" stroke="{C["line"]}" stroke-width="1"/>')
    s.append(f'<text x="{gx}" y="{TOP+RH*len(ROWS)+16}" font-size="9.5" fill="{C["muted"]}" text-anchor="middle" style="font-variant-numeric:tabular-nums">{t}%</text>')
for i, (name, desc, a, b, ast) in enumerate(ROWS):
    cy = TOP + RH * i + RH / 2
    if i == 0:  # 强调与课题组最相关的一行
        s.append(f'<rect x="0" y="{cy-RH/2+2}" width="{W}" height="{RH-4}" rx="4" fill="{C["cream"]}"/>')
    emph = f'stroke="{C["ink"]}" stroke-width="0.3"' if i == 0 else ""
    s.append(f'<text x="0" y="{cy-2}" font-size="11" fill="{C["ink"]}" {emph}>{name}</text>')
    s.append(f'<text x="0" y="{cy+11}" font-size="9" fill="{C["muted"]}">{desc}</text>')
    s.append(f'<line x1="{x(a)}" y1="{cy}" x2="{x(b)}" y2="{cy}" stroke="{C["navyT"]}" stroke-width="3.5" stroke-linecap="round"/>')
    s.append(f'<circle cx="{x(a)}" cy="{cy}" r="5.5" fill="{C["navyL"]}" stroke="#fff" stroke-width="2"/>')
    s.append(f'<circle cx="{x(b)}" cy="{cy}" r="6.5" fill="{C["navy"]}" stroke="#fff" stroke-width="2"/>')
    if ast is not None:
        ax = x(ast)
        s.append(f'<rect x="{ax-4.5}" y="{cy-4.5}" width="9" height="9" fill="{C["brick"]}" stroke="#fff" stroke-width="1.5" transform="rotate(45 {ax} {cy})"/>')
        s.append(f'<text x="{ax+9}" y="{cy-8}" font-size="9" fill="{C["ink2"]}">GPT-6 Astra {ast}%</text>')
    s.append(f'<text x="{VCOL}" y="{cy+4}" font-size="11.5" fill="{C["ink"]}" text-anchor="end" style="font-variant-numeric:tabular-nums">{b}%</text>')
    s.append(f'<text x="{DCOL}" y="{cy+4}" font-size="11" fill="{C["navy"]}" text-anchor="end" style="font-variant-numeric:tabular-nums">+{b-a:.1f}</text>')
s.append("</svg>")
chart = ('<figure class="chart"><figcaption><b>图 1</b>　官方基准：Opus 5 → Opus 5.5（百分比类 8 项，按提升幅度排序）</figcaption>'
         + "".join(s) +
         '<div class="fig-note">GDPval-AA 为 Elo 分，与百分比单位不同，未纳入本图（1708 → 1846，+138）。完整数值与口径脚注见下表。</div></figure>')
h2_bm = next(h for h in soup.find_all("h2") if "官方基准对比" in h.get_text())
h2_bm.find_next_sibling("p").insert_after(BeautifulSoup(chart, "html.parser"))

# ── 附录独立成页 ───────────────────────────────────────
for h in soup.find_all("h2"):
    if "附录" in h.get_text(): h["class"] = h.get("class", []) + ["appendix"]

# ── 小表格不跨页（≤ 6 行）─────────────────────────────────
for t in soup.find_all("table"):
    if len(t.find_all("tr")) <= 7: t["class"] = t.get("class", []) + ["keep"]

# ── 提示框分类 ───────────────────────────────────────────
for bq in soup.find_all("blockquote"):
    t = bq.get_text()
    bq["class"] = "warn" if "⚠" in t else ("info" if "ℹ" in t else "note")

# ── 样式 ─────────────────────────────────────────────────
CSS = f"""
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }}
html {{ font-size: 10pt; }}
body {{ font-family: {FONT}; color: {C['ink']}; line-height: 1.7; margin: 0; background: #fff; }}
strong, b {{ color: {C['navy']}; -webkit-text-stroke: .38px {C['navy']}; font-weight: 700; }}
h2 {{ font-size: 15pt; color: {C['navy']}; margin: 22px 0 12px; padding: 0 0 6px 14px; position: relative;
     border-bottom: 1.5px solid {C['line']}; break-after: avoid; -webkit-text-stroke: .45px {C['navy']}; }}
h2::before {{ content: ""; position: absolute; left: 0; top: 3px; bottom: 9px; width: 5px; border-radius: 2px; background: {C['brick']}; }}
h3 {{ font-size: 11.5pt; color: {C['navy2']}; margin: 16px 0 8px; break-after: avoid; -webkit-text-stroke: .3px {C['navy2']}; }}
h3::before {{ content: ""; display: inline-block; width: 7px; height: 7px; background: {C['sky']}; border-radius: 1.5px; margin: 0 8px 1px 0; }}
p {{ margin: 6px 0; }}
hr {{ border: none; height: 0; margin: 10px 0; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin: 8px 0 14px; font-size: 9pt;
        border: 1px solid {C['line']}; border-radius: 6px; overflow: hidden; }}
tr {{ break-inside: avoid; }}
table.keep {{ break-inside: avoid; }}
h2.appendix {{ break-before: page; margin-top: 0; }}
h2 + p, h3 + p {{ break-after: avoid; }}
th {{ background: {C['navy']}; color: #fff; text-align: left; padding: 6px 8px; font-weight: 700; -webkit-text-stroke: .25px #fff; }}
th strong {{ color: #fff; -webkit-text-stroke: .25px #fff; }}
td {{ padding: 6px 8px; border-top: 1px solid {C['line']}; vertical-align: top; }}
tbody tr:nth-child(even) td {{ background: {C['zebra']}; }}
code {{ font-family: "WenQuanYi Zen Hei Mono", monospace; background: #eef1f6; color: {C['navy2']}; padding: 1px 5px; border-radius: 4px; font-size: 8.6pt; }}
ul, ol {{ margin: 6px 0; padding-left: 22px; }} li {{ margin: 3px 0; }}
li::marker {{ color: {C['brick']}; }}
a {{ color: {C['sky']}; text-decoration: none; }}
blockquote {{ margin: 12px 0; padding: 9px 14px; border-radius: 0 6px 6px 0; break-inside: avoid; }}
blockquote p {{ margin: 3px 0; }}
blockquote.note {{ background: {C['cream']}; border-left: 3.5px solid {C['navy']}; }}
blockquote.warn {{ background: {C['brickT']}; border-left: 3.5px solid {C['brick']}; }}
blockquote.info {{ background: #edf4fc; border-left: 3.5px solid {C['sky']}; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 6px 0 14px; }}
.kpi {{ background: #fff; border: 1px solid {C['line']}; border-top: 3.5px solid {C['navy']}; border-radius: 6px; padding: 10px 12px 9px; }}
.kpi.brick {{ border-top-color: {C['brick']}; background: {C['brickT']}; }}
.k-label {{ font-size: 8.8pt; color: {C['muted']}; }}
.k-value {{ font-size: 18pt; line-height: 1.25; margin: 4px 0 3px; color: {C['ink']}; -webkit-text-stroke: .6px {C['ink']}; white-space: nowrap; }}
.kpi.brick .k-value {{ color: {C['brick']}; -webkit-text-stroke: .6px {C['brick']}; }}
.k-foot {{ font-size: 8.4pt; color: {C['ink2']}; line-height: 1.45; }}
.cards {{ display: grid; gap: 8px; margin-bottom: 8px; }}
.card {{ display: grid; grid-template-columns: 30px 1fr; gap: 10px; align-items: start; background: #fff;
        border: 1px solid {C['line']}; border-radius: 6px; padding: 10px 14px 10px 12px; break-inside: avoid; }}
.card .num {{ width: 26px; height: 26px; border-radius: 50%; background: {C['navy']}; color: #fff; font-size: 11pt;
             display: flex; align-items: center; justify-content: center; -webkit-text-stroke: .3px #fff; }}
.card.brick {{ background: {C['brickT']}; border-color: #ead0cc; }}
.card.brick .num {{ background: {C['brick']}; }}
.card .lead {{ font-size: 10.5pt; color: {C['navy']}; -webkit-text-stroke: .42px {C['navy']}; margin-bottom: 2px; }}
.card.brick .lead {{ color: {C['brick']}; -webkit-text-stroke: .42px {C['brick']}; }}
.card .body {{ color: {C['ink2']}; font-size: 9.4pt; line-height: 1.6; }}
figure.chart {{ margin: 10px 0 14px; padding: 12px 14px 10px; background: #fff; border: 1px solid {C['line']}; border-radius: 8px; break-inside: avoid; }}
figcaption {{ font-size: 10pt; color: {C['ink']}; margin-bottom: 8px; }}
figcaption b {{ color: {C['brick']}; -webkit-text-stroke: .35px {C['brick']}; }}
.fig-note {{ font-size: 8.4pt; color: {C['muted']}; margin-top: 4px; }}
"""
body_html = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title_text}</title><style>{CSS}</style></head><body>{soup}</body></html>'

# ── 封面 ─────────────────────────────────────────────────
b64 = base64.b64encode(pathlib.Path(BANNER).read_bytes()).decode()
t1, t2 = "Claude Opus 5.5 与 Opus 5", "能力对比及对课题组的影响评估"
cover = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; margin: 0; }}
@page {{ size: A4; margin: 0; }}
body {{ width: 210mm; height: 297mm; font-family: {FONT}; background: {C['paper']}; position: relative; overflow: hidden; }}
.photo {{ height: 122mm; background: url(data:image/jpeg;base64,{b64}) center 30% / cover no-repeat; position: relative; }}
.photo::after {{ content: ""; position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 55% at 100% 0%, rgba(32,57,111,.45), rgba(32,57,111,0) 70%),
              linear-gradient(180deg, rgba(32,57,111,.30) 0%, rgba(32,57,111,.04) 32%, rgba(32,57,111,0) 45%, rgba(32,57,111,.55) 82%, {C['navy']} 100%); }}
.band {{ background: {C['navy']}; color: #fff; padding: 12mm 20mm 15mm; }}
.kicker {{ font-size: 9.5pt; letter-spacing: .28em; color: #b9cdea; }}
.t1 {{ font-size: 28pt; line-height: 1.25; margin-top: 7mm; -webkit-text-stroke: .9px #fff; }}
.t2 {{ font-size: 18pt; line-height: 1.4; margin-top: 2.5mm; color: #dfe7f5; -webkit-text-stroke: .35px #dfe7f5; }}
.rule {{ width: 34mm; height: 3px; background: {C['brick']}; margin-top: 8mm; border-radius: 2px; }}
.meta {{ padding: 13mm 20mm 0; display: grid; grid-template-columns: 1fr 1fr; gap: 7mm 12mm; }}
.m-l {{ font-size: 8.8pt; color: {C['muted']}; letter-spacing: .08em; }}
.m-v {{ font-size: 10.5pt; color: {C['ink']}; margin-top: 1.5mm; line-height: 1.55; }}
.m-v strong {{ color: {C['navy']}; -webkit-text-stroke: .35px {C['navy']}; }}
.foot {{ position: absolute; left: 20mm; right: 20mm; bottom: 14mm; border-top: 1px solid {C['line']}; padding-top: 4mm;
        display: flex; justify-content: space-between; font-size: 9pt; color: {C['navy']}; }}
.foot span:last-child {{ color: {C['muted']}; }}
.stripe {{ position: absolute; left: 0; right: 0; bottom: 0; height: 5mm; background: {C['brick']}; }}
</style></head><body>
<div class="photo"></div>
<div class="band"><div class="kicker">专题报告 · SPECIAL REPORT</div>
<div class="t1">{t1}</div><div class="t2">{t2}</div><div class="rule"></div></div>
<div class="meta">
  <div><div class="m-l">编制日期 / 信息截止</div><div class="m-v">{meta.get('编制日期 / 信息截止','')}</div></div>
  <div><div class="m-l">OPUS 5.5 发布日期</div><div class="m-v">{meta.get('Opus 5.5 发布日期','')}</div></div>
  <div style="grid-column: 1 / -1"><div class="m-l">数据来源</div><div class="m-v">{meta.get('数据来源','')}</div></div>
</div>
<div class="foot"><span>中国科学院杭州医学研究所 · 课题组内部交流</span><span>仅供内部参考</span></div>
<div class="stripe"></div>
</body></html>"""

w = pathlib.Path(WORK); w.mkdir(parents=True, exist_ok=True)
(w / "body.html").write_text(body_html, encoding="utf-8"); (w / "cover.html").write_text(cover, encoding="utf-8")
FF = "'WenQuanYi Zen Hei', sans-serif"   # 属性内必须用单引号，否则会截断 style
FOOTER = (f'<div style="width:100%;box-sizing:border-box;padding:0 57px;font-family:{FF};font-size:9px;'
          f'color:{C["muted"]};-webkit-print-color-adjust:exact;">'
          f'<div style="border-top:1px solid {C["line"]};padding-top:5px;overflow:hidden;">'
          f'<span style="float:left">Claude Opus 5.5 与 Opus 5 能力对比 · 课题组内部交流</span>'
          f'<span style="float:right">第 <span class="pageNumber"></span> / <span class="totalPages"></span> 页</span></div></div>')
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
    pg = br.new_page()
    pg.goto((w / "cover.html").as_uri()); pg.pdf(path=str(w / "cover.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
    pg.goto((w / "body.html").as_uri())
    pg.pdf(path=str(w / "body.pdf"), format="A4", print_background=True, display_header_footer=True,
           header_template="<div></div>", footer_template=FOOTER,
           margin=dict(top="15mm", bottom="19mm", left="15mm", right="15mm"))
    br.close()
out = pdfium.PdfDocument.new()
for part in ("cover.pdf", "body.pdf"): out.import_pages(pdfium.PdfDocument(str(w / part)))
out.save(OUT)
print("PDF ok:", OUT, "| 页数", len(pdfium.PdfDocument(OUT)))
