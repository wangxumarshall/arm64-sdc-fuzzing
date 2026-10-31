# -*- coding: utf-8 -*-
"""Generate CORE179 硅失效诊断 PPT (16:9) following 提示词 style + 分页提示词 layout."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.oxml.ns import qn

# ---- palette (strict per 提示词) ----
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x11, 0x11, 0x11)
RED   = RGBColor(0xD3, 0x2F, 0x2F)   # 179 / 故障 / panic / 灭活 / 关键异常
YELLOW= RGBColor(0xFB, 0xC0, 0x2D)   # 关键结论 / 阈值 / 金句 / 必须记住的数字
GRAY  = RGBColor(0x66, 0x66, 0x66)
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
GRID  = RGBColor(0xE0, 0xE0, 0xE0)
FONT  = "Microsoft YaHei"

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


# ---------- low-level font helper (sets latin/ea/cs) ----------
def set_run_font(run, size=None, color=None, bold=None, font=FONT):
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    for tag in ('a:latin', 'a:ea', 'a:cs'):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set('typeface', font)


def R(t, c=BLACK, b=False):
    return (t, c, b)


def new_slide():
    return prs.slides.add_slide(BLANK)


def add_text(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ln.get('align', align)
        if ln.get('space_before') is not None:
            p.space_before = Pt(ln['space_before'])
        if ln.get('space_after') is not None:
            p.space_after = Pt(ln['space_after'])
        p.line_spacing = ln.get('line_spacing', 1.06)
        prefix = '•  ' if ln.get('bullet') else ''
        runs = ln.get('runs')
        if runs is None:
            r = p.add_run()
            r.text = prefix + ln.get('text', '')
            set_run_font(r, ln.get('size', 12), ln.get('color', BLACK), ln.get('bold', False))
        else:
            for j, (t, col, bold) in enumerate(runs):
                r = p.add_run()
                r.text = (prefix if j == 0 else '') + t
                set_run_font(r, ln.get('size', 12), col, bold)
    return tb


def add_header(slide, title_runs, label, page):
    add_text(slide, 0.5, 0.30, 11.3, 0.78, [{'runs': title_runs, 'size': 25, 'bold': True}])
    ln = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.12), Inches(12.33), Pt(1.5))
    ln.fill.solid(); ln.fill.fore_color.rgb = GRAY; ln.line.fill.background()
    add_text(slide, 10.6, 0.34, 2.2, 0.42, [{'text': label, 'size': 11, 'color': GRAY, 'align': PP_ALIGN.RIGHT}])
    if page is not None:
        add_text(slide, 12.2, 7.05, 0.9, 0.4, [{'text': str(page), 'size': 11, 'color': GRAY, 'align': PP_ALIGN.RIGHT}])


def add_golden(slide, text, y=6.4):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(y), Inches(12.33), Inches(0.56))
    box.fill.solid(); box.fill.fore_color.rgb = YELLOW; box.line.fill.background()
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.18); tf.margin_top = Inches(0.03); tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = '→ ' + text
    set_run_font(r, 12.5, BLACK, True)
    return box


def bg_white(slide):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE


def add_card(slide, x, y, w, h, title, body, accent=RED):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = WHITE
    box.line.color.rgb = GRAY; box.line.width = Pt(1)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.09), Inches(h))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background()
    add_text(slide, x + 0.22, y + 0.12, w - 0.4, 0.4,
             [{'runs': [(title, BLACK, True)], 'size': 12.5}])
    add_text(slide, x + 0.22, y + 0.55, w - 0.4, h - 0.7,
             [{'runs': [(body, BLACK, False)], 'size': 10.5, 'line_spacing': 1.15}])


def add_table(slide, x, y, w, col_w, rows, header_fill=BLACK, fs=10):
    nr = len(rows); nc = len(rows[0])
    gf = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(0.42 * nr))
    tbl = gf.table
    tot = sum(col_w)
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(w * cw / tot)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(0.42)
        for c, cell in enumerate(row):
            cobj = tbl.cell(r, c)
            cobj.margin_left = Inches(0.07); cobj.margin_right = Inches(0.07)
            cobj.margin_top = Inches(0.02); cobj.margin_bottom = Inches(0.02)
            cobj.vertical_anchor = MSO_ANCHOR.MIDDLE
            if r == 0:
                cobj.fill.solid(); cobj.fill.fore_color.rgb = header_fill
            else:
                cobj.fill.solid(); cobj.fill.fore_color.rgb = WHITE if r % 2 == 1 else LIGHT
            tf = cobj.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
            if isinstance(cell, tuple):
                text, color, bold = cell
            else:
                text, color, bold = cell, (WHITE if r == 0 else BLACK), (r == 0)
            r0 = p.add_run(); r0.text = text
            set_run_font(r0, fs, color, bold or (r == 0))


def add_bar(slide, x, y, w, h, categories, series, legend=False, max_y=None):
    cd = CategoryChartData(); cd.categories = categories
    for s in series:
        cd.add_series(s['name'], s['values'])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(10); ch.legend.font.name = FONT
    plot = ch.plots[0]
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(10); plot.data_labels.font.name = FONT
    plot.data_labels.font.color.rgb = BLACK
    plot.data_labels.number_format = '0'; plot.data_labels.number_format_is_linked = False
    for i, s in enumerate(series):
        ser = plot.series[i]
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = s['color']
    ch.category_axis.tick_labels.font.size = Pt(9); ch.category_axis.tick_labels.font.name = FONT
    ch.value_axis.tick_labels.font.size = Pt(8); ch.value_axis.tick_labels.font.name = FONT
    if max_y:
        ch.value_axis.maximum_scale = max_y
    try:
        ch.fill.background()
        ch.plot_area.fill.solid(); ch.plot_area.fill.fore_color.rgb = WHITE
    except AttributeError:
        pass
    return gf


def add_pie(slide, x, y, w, h, categories, values, colors):
    cd = CategoryChartData(); cd.categories = categories; cd.add_series('op', values)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.RIGHT
    ch.legend.font.size = Pt(11); ch.legend.font.name = FONT
    plot = ch.plots[0]
    plot.has_data_labels = True
    plot.data_labels.number_format = '0"%"'
    plot.data_labels.number_format_is_linked = False
    plot.data_labels.show_value = True; plot.data_labels.show_percentage = False
    plot.data_labels.font.size = Pt(11); plot.data_labels.font.name = FONT
    plot.data_labels.font.color.rgb = BLACK
    pts = plot.series[0].points
    for i, c in enumerate(colors):
        pts[i].format.fill.solid(); pts[i].format.fill.fore_color.rgb = c
    try:
        ch.fill.background()
    except AttributeError:
        pass
    return gf


def add_code(slide, x, y, w, h, lines, emph=None):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = GRID; box.line.width = Pt(0.75)
    tb = slide.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.08), Inches(w - 0.3), Inches(h - 0.16))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(2)
        if emph and ln in emph:
            r = p.add_run(); r.text = ln; set_run_font(r, 11.5, RED, True, "Consolas")
        else:
            r = p.add_run(); r.text = ln; set_run_font(r, 11.5, BLACK, False, "Consolas")
    return tb


# =====================================================================
# SLIDE 1 — Cover
# =====================================================================
s = new_slide(); bg_white(s)
add_text(s, 0.8, 2.1, 11.7, 1.6, [
    {'runs': [("CORE", BLACK, True), ("179", RED, True), (" 硅失效诊断", BLACK, True)], 'size': 40}])
ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.85), Inches(3.5), Inches(4.0), Pt(2.5))
ln.fill.solid(); ln.fill.fore_color.rgb = YELLOW; ln.line.fill.background()
add_text(s, 0.85, 3.75, 11.5, 0.7, [{'runs': [("从触发配方到关机根因", BLACK, False)], 'size': 22}])
add_text(s, 0.85, 4.7, 11.5, 1.0, [
    {'runs': [("日期：", GRAY, False), ("2026-09-17", BLACK, False)], 'size': 14, 'space_after': 6},
    {'runs': [("平台：", GRAY, False),
              ("Kunpeng 920 / ARMv8.1-A / openEuler / OpenDCDiag", BLACK, False)], 'size': 14}])
add_golden(s, "单核 179 静默数据损坏，最终导致内核 panic 与关机。", y=6.2)

# =====================================================================
# SLIDE 2 — TOC
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("目录", BLACK, True)], "目录", 2)
toc = [
    ("1", "背景与问题定义"),
    ("2", "早期假说"),
    ("3", "三层否定"),
    ("4", "触发配方"),
    ("5", "梯度实验"),
    ("6", "转发研究与错误签名"),
    ("7", "关机根因"),
    ("8", "处置建议与总结"),
]
lines = []
for num, txt in toc:
    col = YELLOW if num == "7" else BLACK
    lines.append({'runs': [(num + "  ", BLACK, True), (txt, col, num == "7")], 'size': 17, 'space_after': 9})
add_text(s, 1.2, 1.6, 11.0, 5.0, lines)

# =====================================================================
# SLIDE 3 — 背景与对象
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("背景与对象", BLACK, True)], "背景", 3)
add_text(s, 0.5, 1.45, 6.6, 4.8, [
    {'runs': [("平台：", BLACK, True), ("Kunpeng 920，192 逻辑核，openEuler。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("工具：", BLACK, True), ("OpenDCDiag ARM64 移植版。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("问题：", BLACK, True), ("逻辑核 ", BLACK, False), ("179", RED, True), (" 存在 SDC 静默数据损坏。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("表现：", BLACK, True), ("load 低概率返回错误数据，无 MCE、无 RAS 报错，OS 无感知。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("判定：", BLACK, True), ("热循环 golden 比对，错误即 miscompare。", BLACK, False)], 'size': 13, 'space_after': 9},
])
# 192-core grid
cols, rows = 16, 12
cell, gap = 0.42, 0.09
gw = cols * (cell + gap)
gx = 0.5 + 6.9 + (5.8 - gw) / 2
gy = 1.7
for idx in range(cols * rows):
    rr = idx // cols; cc = idx % cols
    x = gx + cc * (cell + gap); y = gy + rr * (cell + gap)
    shp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(cell), Inches(cell))
    if idx == 179:
        shp.fill.solid(); shp.fill.fore_color.rgb = RED
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = GRID
    shp.line.fill.background()
add_text(s, gx - 0.1, gy + rows * (cell + gap) + 0.05, 6.0, 0.3,
         [{'runs': [("192 逻辑核（0–191），", GRAY, False), ("核 179", RED, True), (" 高亮。", GRAY, False)], 'size': 10}])
add_golden(s, "这不是普通软件 bug，是绑定硅的硬件缺陷。")

# =====================================================================
# SLIDE 4 — 事实基线
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("事实基线", BLACK, True)], "事实基线", 4)
add_text(s, 0.5, 1.45, 6.5, 4.6, [
    {'runs': [("数千失败样本中，错误 ", BLACK, False), ("100% 落在核 179", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 8},
    {'runs': [("其余 ", BLACK, False), ("191 核零错误", BLACK, True), ("。", BLACK, False)], 'size': 13, 'space_after': 8},
    {'runs': [("排除 179 后，长时间满载零失败。", BLACK, False)], 'size': 13, 'space_after': 8},
    {'runs': [("179 错误不限于用户态：内核态访存同样出错。", BLACK, False)], 'size': 13, 'space_after': 8},
    {'runs': [("衍生两类严重显形：可恢复内核 ", BLACK, False), ("WARN", BLACK, True), ("、致命 ", BLACK, False), ("kernel panic", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 8},
])
add_bar(s, 7.2, 1.6, 5.5, 3.4, ["核 179", "其他 191 核"],
        [{'name': '', 'values': [100, 0], 'color': RED}], max_y=110)
add_text(s, 7.2, 5.05, 5.5, 0.4, [{'runs': [("失败样本占比（%）", GRAY, False)], 'size': 10, 'align': PP_ALIGN.CENTER}])
add_golden(s, "故障绑定该核的硅，属硬件缺陷。")

# =====================================================================
# SLIDE 5 — 早期主假说
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("早期主假说：", BLACK, True), ("str+ldr 是充分条件？", BLACK, True)], "早期假说", 5)
add_text(s, 0.5, 1.45, 7.1, 4.6, [
    {'runs': [("早期唯二触发测试：", BLACK, False), ("movbe 57 次/30min", BLACK, True), ("，", BLACK, False), ("mrn_rmw 6 次/30min", BLACK, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("两者都含同址 ", BLACK, False), ("str → ldr", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("假说：", BLACK, True), ("store→load 转发窗口是根因。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("数据从 store buffer 直接转发给 load，不过缓存阵列。", BLACK, False)], 'size': 13, 'space_after': 9},
])
add_code(s, 7.9, 1.7, 4.9, 1.5, ["str [x0]      ; 写入", "ldr [x0]      ; 同址读回", "              ; 背靠背"], emph=["ldr [x0]      ; 同址读回"])
add_text(s, 7.9, 3.35, 4.9, 0.4, [{'runs': [("同址背靠背 str→ldr", RED, True)], 'size': 11}])
add_golden(s, "早期主假说把根因指向 store→load 转发窗口。")

# =====================================================================
# SLIDE 6 — 第一层否定
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第一层否定：", BLACK, True), ("转发微操作同构，却不触发", BLACK, True)], "三层否定·一", 6)
add_table(s, 0.5, 1.5, 12.33, [3.0, 6.0, 1.5], [
    ["测试", "store→load 微操作（反汇编实录）", "触发？"],
    ["mrn_rmw", "add; str [x0]; ldr [x0] —— 同址同寄存器，背靠背", R("触发", RED, True)],
    ["mrn_nuke", "add; str [x0]; ldr [x0] —— 逐指令相同", "0 失败"],
    ["mem_disambiguation", "add; str [x6]; ldr [x6] —— 逐指令相同", "0 失败"],
    ["mrn_reloaded", "strb; ldrb 同址背靠背（sub-word 转发）", "0 失败"],
    ["part_store_fwd_jit", "JIT 生成 str; ldr 背靠背", "0 失败"],
], fs=10.5)
add_golden(s, "转发微操作原样存在，仍零失败 —— 转发本身不充分。")

# =====================================================================
# SLIDE 7 — 第二层否定
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第二层否定：", BLACK, True), ("时序拉开即归零", BLACK, True)], "三层否定·二", 7)
add_table(s, 0.5, 1.45, 8.2, [2.0, 4.2, 2.0], [
    ["变体", "内容", "36min 失败数"],
    ["紧时序版", "2 源 load + 轮换 ALU + 同址 str→ldr 背靠背", R("46", RED, True)],
    ["松时序版", "同上，但 store/load 间隔拉开 7 条指令", R("0", YELLOW, True)],
], fs=10)
add_bar(s, 9.0, 1.5, 3.8, 3.3, ["紧时序", "松时序"],
        [{'name': '', 'values': [46, 0], 'color': RED}], max_y=55)
add_text(s, 0.5, 4.05, 8.2, 2.2, [
    {'runs': [("松时序版拥有完整“2 源 + ALU + 同址背靠背 str→ldr”，只因间隔拉开就归零。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("1 源但紧时序的骨架也归零。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("触发需要 ", BLACK, False), ("≥2 源 load + ALU 依赖链 + 紧时序", RED, True), ("，缺一不可。", BLACK, False)], 'size': 12.5, 'space_after': 8},
])
add_golden(s, "触发需要 ≥2 源 load + ALU 依赖链 + 紧时序，缺一不可。")

# =====================================================================
# SLIDE 8 — 第三层否定
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第三层否定：", BLACK, True), ("reload 存在性 vs 必要性", BLACK, True)], "三层否定·三", 8)
add_table(s, 0.5, 1.45, 12.33, [1.8, 7.5, 2.0], [
    ["变体", "热循环数据流", "30min 失败数"],
    ["baseline", "ALU → str temp → 同址 ldr temp → str dst", "26~33"],
    ["store_only", "ALU → str temp → str dst（无 ldr 重读）", "14"],
    ["fwd_probe", "ALU → str temp → 异址 ldr dst → str dst", R("0", YELLOW, True)],
], fs=10.5)
add_text(s, 0.5, 4.2, 12.3, 2.0, [
    {'runs': [("store_only 的 14 次失败证明 ", BLACK, False), ("存在性命题", BLACK, True), ("：存在不含热循环重读的触发配置。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("fwd_probe 的 0 是复合变量结果（重读值被丢弃、依赖链断裂），归为“功能等价改写即灭活”的存在性证据。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("26/14/0 作为现象记录保留，", BLACK, False), ("机制归因悬置", BLACK, True), ("（无一对是单变量）。", BLACK, False)], 'size': 12.5, 'space_after': 7},
])
add_golden(s, "str+ldr 只是必要条件侧写的一部分。")

# =====================================================================
# SLIDE 9 — 触发配方五步收敛（时间线）
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("触发配方五步收敛", BLACK, True)], "触发配方", 9)
tl = [
    ("09-01~02", "三要素配方", BLACK),
    ("09-03", "搬进 NEON", BLACK),
    ("09-03/04", "lane 形状判定", BLACK),
    ("09-04", "3 ldr 骨架诞生", RED),
    ("09-05~13", "稳定检测器（7 用例）", YELLOW),
]
y_line = 3.9
x0, x1 = 1.1, 12.2
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x0), Inches(y_line - 0.01), Inches(x1 - x0), Pt(2))
line.fill.solid(); line.fill.fore_color.rgb = GRAY; line.line.fill.background()
n = len(tl)
for i, (d, t, col) in enumerate(tl):
    x = x0 + i * (x1 - x0) / (n - 1)
    circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - 0.13), Inches(y_line - 0.13), Inches(0.26), Inches(0.26))
    circ.fill.solid(); circ.fill.fore_color.rgb = col; circ.line.color.rgb = WHITE; circ.line.width = Pt(1.5)
    add_text(s, x - 1.1, y_line - 1.15, 2.2, 0.5, [{'runs': [(d, GRAY, False)], 'size': 11, 'align': PP_ALIGN.CENTER}])
    add_text(s, x - 1.1, y_line + 0.25, 2.2, 0.9, [{'runs': [(t, col, True)], 'size': 11.5, 'align': PP_ALIGN.CENTER, 'line_spacing': 1.0}])
add_text(s, 0.5, 5.4, 12.3, 1.0, [
    {'runs': [("配方非一次性设计，而是 ", BLACK, False), ("五步实验收敛", BLACK, True), (" 的产物：三要素 → NEON 验证 → lane 阈值 → 位置拆分 → 稳定检测器。", BLACK, False)], 'size': 13}])
add_golden(s, "3ldr + 轮换 ALU + 2str 骨架，五步收敛，固化 7 个有效用例。")

# =====================================================================
# SLIDE 10 — 第一步 三要素配方
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第一步：", BLACK, True), ("三要素配方", BLACK, True)], "第一步", 10)
add_text(s, 0.5, 1.45, 7.0, 4.4, [
    {'runs': [("① ", BLACK, True), ("≥2 源 load + 数据 ALU 依赖链", BLACK, True), ("（store 值为两源经 ALU 加工，非原值搬运）。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("② ", BLACK, True), ("ALU 轮换/混合", BLACK, True), ("：", BLACK, False)], 'size': 13, 'space_after': 3},
    {'runs': [("固定单条 ALU（add/sub/eor/and 各 36min）全部 0 失败；轮换版触发。", BLACK, False)], 'size': 12.5, 'space_after': 3, 'bullet': True},
    {'runs': [("起作用的是 ", BLACK, False), ("“轮换模式”", RED, True), ("，不是特定指令。", BLACK, False)], 'size': 12.5, 'space_after': 9, 'bullet': True},
    {'runs': [("③ ", BLACK, True), ("紧时序", BLACK, True), ("：关键访存指令背靠背，间隔 ≤2 拍。", BLACK, False)], 'size': 13, 'space_after': 9},
])
add_table(s, 7.7, 1.6, 5.1, [3.0, 2.1], [
    ["ALU 模式", "30min 失败数"],
    ["固定单条 (add/sub/eor/and)", R("0", YELLOW, True)],
    ["轮换 / 混合", R("触发", RED, True)],
], fs=10.5)
add_golden(s, "起作用的是“轮换模式”，不是特定指令。")

# =====================================================================
# SLIDE 11 — 第二步 NEON
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第二步：", BLACK, True), ("配方搬进 NEON", BLACK, True)], "第二步", 11)
add_text(s, 0.5, 1.45, 7.2, 4.2, [
    {'runs': [("选 ", BLACK, False), ("uint64x2_t", BLACK, True), ("，2×64b lane，每条 lane 语义与标量版同构。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("唯一变量：执行通路从标量 ALU 换到 NEON 单元。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("结果：", BLACK, True), ("33 次失败/30min", BLACK, True), ("，约 1.1 次/min，全部核 ", BLACK, False), ("179", RED, True), ("，首触发仅 ", BLACK, False), ("11.6 秒", YELLOW, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("是标量同构版的 1.7 倍，成为触发率最高的受控检测器。", BLACK, False)], 'size': 13, 'space_after': 9},
])
box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.9), Inches(1.7), Inches(4.9), Inches(2.3))
box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = RED; box.line.width = Pt(1.25)
add_text(s, 8.1, 1.85, 4.5, 2.0, [
    {'runs': [("工程红线", RED, True)], 'size': 13, 'space_after': 6},
    {'runs': [("NEON 的重读必须用内联汇编写 ", BLACK, False)], 'size': 11.5, 'space_after': 2},
    {'runs': [("asm volatile ldr", BLACK, True)], 'size': 11.5, 'space_after': 4},
    {'runs': [("否则编译器 intrinsic 会被直接消除，", BLACK, False)], 'size': 11.5, 'space_after': 2},
    {'runs': [("load 根本不发出。", BLACK, False)], 'size': 11.5}])
add_golden(s, "NEON 重读须用 asm volatile，否则被编译器消除。")

# =====================================================================
# SLIDE 12 — 第三步 lane 形状
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第三步：", BLACK, True), ("lane 形状判定", BLACK, True)], "第三步", 12)
add_table(s, 0.5, 1.5, 6.0, [3.0, 3.0], [
    ["lane 形状", "30min 失败数"],
    ["2×64b", "26~33"],
    ["4×32b", R("0", YELLOW, True)],
    ["16×8b", "2"],
], fs=11)
add_text(s, 0.5, 3.2, 6.0, 3.0, [
    {'runs': [("同宽度（16B）不同 lane 组织对照。", GRAY, False)], 'size': 11.5}])
add_text(s, 7.0, 1.6, 5.8, 4.0, [
    {'runs': [("触发绑定 ", BLACK, False), ("64-bit lane 数据通路本身", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("是 ", BLACK, False), ("阈值不是梯度", YELLOW, True), ("：4×32b 塌得比 16×8b 更彻底。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("排除“数据量计费”和“越宽越触发”两种解释。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("≥2 源阈值跨通路成立：", BLACK, False), ("NEON 1 源 = 0", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
])
add_golden(s, "≥2 源阈值跨通路成立，NEON 1 源 = 0。")

# =====================================================================
# SLIDE 13 — 第四步 3 ldr 骨架
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第四步：", BLACK, True), ("3 ldr 骨架诞生", BLACK, True)], "第四步", 13)
add_code(s, 0.5, 1.5, 5.6, 2.6, [
    "ldr  scratch[i]     ; 第3条 ldr 挪到迭代顶部",
    "a = srcA[i]",
    "b = srcB[i]",
    "res = 轮换 ALU(a, b)",
    "str temp[i]",
    "str dst[i]",
])
add_text(s, 0.5, 4.3, 5.6, 2.0, [
    {'runs': [("与 fwd_probe 同指令条数、同访存混合度：", BLACK, False), ("3 ldr + 2 str", BLACK, True), ("。", BLACK, False)], 'size': 11.5, 'space_after': 6},
    {'runs': [("唯一差异：第三条 ldr 的位置。", BLACK, False)], 'size': 11.5, 'space_after': 6},
])
add_text(s, 6.4, 1.6, 6.4, 4.0, [
    {'runs': [("顶部第 3 条 ldr 的结果 ", BLACK, False), ("架构上死亡", RED, True), ("（不被消费）。", BLACK, False)], 'size': 13, 'space_after': 10},
    {'runs': [("从设计起就是 ", BLACK, False), ("load 端口占用 / 调度压力探针", BLACK, True), ("。", BLACK, False)], 'size': 13, 'space_after': 10},
    {'runs': [("位置对照：与 fwd_probe 唯一差异是第三条 ldr 在迭代顶部 vs 两 str 之间。", BLACK, False)], 'size': 12.5, 'space_after': 10},
])
add_golden(s, "这就是 3ldr + 轮换 ALU + 2str 骨架的出处。")

# =====================================================================
# SLIDE 14 — 第五步 稳定检测器
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("第五步：", BLACK, True), ("稳定检测器", BLACK, True)], "第五步", 14)
add_text(s, 0.5, 1.5, 12.3, 4.0, [
    {'runs': [("三变体 × 3 轮 30min 复测。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("rowmajor 变体 3 轮共 ", BLACK, False), ("669 次失败", BLACK, True), ("（223/轮）。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("1019/1019 ", BLACK, False), ("全部核 179", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("失败在时间窗内均匀分布、跨 seed 独立 —— 可复现的受控检测器。", BLACK, False)], 'size': 13, 'space_after': 9},
    {'runs': [("附带发现：加 dump（落盘）冷分支使触发率塌缩 ", BLACK, False), ("30 倍", YELLOW, True), ("。", BLACK, False)], 'size': 13, 'space_after': 9},
])
add_golden(s, "检测与取证必须分离设计（任何对热循环的改动都可能灭活）。")

# =====================================================================
# SLIDE 15 — 骨架固化 7 用例
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("骨架固化：", BLACK, True), ("7 个有效 SDC 用例", BLACK, True)], "骨架固化", 15)
add_code(s, 0.5, 1.5, 6.0, 1.1, [
    "3×ldr q → i%4 分派 → 轮换 vALU → 2×str q → 降序回跳",
])
add_text(s, 0.5, 2.8, 6.1, 3.6, [
    {'runs': [("转发边：", BLACK, True)], 'size': 12.5, 'space_after': 5},
    {'runs': [("① 顶部死 load：无转发边，占端口。", BLACK, False)], 'size': 11.5, 'space_after': 4, 'bullet': True},
    {'runs': [("② ③ → ④：load-to-use 0 拍旁路。", BLACK, False)], 'size': 11.5, 'space_after': 4, 'bullet': True},
    {'runs': [("④ → ⑤：ALU→store 0 拍旁路。", BLACK, False)], 'size': 11.5, 'space_after': 8, 'bullet': True},
    {'runs': [("六格差异只落三个正交平面：", BLACK, True)], 'size': 12.5, 'space_after': 5},
    {'runs': [("地址平面：k5far / k5inter_rand", BLACK, False)], 'size': 11.5, 'space_after': 4, 'bullet': True},
    {'runs': [("数据平面：k7p ×3", BLACK, False)], 'size': 11.5, 'space_after': 4, 'bullet': True},
    {'runs': [("容量平面：k3res", BLACK, False)], 'size': 11.5, 'bullet': True},
])
add_text(s, 6.9, 1.6, 5.9, 4.2, [
    {'runs': [("热循环指令构成 7 用例完全一致，依赖边全为 0 拍旁路边。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("失败 ", BLACK, False), ("100% 落在核 179", RED, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("变体间热循环须逐指令同构，才是 ", BLACK, False), ("单变量", YELLOW, True), (" 实验。", BLACK, False)], 'size': 12.5, 'space_after': 9},
])
add_golden(s, "三正交平面（地址/数据/容量）限定差异，单变量对照。")

# =====================================================================
# SLIDE 16 — 多 ldr 梯度
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("多 ldr 梯度：", BLACK, True), ("2 源是阈值", BLACK, True)], "梯度实验", 16)
add_bar(s, 7.3, 1.6, 5.4, 3.6, ["1 源", "2 源", "3 源", "4 源"],
        [{'name': '', 'values': [0, 14, 10, 4], 'color': RED}], max_y=16)
add_text(s, 7.3, 5.25, 5.4, 0.4, [{'runs': [("失败数（次/36min）", GRAY, False)], 'size': 10, 'align': PP_ALIGN.CENTER}])
add_text(s, 0.5, 1.6, 6.6, 4.0, [
    {'runs': [("mrn_nuke 骨架，只变源 load 数，其余逐字节不动。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("1 源 = 0；", BLACK, False), ("2 源最高（14）", RED, True), ("；3 源 10；4 源 4。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("非单调：", BLACK, True), ("2 源最高，3/4 源反而下降。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("更多源拉长依赖链、增加指令数，反而扰动紧时序窗口。", BLACK, False)], 'size': 12.5, 'space_after': 9},
])
add_golden(s, "“≥2 源”是阈值条件，不是越多越好。")

# =====================================================================
# SLIDE 17 — 多 store / 去 reload
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("多 store / 去 reload：", BLACK, True), ("转发非必要", BLACK, True)], "多 store", 17)
add_table(s, 0.5, 1.5, 12.33, [1.7, 7.6, 1.6], [
    ["变体", "每元素指令流", "失败数"],
    ["2src", "2 源 + 轮换 + str/reload/str（3 ldr + 2 str）", R("19", RED, True)],
    ["1src", "1 源 + 同轮换 + str/reload/str", R("0", YELLOW, True)],
    ["store_only", "2 源 + 轮换 + 2×str 无 reload（2 ldr + 2 str）", "1"],
    ["unaligned", "2src + 16B 槽内旋转偏移（7/8 非对齐）", R("0", YELLOW, True)],
], fs=10.5)
add_text(s, 0.5, 4.4, 12.3, 1.8, [
    {'runs': [("NEON 侧：双 str 无 reload = ", BLACK, False), ("14 次失败/30min", RED, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("去掉所有 reload 仍能触发 → 转发窗口", BLACK, False), ("不是严格必要条件", RED, True), ("，而是约 20 倍强放大器。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("轮换指令集可替换（add/sub/eor/and → add/eor/and/orr 仍触发）；非对齐 0 失败 → 布局效应。", BLACK, False)], 'size': 12.5, 'space_after': 7},
])
add_golden(s, "store 必要，store→load 转发不必要。")

# =====================================================================
# SLIDE 18 — 零 store 反证
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("零 store 反证：", BLACK, True), ("store 在场必要", BLACK, True)], "零 store", 18)
add_bar(s, 7.3, 1.7, 5.4, 3.4, ["基线 3ldr+2str", "k2pureload 3ldr+0str"],
        [{'name': '', 'values': [58, 0], 'color': RED}], max_y=65)
add_text(s, 7.3, 5.15, 5.4, 0.4, [{'runs': [("失败数（次/30min）", GRAY, False)], 'size': 10, 'align': PP_ALIGN.CENTER}])
add_text(s, 0.5, 1.7, 6.6, 4.0, [
    {'runs': [("k2pureload：保留 2 源 load + 轮换 ALU + 顶部死 ldr，", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("删掉全部 store，结果用 xor 累加器冷路径校验。", BLACK, False)], 'size': 12.5, 'space_after': 10},
    {'runs': [("基线 3ldr+2str = ", BLACK, False), ("58", RED, True), ("；k2pureload 3ldr+0str = ", BLACK, False), ("0", YELLOW, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 10},
    {'runs': [("结论：", BLACK, True), ("store 在场是必要条件", RED, True), ("；但不需要 store 被转发回 load。", BLACK, False)], 'size': 12.5, 'space_after': 10},
])
add_golden(s, "store 必要，store→load 转发不必要。")

# =====================================================================
# SLIDE 19 — 时序间距反证
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("时序间距反证：", BLACK, True), ("全链紧邻，缺一不可", BLACK, True)], "时序间距", 19)
add_bar(s, 7.3, 1.7, 5.4, 3.4, ["基线", "k4gap", "k4bgap"],
        [{'name': '', 'values': [58, 0, 0], 'color': RED}], max_y=65)
add_text(s, 7.3, 5.15, 5.4, 0.4, [{'runs': [("失败数（次/30min）", GRAY, False)], 'size': 10, 'align': PP_ALIGN.CENTER}])
add_text(s, 0.5, 1.7, 6.6, 4.0, [
    {'runs': [("基线：load→ALU→str 零间隔 = ", BLACK, False), ("58", RED, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("k4gap：load→ALU 之间插 ", BLACK, False), ("8 条 nop", BLACK, True), (" = 0。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("k4bgap：ALU→str 之间插 8 条 nop = 0。", BLACK, False)], 'size': 12.5, 'space_after': 10},
    {'runs': [("结论：", BLACK, True), ("每一环都必须紧邻", RED, True), (" —— load 到消费、计算到 store，任何一端拉开都灭活。", BLACK, False)], 'size': 12.5, 'space_after': 10},
])
add_golden(s, "load 到消费、计算到 store，任何一端拉开都灭活。")

# =====================================================================
# SLIDE 20 — 复现性与率波动
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("复现性与率波动", BLACK, True)], "复现性", 20)
cats = ["基线 rowmajor", "k5far", "k5inter_rand", "k7p_rand", "k7p_one", "k7p_hiham", "k3res", "合计"]
first =  [58, 37, 72, 78, 42, 44, 58, 389]
second = [18, 16, 50, 34, 8, 9, 41, 176]
add_bar(s, 0.5, 1.5, 12.33, 3.7, cats,
        [{'name': '首晚 原序', 'values': first, 'color': RED},
         {'name': '复跑 逆序', 'values': second, 'color': YELLOW}],
        legend=True, max_y=90)
add_text(s, 0.5, 5.3, 12.3, 1.3, [
    {'runs': [("7/7 全部复现，失败仍全在 ", BLACK, False), ("核 179", RED, True), ("；相对排序两晚一致。", BLACK, False)], 'size': 12, 'space_after': 5},
    {'runs': [("绝对率整体塌缩到 45%（系统性为真，成因归于机器状态时间尺度波动，未定论）。", BLACK, False)], 'size': 12, 'space_after': 5},
])
add_golden(s, "比较触发率须同时段配对，同晚内排序才有效。")

# =====================================================================
# SLIDE 21 — 转发视角 0 拍
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("转发视角：", BLACK, True), ("所有活依赖边必须 0 拍", BLACK, True)], "转发视角", 21)
add_table(s, 0.5, 1.5, 12.33, [3.2, 9.1], [
    ["依赖边", "转发含义"],
    ["源 ldr → vALU", "load-to-use 0 拍旁路（不旁路即 stall）"],
    ["vALU → str ×2", "ALU→store 0 拍旁路（结果不过寄存器堆直达 store）"],
    ["顶部第 3 条 ldr", "无转发边，纯 load 端口占用"],
    ["i%4 轮换 ALU", "每元素换一条旁路路由（加法器入口 ↔ 逻辑入口）"],
    ["升/降交替扫描", "循环接缝处 str→ldr 邻接关系翻转"],
], fs=11)
add_text(s, 0.5, 5.5, 12.3, 1.0, [
    {'runs': [("精确表述：热循环内 ", BLACK, False), ("没有任何一条活依赖边走寄存器堆往返", RED, True), ("；三条 load 中仅两条形成转发边，第三条故意做成死的。", BLACK, False)], 'size': 12.5}])
add_golden(s, "所有活依赖边必须 0 拍 —— 转发是配方边界的坐标系。")

# =====================================================================
# SLIDE 22 — 数据内容门控
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("数据内容门控", BLACK, True)], "数据门控", 22)
add_bar(s, 7.3, 1.6, 5.4, 3.6, ["全 0", "全 1", "GPS 随机", "0x55/0xAA"],
        [{'name': '', 'values': [0, 42, 78, 44], 'color': RED}], max_y=90)
add_text(s, 7.3, 5.25, 5.4, 0.4, [{'runs': [("失败数（次/30min）", GRAY, False)], 'size': 10, 'align': PP_ALIGN.CENTER}])
add_text(s, 0.5, 1.6, 6.6, 4.0, [
    {'runs': [("同一指令序列，只换填充数据。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("全 0 = ", BLACK, False), ("0（灭活）", YELLOW, True), ("；全 1 = 42；GPS 随机 = ", BLACK, False), ("78（最强）", RED, True), ("；高汉明 = 44。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("数据多样性是必要条件；随机数据最强。", BLACK, False)], 'size': 12.5, 'space_after': 9},
    {'runs': [("损伤不是均匀位翻转，而是 ", BLACK, False), ("模式敏感", RED, True), (" 的。", BLACK, False)], 'size': 12.5, 'space_after': 9},
])
add_golden(s, "全 0 灭活，随机数据最强 —— 损伤是模式敏感的。")

# =====================================================================
# SLIDE 23 — 错误签名
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("错误签名：", BLACK, True), ("指向地址捕获/数据装配级", BLACK, True)], "错误签名", 23)
add_pie(s, 8.3, 1.5, 4.6, 4.0, ["orr", "and", "eor", "add"], [71, 23, 0, 1],
        [RED, YELLOW, GRAY, RGBColor(0x9E, 0x9E, 0x9E)])
add_text(s, 0.5, 1.5, 7.6, 4.6, [
    {'runs': [("① ", BLACK, True), ("eor 零例", RED, True), ("：got = expected ± X·(2^32 - 2^16) 100% 符合；", BLACK, False)], 'size': 12, 'space_after': 6},
    {'runs': [("    op 偏置 orr 71% / and 23% / ", BLACK, False), ("eor 0%", RED, True), (" / add 1%。", BLACK, False)], 'size': 12, 'space_after': 8},
    {'runs': [("② ", BLACK, True), ("替换源 = 地址近邻", BLACK, True), ("：交错布局下 79/79 命中错位窗 —— “拿错数据”非“数据被改坏”。", BLACK, False)], 'size': 12, 'space_after': 8},
    {'runs': [("③ ", BLACK, True), ("mod-8 错位窗", BLACK, True), ("：8 字节粒度窗口搬移，与内核态崩溃错误地址同构。", BLACK, False)], 'size': 12, 'space_after': 8},
    {'runs': [("④ ", BLACK, True), ("运算偏置与进位链形状", BLACK, True), ("：指向装配/选择电路（含进位链），非数据通路。", BLACK, False)], 'size': 12, 'space_after': 8},
])
add_golden(s, "损伤是“拿错了数据”，不是“数据在通路上被翻位”。")

# =====================================================================
# SLIDE 24 — 方法论边界
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("方法论边界", BLACK, True)], "方法论", 24)
add_text(s, 0.5, 1.5, 12.3, 4.4, [
    {'runs': [("干预解耦不可能", RED, True), ("：插 nop 同时改变“是否走旁路路径”与“时序余量”两件事。", BLACK, False)], 'size': 13, 'space_after': 10},
    {'runs': [("零格只证明“所有活边必须 0 拍”，", BLACK, False), ("不能证明“缺陷骑在旁路通路上”", RED, True), ("。", BLACK, False)], 'size': 13, 'space_after': 10},
    {'runs': [("转发不充分（§1），转发亦非故障位点（§4.3）—— 它只是必要条件的侧写。", BLACK, False)], 'size': 13, 'space_after': 10},
    {'runs': [("布局敏感是全局现象", YELLOW, True), ("：改寻址、改时序、增删指令、加 dump 分支都可能灭活。", BLACK, False)], 'size': 13, 'space_after': 10},
    {'runs': [("任何单变量结论必须以反汇编逐指令核对的同构性为前提。", BLACK, False)], 'size': 13, 'space_after': 10},
])
add_golden(s, "转发是排除法的坐标系，不是已被指认的凶手。")

# =====================================================================
# SLIDE 25 — 关机直接原因
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("关机直接原因：", BLACK, True), ("12 次 panic 同指令", BLACK, True)], "关机根因", 25)
add_text(s, 0.5, 1.5, 7.0, 4.2, [
    {'runs': [("12 次致命 panic：09-04 ~ 09-14，跨 6 天、8 种受害进程。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("崩溃点 ", BLACK, False), ("12/12 完全一致", YELLOW, True), ("：", BLACK, False)], 'size': 12.5, 'space_after': 4},
    {'runs': [("find_busiest_group+0x140，ldr x23, [x27, #0x120]，机器码 f9409377。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("寄存器交叉验证：x27 + 0x120 精确等于报错地址。", BLACK, False)], 'size': 12.5, 'space_after': 8},
    {'runs': [("报错地址：全部是 ", BLACK, False), ("非规范地址", RED, True), ("（读到随机垃圾值再当指针解引用）。", BLACK, False)], 'size': 12.5, 'space_after': 8},
])
add_code(s, 7.7, 1.6, 5.1, 2.3, [
    "find_busiest_group+0x140",
    "load_balance+0x108",
    "newidle_balance+0x198",
    "pick_next_task_fair",
    "  → __schedule → schedule",
], emph=["find_busiest_group+0x140"])
add_golden(s, "12/12 同指令崩于调度器读 runqueue 统计。")

# =====================================================================
# SLIDE 26 — 机制链条（流程图）
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("机制链条：", BLACK, True), ("从满载到关机", BLACK, True)], "机制链条", 26)
steps = [
    ("1", "全核满载测试（负载逼近核数）", BLACK, False),
    ("2", "调度器把可运行进程摊到全部核（含无关守护进程）", BLACK, False),
    ("3", "进程在 179 上睡眠 / 退出 / 让出 CPU", RED, False),
    ("4", "调度器为其做负载均衡", BLACK, False),
    ("5", "find_busiest_group 在 179 上读 runqueue 统计", RED, False),
    ("6", "179 的 load 读路径随机返回错值", RED, False),
    ("7", "错值被当指针 / 偏移解引用 → 非规范地址 → 翻译错误", BLACK, False),
    ("8", "Oops → kernel panic → kdump → 重启", RED, True),
]
x = 0.9; w = 11.5; y = 1.45; bh = 0.46; ag = 0.115
for i, (num, txt, col, hot) in enumerate(steps):
    yy = y + i * (bh + ag)
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(yy), Inches(w), Inches(bh))
    box.fill.solid(); box.fill.fore_color.rgb = (LIGHT if not hot else RGBColor(0xFB, 0xE9, 0xE9))
    box.line.color.rgb = (RED if hot else GRID); box.line.width = Pt(0.75 if not hot else 1.25)
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.12)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = num + "  "; set_run_font(r, 12, col, True)
    r2 = p.add_run(); r2.text = txt; set_run_font(r2, 11.5, col, False)
    if i < len(steps) - 1:
        ar = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(x + w/2 - 0.08), Inches(yy + bh + 0.005), Inches(0.16), Inches(ag - 0.01))
        ar.fill.solid(); ar.fill.fore_color.rgb = GRAY; ar.line.fill.background()
add_golden(s, "守护进程只是乘客，司机是调度器。", y=6.4)

# =====================================================================
# SLIDE 27 — 触发条件与防护
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("触发条件与防护手段", BLACK, True)], "防护手段", 27)
add_text(s, 0.5, 1.5, 7.2, 4.2, [
    {'runs': [("必要环境：", BLACK, True), ("满载 + 179 在调度器内。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("cpuset 排除 179 无效", RED, True), ("：拦不住 OS 把守护进程调度上 179。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("概率性：满载不必然死，死时必然满载。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("历史死亡窗口：run 启动后 1~16 分钟。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("唯一可靠阻断：", BLACK, True), ("hotplug 下线 179", RED, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 7},
])
box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.0), Inches(1.55), Inches(4.8), Inches(2.2))
box.fill.solid(); box.fill.fore_color.rgb = LIGHT; box.line.color.rgb = GRAY; box.line.width = Pt(1)
add_text(s, 8.2, 1.7, 4.4, 2.0, [
    {'runs': [("旁证：180 核对照（3 小时满载）", BLACK, True)], 'size': 12, 'space_after': 5},
    {'runs': [("179 上访客进程到访两千余次，", BLACK, False)], 'size': 11.5, 'space_after': 2},
    {'runs': [("无一死亡，内核零错误；", BLACK, False)], 'size': 11.5, 'space_after': 2},
    {'runs': [("同期用户态 SDC ", BLACK, False), ("113 次全部在 179", RED, True), ("。", BLACK, False)], 'size': 11.5, 'space_after': 2},
])
add_golden(s, "错在核，不在进程。")

# =====================================================================
# SLIDE 28 — 显形谱系
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("同一根因的显形谱系", BLACK, True)], "显形谱系", 28)
add_table(s, 0.5, 1.5, 12.33, [2.0, 6.3, 4.0], [
    ["形态", "表现", "错值落点"],
    ["用户态 SDC", "数据比对失败，全部核 179", "被测 load 返回值"],
    ["可恢复警告", "spurious translation fault，45+ 例，CPU 全 179", "可重试的页表遍历"],
    ["致命崩溃", "Oops → panic → 重启，12 次同指令", "runqueue 统计 → 坏指针解引用"],
], fs=10.5)
add_text(s, 0.5, 4.5, 12.3, 1.6, [
    {'runs': [("强度递增的三档，共享同一物理来源：", BLACK, False), ("同一根因", YELLOW, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 7},
    {'runs': [("关机不是另一个故障，而是 ", BLACK, False), ("同一个读路径缺陷在内核敏感路径上的显形", RED, True), ("。", BLACK, False)], 'size': 12.5, 'space_after': 7},
])
add_golden(s, "关机不是另一个故障，而是同一读路径缺陷的显形。")

# =====================================================================
# SLIDE 29 — 处置建议
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("处置建议", BLACK, True)], "处置建议", 29)
add_card(s, 0.5, 1.6, 4.0, 4.6, "1  生产处置",
         "hotplug 下线 179，或 RAS 层面隔离，阻断调度。\n\n这是唯一可靠阻断手段。", accent=RED)
add_card(s, 4.66, 1.6, 4.0, 4.6, "2  诊断侧",
         "179 在线 + 全核满载即可复现用户态 SDC；7 个有效用例，约 1~2 次/min 量级，作为硅失效证据链。", accent=YELLOW)
add_card(s, 8.82, 1.6, 4.0, 4.6, "3  硬件侧",
         "读路径（地址捕获 / 数据装配级）为定位方向，建议结合 L1D ECC / RAS 计数器做零扰动佐证。", accent=BLACK)
add_golden(s, "hotplug 下线 179 是唯一可靠阻断；7 用例可作硅失效证据链。")

# =====================================================================
# SLIDE 30 — 总结五句话
# =====================================================================
s = new_slide(); bg_white(s)
add_header(s, [("总结五句话", BLACK, True)], "总结", 30)
pts = [
    ("1", "str+ldr 不充分", "转发微操作逐指令同构却零失败；补齐 2 源+ALU 后被时序灭活；reload 三点拆分。触发 = ≥2 源 load + 轮换 ALU + 紧时序，缺一不可。"),
    ("2", "3ldr+轮换 ALU+2str 骨架", "五步实验收敛；顶部第 3 条 ldr 是有意端口压力设计；固化为 7 个稳定 SDC 用例，失败 100% 在 179。"),
    ("3", "多 ldr / 多 str 边界", "源数 2 是阈值；双 store 无 reload 仍触发（转发非必要）；零 store 即灭活（store 必要）；全链紧邻缺一不可。"),
    ("4", "转发研究现状", "所有活依赖边必须 0 拍；但错误签名指向地址捕获 / 数据装配级，而非旁路数据线。转发是定位地形图，不是凶手。"),
    ("5", "关机根因", "12 次 panic 同指令崩于调度器 find_busiest_group 读 runqueue 统计；179 坏硅读错误被调度路径放大成内核崩溃；hotplug 下线 179 是唯一可靠阻断。"),
]
lines = []
for num, head, body in pts:
    lines.append({'runs': [(num + "  ", YELLOW, True), (head + "：", BLACK, True), (body, BLACK, False)],
                  'size': 12, 'space_after': 9, 'line_spacing': 1.05})
add_text(s, 0.6, 1.45, 12.2, 5.0, lines)
add_golden(s, "转发是地形图，不是凶手；错在核，不在进程。", y=6.4)

# =====================================================================
OUT = r"C:\Users\xupeng\Desktop\华为sdc报告\0102机器时序研究\20260917\CORE179硅失效诊断_20260917.pptx"
prs.save(OUT)
print("SAVED:", OUT)
print("SLIDES:", len(prs.slides._sldIdLst))
