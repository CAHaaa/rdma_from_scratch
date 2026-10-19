# -*- coding: utf-8 -*-
"""Build the 16:9 lecture deck for the CX6 vs self-developed NIC course."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

OUT = Path("CX6_vs_自研网卡_讲座.pptx")

# ---------- palette ----------
NAVY = RGBColor(0x0B, 0x1F, 0x3A)
NAVY2 = RGBColor(0x16, 0x32, 0x58)
GREEN = RGBColor(0x76, 0xB9, 0x00)
GREEN_D = RGBColor(0x4E, 0x80, 0x00)
TEAL = RGBColor(0x00, 0x96, 0x94)
AMBER = RGBColor(0xE8, 0x9B, 0x00)
RED = RGBColor(0xC0, 0x39, 0x2B)
TEXT = RGBColor(0x1A, 0x20, 0x2C)
GRAY = RGBColor(0x5F, 0x6C, 0x80)
LIGHT = RGBColor(0x8A, 0x96, 0xA8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CARD = RGBColor(0xF4, 0xF7, 0xFA)
BORDER = RGBColor(0xDC, 0xE3, 0xEC)
PALE_GREEN = RGBColor(0xEE, 0xF6, 0xE2)
PALE_BLUE = RGBColor(0xEB, 0xF2, 0xFA)
PALE_AMBER = RGBColor(0xFF, 0xF6, 0xE3)

FONT = "Microsoft YaHei"
MONO = "Consolas"

SW, SH = 13.333, 7.5


def set_run(run, size=14, bold=False, color=TEXT, font=FONT, italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", font)
    cs = rPr.find(qn("a:cs"))
    if cs is None:
        cs = etree.SubElement(rPr, qn("a:cs"))
    cs.set("typeface", font)


def textbox(slide, l, t, w, h, text="", size=14, bold=False, color=TEXT,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line=1.0, font=FONT):
    box = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line
    r = p.add_run()
    r.text = text
    set_run(r, size=size, bold=bold, color=color, font=font)
    return box


def rect(slide, l, t, w, h, fill, line=None, radius=True, line_width=1):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(l), Inches(t), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_width)
    shape.shadow.inherit = False
    if radius:
        try:
            shape.adjustments[0] = 0.08
        except Exception:
            pass
    return shape


def header(slide, section, title, subtitle=None):
    # top accent
    rect(slide, 0.55, 0.34, 0.10, 0.34, GREEN, None, False)
    textbox(slide, 0.75, 0.30, 8.0, 0.32, section.upper(), size=10, bold=True, color=GREEN)
    textbox(slide, 0.55, 0.66, 12.2, 0.62, title, size=27, bold=True, color=NAVY)
    if subtitle:
        textbox(slide, 0.55, 1.26, 12.2, 0.38, subtitle, size=12, color=GRAY)


def footer(slide, idx):
    rect(slide, 0.55, 7.10, 12.23, 0.012, BORDER, None, False)
    textbox(slide, 0.55, 7.16, 8.0, 0.22, "从自研网卡到 NVIDIA ConnectX-6  ·  课程讲义",
            size=8.5, color=LIGHT)
    textbox(slide, 11.7, 7.16, 1.08, 0.22, f"{idx:02d}", size=8.5, color=LIGHT,
            align=PP_ALIGN.RIGHT)


def bullets(slide, l, t, w, h, items, size=13, color=TEXT, gap=6, bullet_color=GREEN):
    box = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.15
        r1 = p.add_run()
        r1.text = "●  "
        set_run(r1, size=size - 4, bold=True, color=bullet_color)
        r2 = p.add_run()
        r2.text = item
        set_run(r2, size=size, color=color)
    return box


def card(slide, l, t, w, h, num, title, body, code_line=None, accent=GREEN_D,
         fill=CARD, title_size=15, body_size=11):
    rect(slide, l, t, w, h, fill, BORDER, True, 0.75)
    rect(slide, l, t, 0.08, h, accent, None, False)
    textbox(slide, l + 0.18, t + 0.12, 0.5, 0.34, num, size=17, bold=True, color=accent)
    textbox(slide, l + 0.62, t + 0.13, w - 0.78, 0.34, title, size=title_size, bold=True, color=NAVY)
    textbox(slide, l + 0.18, t + 0.58, w - 0.36, h - 0.66, body, size=body_size, color=GRAY, line=1.18)
    if code_line:
        rect(slide, l + 0.18, t + h - 0.50, w - 0.36, 0.36, RGBColor(0x0F, 0x1B, 0x2D), None, True)
        textbox(slide, l + 0.28, t + h - 0.46, w - 0.50, 0.28, code_line, size=9.5,
                color=RGBColor(0xD8, 0xE1, 0xEE), font=MONO)


def code_card(slide, l, t, w, h, lines, size=11, title=None):
    rect(slide, l, t, w, h, RGBColor(0x0F, 0x1B, 0x2D), None, True)
    ty = t + 0.12
    if title:
        textbox(slide, l + 0.20, ty, w - 0.4, 0.26, title, size=9, bold=True,
                color=RGBColor(0x8F, 0xA6, 0xC0))
        ty += 0.28
    box = slide.shapes.add_textbox(Inches(l + 0.20), Inches(ty), Inches(w - 0.40), Inches(h - (ty - t) - 0.08))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(0)
        p.line_spacing = 1.15
        r = p.add_run()
        r.text = line if line else " "
        set_run(r, size=size, color=RGBColor(0xD8, 0xE1, 0xEE), font=MONO)


def picture(slide, path, l, t, w, caption=None, caption_y=None):
    slide.shapes.add_picture(path, Inches(l), Inches(t), width=Inches(w))
    if caption:
        textbox(slide, 0.55, caption_y if caption_y is not None else 6.72, 12.23, 0.26,
                caption, size=10, color=GRAY, align=PP_ALIGN.CENTER)


def picture_fit(slide, path, l, t, max_w, max_h):
    iw, ih = Image.open(path).size
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale
    left = l + (max_w - w) / 2
    top = t + (max_h - h) / 2
    slide.shapes.add_picture(path, Inches(left), Inches(top), width=Inches(w))


def table(slide, l, t, w, h, headers, rows, widths, font_size=10.5, header_size=10.5,
          first_bold=False):
    shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(l), Inches(t),
                                   Inches(w), Inches(h))
    tbl = shape.table
    tbl.first_row = True
    tbl.horz_banding = False
    for i, cw in enumerate(widths):
        tbl.columns[i].width = Inches(cw)
    for ci, htxt in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.margin_left = Inches(0.08)
        cell.margin_right = Inches(0.06)
        cell.margin_top = Inches(0.03)
        cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = htxt
        set_run(r, size=header_size, bold=True, color=WHITE)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if ri % 2 == 0 else RGBColor(0xF4, 0xF7, 0xFA)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.line_spacing = 1.0
            r = p.add_run()
            r.text = str(val)
            set_run(r, size=font_size, bold=(first_bold and ci == 0), color=TEXT)
    return tbl


# ==================================================================
# build
# ==================================================================
prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
blank = prs.slide_layouts[6]


def new_slide(bg=WHITE):
    s = prs.slides.add_slide(blank)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s


# ---------- 1 cover ----------
s = new_slide(NAVY)
rect(s, 0, 0, 0.18, 7.5, GREEN, None, False)
textbox(s, 0.95, 0.75, 6.0, 0.30, "COURSE  ·  2026.10", size=11, bold=True, color=GREEN)
textbox(s, 0.95, 1.55, 11.4, 0.80, "从自研网卡到", size=40, bold=True, color=WHITE)
textbox(s, 0.95, 2.35, 11.4, 0.90, "NVIDIA ConnectX-6", size=46, bold=True, color=WHITE)
textbox(s, 0.95, 3.32, 11.0, 0.50, "使用差异分析与 CX6 文档地图", size=21, bold=True, color=GREEN)
textbox(s, 0.95, 4.18, 10.8, 0.65,
        "为什么“CX6 使用说明”找不到  ·  差异通常落在哪 12 个地方  ·  一份可直接照做的文档清单",
        size=12.5, color=RGBColor(0xC9, 0xD4, 0xE2), line=1.3)
# chips
chips = [("12 个差异落点", 1.95), ("6 层文档地图", 1.85), ("30 分钟检查单", 2.05)]
x = 0.95
for c, w in chips:
    rect(s, x, 5.30, w, 0.42, RGBColor(0x16, 0x32, 0x58), GREEN, True, 0.75)
    textbox(s, x + 0.14, 5.37, w - 0.20, 0.28, c, size=10.5, bold=True, color=WHITE)
    x += w + 0.18
textbox(s, 0.95, 6.55, 8.0, 0.30, "讲义 · 幻灯片 · 文档地图  |  适用于网络/云/存储方向的架构、驱动与运维",
        size=9.5, color=RGBColor(0x8F, 0xA6, 0xC0))

# ---------- 2 three questions ----------
s = new_slide()
header(s, "00 · 开场", "今天只回答三个问题", "不是命令大全，而是一张“差异地图 + 文档地图 + 上机检查单”")
qs = [
    ("01", "为什么找不到？", "CX6 是家族；文档按层切；平台在迁移；版本强绑定；大量内容在 KB。", NAVY2),
    ("02", "差异在哪里？", "12 个落点：认卡、驱动、固件、命名、链路、队列、offload、RoCE、SR-IOV、DPDK、存储、调优。", GREEN_D),
    ("03", "上机怎么查？", "30 分钟检查单：认卡 → 认固件 → 认驱动 → 看链路 → 验 RoCE → 开 SR-IOV。", AMBER),
]
for i, (n, t, b, c) in enumerate(qs):
    l = 0.55 + i * 4.10
    rect(s, l, 1.85, 3.90, 3.55, CARD, BORDER, True, 0.75)
    rect(s, l, 1.85, 3.90, 0.08, c, None, False)
    textbox(s, l + 0.22, 2.05, 0.7, 0.55, n, size=30, bold=True, color=c)
    textbox(s, l + 0.22, 2.72, 3.45, 0.45, t, size=17, bold=True, color=NAVY)
    textbox(s, l + 0.22, 3.28, 3.45, 1.55, b, size=11.5, color=GRAY, line=1.28)
    textbox(s, l + 0.22, 4.88, 3.45, 0.25, ["对应讲义：第 1 章", "对应讲义：第 3 章", "对应讲义：第 6 章"][i],
            size=9, bold=True, color=c)
rect(s, 0.55, 5.78, 12.23, 0.85, PALE_GREEN, None, True)
textbox(s, 0.82, 5.97, 11.7, 0.48, "先问“这件事归哪一层管”，再问“用哪条命令”。",
        size=18, bold=True, color=GREEN_D)
footer(s, 2)

# ---------- 3 family ----------
s = new_slide()
header(s, "01 · 认卡", "第一步不是配，是认卡", "“CX6”至少对应三款硅片：VPI / Dx / Lx")
table(s, 0.55, 1.85, 8.3, 2.45,
      ["家族", "定位", "固件分支", "典型 OPN"],
      [
          ["CX6 VPI", "IB + Ethernet 双栈，200Gb/s", "20.43.x", "MCX653106A-HDAT"],
          ["CX6 Dx", "以太网 + 加密卸载，200GbE", "22.4x", "MCX623106AN-CDAT"],
          ["CX6 Lx", "低功耗以太网，50GbE", "26.4x", "MCX631102AN-ADAT"],
      ],
      [1.55, 3.15, 1.45, 2.15], font_size=10.5, header_size=10, first_bold=True)
code_card(s, 9.05, 1.85, 3.73, 2.45, [
    "lspci -nn | grep -i mellanox",
    "mlxfwmanager --query",
    "ethtool -i ens1f0np0",
], size=10.5, title="三条命令定位")
rect(s, 0.55, 4.62, 12.23, 1.02, PALE_AMBER, None, True)
textbox(s, 0.82, 4.78, 11.7, 0.65,
        "型号 / PSID / 固件分支，三者必须对齐；型号错，后面全错。\n"
        "15b3:101b 常见于 VPI；101d 常见于 Dx；101f 常见于 Lx（以 lspci 为准）。",
        size=12, color=TEXT, line=1.3)
footer(s, 3)

# ---------- 4 names ----------
s = new_slide()
header(s, "01 · 命名", "一张卡，至少五个名字", "排障第一步：建立 PCI ↔ netdev ↔ ibdev ↔ VF/representor ↔ MST 的映射")
picture_fit(s, "assets/deck_names.png", 0.55, 1.62, 12.23, 5.25)
footer(s, 4)

# ---------- 5 five reasons ----------
s = new_slide()
header(s, "01 · 为什么找不到", "不是没有文档，是文档不在一层", "五个原因，每一个都对应一种“你以为它在该在的地方”")
reasons = [
    ("1", "家族", "CX6 = VPI / Dx / Lx；三套硅片、三套固件、三套文档。"),
    ("2", "分层", "卡手册只讲硬件；RoCE/QoS/SR-IOV 在 OFED；固件参数在 MFT。"),
    ("3", "迁移", "MLNX_OFED → DOCA-OFED；旧链接 404，命令看起来还能用。"),
    ("4", "版本", "卡 ↔ PSID ↔ 固件 ↔ 驱动 ↔ OS，五元组必须对齐。"),
    ("5", "检索", "中文“CX6 使用说明”命中产品页；英文精确标题才命中手册。"),
]
for i, (n, t, b) in enumerate(reasons):
    y = 1.82 + i * 0.92
    rect(s, 0.55, y, 8.35, 0.78, CARD if i % 2 == 0 else WHITE, BORDER, True, 0.6)
    textbox(s, 0.72, y + 0.12, 0.45, 0.45, n, size=17, bold=True, color=GREEN)
    textbox(s, 1.15, y + 0.09, 1.25, 0.30, t, size=13, bold=True, color=NAVY)
    textbox(s, 2.30, y + 0.10, 6.40, 0.56, b, size=10.5, color=GRAY, line=1.15)
# right search card
rect(s, 9.28, 1.82, 3.50, 4.48, PALE_BLUE, None, True)
textbox(s, 9.50, 2.02, 3.05, 0.30, "把检索词换掉", size=13, bold=True, color=NAVY)
textbox(s, 9.50, 2.42, 3.05, 0.30, "不要搜", size=9.5, bold=True, color=RED)
textbox(s, 9.50, 2.66, 3.05, 0.55, "“CX6 使用说明”\n“CX6 配置手册”", size=10, color=GRAY, line=1.2)
textbox(s, 9.50, 3.30, 3.05, 0.30, "改搜", size=9.5, bold=True, color=GREEN_D)
textbox(s, 9.50, 3.54, 3.05, 2.05,
        "ConnectX-6 Dx Ethernet\nAdapter Cards User Manual\n\nNVIDIA MLNX_OFED 24.10\ninstallation\n\nNVIDIA Firmware Tools\nmlxconfig",
        size=9.8, color=TEXT, line=1.25)
textbox(s, 9.50, 5.75, 3.05, 0.28, "入口：docs.nvidia.com/networking", size=8, color=GRAY)
footer(s, 5)

# ---------- 6 stack ----------
s = new_slide()
s.shapes.add_picture("assets/fig_stack_compare.png", Inches(0.67), Inches(0.25), width=Inches(12.0))
footer(s, 6)

# ---------- 7 map ----------
s = new_slide()
s.shapes.add_picture("assets/fig_difference_map.png", Inches(0.67), Inches(0.25), width=Inches(12.0))
footer(s, 7)

# ---------- 8 points 1-4 ----------
s = new_slide()
header(s, "03 · 识别与版本", "落点 1–4：先搞清楚“你是谁、你从哪来”", "这一组错，后面所有配置都是错的")
cards = [
    ("01", "认卡与型号", "自研：一个型号一本手册。\nCX6：PCI ID + Device Type + PSID 三层识别。", "mlxfwmanager --query"),
    ("02", "驱动安装", "自研：驱动+固件一个包。\nCX6：inbox mlx5_core 或 DOCA-OFED，二选一。", "ofed_info -s"),
    ("03", "固件升级", "自研：厂商刷机工具。\nCX6：MFT + 匹配 PSID 的 .mfa + mlxfwreset。", "mlxfwmanager -u ..."),
    ("04", "固件参数", "自研：私有配置文件。\nCX6：mlxconfig 读写固件 NV 配置。", "mlxconfig q / set / backup"),
]
for i, (n, t, b, c) in enumerate(cards):
    l = 0.55 + (i % 2) * 6.22
    top = 1.82 + (i // 2) * 2.35
    card(s, l, top, 6.01, 2.10, n, t, b, c, accent=NAVY2, body_size=10.8)
textbox(s, 0.55, 6.55, 12.2, 0.30, "判读口诀：Device Type 看家族，PSID 看固件，FW 第一段看分支。",
        size=11, bold=True, color=NAVY)
footer(s, 8)

# ---------- 9 points 5-8 ----------
s = new_slide()
header(s, "03 · 配置与数据面", "落点 5–8：怎么配，配了有没有生效", "同一个“口”，在五个层里有五个名字")
cards = [
    ("05", "设备命名", "netdev / ibdev / VF / representor / MST。\n先用 symlink 建立映射。", "ibdev2netdev"),
    ("06", "链路与光模块", "先看物理层：speed / FEC / BER / DDM。\n不要先怀疑驱动。", "mlxlink -d <mst> -m -c"),
    ("07", "队列与中断", "队列、ring、coalesce 都可调；\n改队列会重置 RSS 表。", "ethtool -L / -G / -C"),
    ("08", "Offload", "软件 counters 有值 ≠ 硬件在做。\n用 skip_sw 验证。", "ethtool -K / tc flower"),
]
for i, (n, t, b, c) in enumerate(cards):
    l = 0.55 + (i % 2) * 6.22
    top = 1.82 + (i // 2) * 2.35
    card(s, l, top, 6.01, 2.10, n, t, b, c, accent=GREEN_D, body_size=10.8)
textbox(s, 0.55, 6.55, 12.2, 0.30, "判读口诀：netdev 看流量，ibdev 看 RoCE，mlxlink 看物理层。",
        size=11, bold=True, color=NAVY)
footer(s, 9)

# ---------- 10 points 9-12 ----------
s = new_slide()
header(s, "03 · 生态与运维", "落点 9–12：怎么用，怎么证明它真的在用", "这一组决定“性能”和“稳定性”，也最容易踩坑")
cards = [
    ("09", "RoCE 与 QoS", "PFC 必须端到端；trust 要在 SR-IOV 之前设。\nRoCE 计数不在 ethtool。", "cma_roce_mode / mlnx_qos"),
    ("10", "SR-IOV", "先固件、再系统、再 switchdev；\n切模式前先 unbind VF。", "sriov_numvfs / devlink"),
    ("11", "DPDK / OVS", "mlx5 是 bifurcated；\n不要把 mlx5 绑到 vfio-pci。", "testpmd -a <bdf>"),
    ("12", "调优与监控", "四个计数器来源：ethtool / IB sysfs /\nmlxlink / devlink health。", "ethtool -S / devlink health"),
]
for i, (n, t, b, c) in enumerate(cards):
    l = 0.55 + (i % 2) * 6.22
    top = 1.82 + (i // 2) * 2.35
    card(s, l, top, 6.01, 2.10, n, t, b, c, accent=AMBER, body_size=10.5)
textbox(s, 0.55, 6.55, 12.2, 0.30, "判读口诀：RoCE 看 IB sysfs，SR-IOV 看 devlink port，DPDK 看 PMD 日志。",
        size=11, bold=True, color=NAVY)
footer(s, 10)

# ---------- 11 files table ----------
s = new_slide()
header(s, "04 · 文件与参数", "所谓“文件系统参数”，在 CX6 上是什么？", "网卡没有文件系统；你要找的是 /sys、/etc、/dev")
table(s, 0.55, 1.80, 12.23, 4.35,
      ["配置对象", "CX6 位置", "重启后"],
      [
          ["IP / MTU", "NetworkManager / systemd-networkd", "保留"],
          ["队列 / ring / coalesce", "ethtool（运行时）", "丢失"],
          ["SR-IOV VF 数", "/sys/class/net/<if>/device/sriov_numvfs", "丢失"],
          ["SRIOV_EN / NUM_OF_VFS", "mlxconfig（固件 NV 配置）", "保留"],
          ["RoCE / PFC", "cma_roce_mode / mlnx_qos", "丢失"],
          ["memlock", "/etc/security/limits.d/", "保留"],
          ["sysctl", "/etc/sysctl.d/", "保留"],
          ["udev 命名", "/etc/udev/rules.d/", "保留"],
      ],
      [4.15, 6.55, 1.53], font_size=10.2, header_size=10, first_bold=True)
textbox(s, 0.55, 6.42, 12.2, 0.30,
        "固化三件套：udev rule · systemd oneshot · NetworkManager dispatcher。",
        size=11, bold=True, color=GREEN_D)
footer(s, 11)

# ---------- 12 persist ----------
s = new_slide()
header(s, "04 · 持久化", "哪些重启会丢？", "把运行时配置变成持久配置，是上机的最后一公里")
# left lose
rect(s, 0.55, 1.80, 6.01, 4.55, RGBColor(0xFD, 0xF2, 0xF0), None, True)
textbox(s, 0.82, 2.00, 5.5, 0.35, "会丢（运行时）", size=15, bold=True, color=RED)
bullets(s, 0.85, 2.48, 5.45, 3.55, [
    "队列 / ring / coalesce（ethtool）",
    "SR-IOV VF 数（sriov_numvfs）",
    "VF MAC / VLAN / trust",
    "RoCE 模式 / PFC / DSCP 映射",
    "hugepages（未写 cmdline 时）",
], size=11.2, gap=8, bullet_color=RED)
# right keep
rect(s, 6.77, 1.80, 6.01, 4.55, PALE_GREEN, None, True)
textbox(s, 7.04, 2.00, 5.5, 0.35, "会保留（固件 / 系统配置）", size=15, bold=True, color=GREEN_D)
bullets(s, 7.07, 2.48, 5.45, 3.55, [
    "SRIOV_EN / NUM_OF_VFS（mlxconfig）",
    "memlock（limits.conf）",
    "sysctl（sysctl.d）",
    "udev 命名规则",
    "modprobe 参数（需 initramfs）",
], size=11.2, gap=8, bullet_color=GREEN_D)
textbox(s, 0.55, 6.52, 12.2, 0.30, "判断标准：命令改的是“寄存器/驱动状态”，还是“固件/配置文件”？",
        size=11, bold=True, color=NAVY)
footer(s, 12)

# ---------- 13 doc map ----------
s = new_slide()
s.shapes.add_picture("assets/fig_doc_map.png", Inches(0.67), Inches(0.25), width=Inches(12.0))
footer(s, 13)

# ---------- 14 six docs ----------
s = new_slide()
header(s, "05 · 必读", "如果只读 6 份，读这 6 份", "完整 14 份清单在讲义第 5 章")
docs = [
    ("01", "CX6 Dx 用户手册", "上架、接口、规格、固件升级、排障", NAVY2),
    ("02", "MLNX_OFED 24.10", "安装、RoCE、QoS、SR-IOV、OVS", GREEN_D),
    ("03", "DOCA-OFED 迁移指南", "为什么改名、怎么迁、时间线", GREEN_D),
    ("04", "MFT / mlxconfig", "固件参数、升级、链路诊断", NAVY2),
    ("05", "mlxlink / mlxcables", "物理层、FEC、BER、光模块 DDM", AMBER),
    ("06", "DPDK mlx5 PMD", "数据面、flow steering、调优", AMBER),
]
for i, (n, t, b, c) in enumerate(docs):
    l = 0.55 + (i % 3) * 4.10
    top = 1.85 + (i // 3) * 2.25
    rect(s, l, top, 3.90, 2.00, CARD, BORDER, True, 0.7)
    rect(s, l, top, 0.08, 2.00, c, None, False)
    textbox(s, l + 0.20, top + 0.14, 0.55, 0.40, n, size=20, bold=True, color=c)
    textbox(s, l + 0.78, top + 0.18, 2.95, 0.45, t, size=14, bold=True, color=NAVY)
    textbox(s, l + 0.20, top + 0.80, 3.50, 0.55, b, size=10.5, color=GRAY, line=1.22)
    textbox(s, l + 0.20, top + 1.42, 3.50, 0.28,
            ["Interfaces / Firmware", "Installation / Ethernet", "Timeline / Profiles",
             "mlxconfig / mlxfwmanager", "Queries / DDM", "Configuration / Tuning"][i],
            size=8.5, bold=True, color=c)
textbox(s, 0.55, 6.45, 12.2, 0.30, "入口：docs.nvidia.com/networking  ·  networking-docs.nvidia.com  ·  enterprise-support.nvidia.com",
        size=10, color=GRAY)
footer(s, 14)

# ---------- 15 task table ----------
s = new_slide()
header(s, "05 · 按任务找", "不要从“文档目录”开始，从“任务”开始", "同一个任务，通常只需要看一份文档的一章")
table(s, 0.55, 1.82, 12.23, 4.30,
      ["你要做的事", "先看这份", "关键章节"],
      [
          ["上架 / 规格 / 接线", "CX6 / Dx 用户手册", "Interfaces / Specifications"],
          ["装驱动、选版本", "MLNX_OFED 24.10 安装", "Installation / Supported OS"],
          ["固件升级 / 改参数", "MFT 手册", "mlxfwmanager / mlxconfig"],
          ["RoCE / PFC / QoS", "OFED Ethernet Network", "RoCE / QoS / ECN"],
          ["SR-IOV / switchdev", "OFED Virtualization", "SR-IOV / Representor"],
          ["DPDK / OVS 卸载", "DPDK mlx5 PMD", "Configuration / Rx-Tx Tuning"],
      ],
      [3.55, 4.55, 4.13], font_size=10.5, header_size=10.2, first_bold=True)
textbox(s, 0.55, 6.45, 12.2, 0.30, "卡手册解决“物理”，OFED 解决“协议与配置”，MFT 解决“固件”，DPDK/OVS 解决“数据面”。",
        size=10.5, color=GRAY)
footer(s, 15)

# ---------- 16 lifecycle ----------
s = new_slide()
header(s, "05 · 版本", "2026 年的版本选择：别把三条线混在一起", "MLNX_OFED 已进入维护期，DOCA-OFED 是新主线")
# timeline
rect(s, 0.55, 2.32, 12.23, 0.06, BORDER, None, False)
points = [
    ("2024-10", "MLNX_OFED\n最后独立版", NAVY2, 0.55),
    ("2025-01", "新功能\n只进 DOCA-OFED", GREEN_D, 4.55),
    ("2027-10", "MLNX_OFED\nEOL", RED, 8.55),
]
for date, label, color, l in points:
    rect(s, l, 2.22, 0.26, 0.26, color, None, True)
    textbox(s, l - 0.05, 1.65, 2.7, 0.30, date, size=13, bold=True, color=color)
    textbox(s, l - 0.05, 2.62, 2.85, 0.60, label, size=10.5, color=TEXT, line=1.2)
# table
table(s, 0.55, 3.55, 12.23, 1.65,
      ["卡", "固件分支", "DOCA 3.2.3 捆绑", "建议"],
      [
          ["ConnectX-6 VPI", "20.43.x", "20.43.8016", "存量用 24.10 LTS"],
          ["ConnectX-6 Dx", "22.4x", "22.47.3576", "新部署 DOCA-OFED 3.x"],
          ["ConnectX-6 Lx", "26.4x", "26.47.3576", "按 OS 支持矩阵选"],
      ],
      [3.3, 2.3, 3.0, 3.63], font_size=9.8, header_size=9.6, first_bold=True)
textbox(s, 0.55, 5.55, 12.2, 0.30, "三个不要：不要混装 inbox/OFED；不要跨 PSID 刷固件；不要只看驱动不看固件。",
        size=11.5, bold=True, color=NAVY)
textbox(s, 0.55, 5.95, 12.2, 0.55,
        "DOCA 3.2+ 使用 DKMS 源码编译，NVIDIA 不再签驱动；Secure Boot 环境要提前规划 MOK/签名。",
        size=9.8, color=GRAY, line=1.2)
footer(s, 16)

# ---------- 17 checklist ----------
s = new_slide()
header(s, "06 · 上机", "30 分钟检查单：先建立映射，再谈性能", "六步，每步一条命令，先跑通再调优")
steps = [
    ("1", "认卡", "lspci -nn | grep -i mellanox"),
    ("2", "认固件", "mlxfwmanager --query"),
    ("3", "认驱动", "ofed_info -s"),
    ("4", "看链路", "mlxlink -d <mst> -m -c"),
    ("5", "验 RoCE", "ibv_devinfo / ibv_rc_pingpong"),
    ("6", "开 SR-IOV", "sriov_numvfs / devlink port"),
]
for i, (n, t, c) in enumerate(steps):
    l = 0.55 + i * 2.05
    rect(s, l, 2.05, 1.88, 2.55, CARD, BORDER, True, 0.7)
    textbox(s, l + 0.16, 2.20, 0.45, 0.40, n, size=22, bold=True, color=GREEN)
    textbox(s, l + 0.16, 2.72, 1.55, 0.35, t, size=13, bold=True, color=NAVY)
    textbox(s, l + 0.14, 3.20, 1.62, 1.20, c, size=8.6, color=GRAY, font=MONO, line=1.25)
textbox(s, 0.55, 4.95, 12.2, 0.55,
        "判读顺序：有没有 link → speed/FEC/BER 是否正常 → GID 是否 v2 → VF 是否能创建。",
        size=11.5, color=TEXT)
textbox(s, 0.55, 5.55, 12.2, 0.55,
        "先记录基线（吞吐/延迟/BER），再做任何调优；否则你无法证明调优有效。",
        size=11.5, bold=True, color=GREEN_D)
footer(s, 17)

# ---------- 18 pitfalls 1 ----------
s = new_slide()
header(s, "07 · 高频坑（上）", "五个最常见的“一开始就错”", "这些错误会让后面的所有步骤都失去意义")
table(s, 0.55, 1.82, 12.23, 4.35,
      ["现象", "根因", "处理"],
      [
          ["把 Dx 当 VPI，刷固件失败", "型号 / PSID 不匹配", "先 query PSID，再下固件"],
          ["ethtool -i 与 ofed_info 对不上", "inbox 与 OFED 混装", "卸掉一套，只留一套"],
          ["只升驱动不升固件", "新功能依赖新固件", "按兼容矩阵成对升级"],
          ["mlxconfig 改完不生效", "没重启 / 没 mlxfwreset", "query 后 reset，或重启"],
          ["SR-IOV 创建 VF 失败", "BIOS 未开 4G/IOMMU", "开 above 4G + VT-d + iommu=pt"],
      ],
      [4.55, 3.85, 3.83], font_size=10.2, header_size=10, first_bold=False)
textbox(s, 0.55, 6.42, 12.2, 0.30, "三条铁律：型号不对不做；驱动与固件成对升级；改完先问“运行时还是固件”。",
        size=10.5, bold=True, color=NAVY)
footer(s, 18)

# ---------- 19 pitfalls 2 ----------
s = new_slide()
header(s, "07 · 高频坑（下）", "五个最容易“配了但没生效”", "问题通常不在命令，而在“层”搞错了")
table(s, 0.55, 1.82, 12.23, 4.35,
      ["现象", "根因", "处理"],
      [
          ["切 switchdev 失败", "VF 还被驱动占用", "先 unbind 所有 VF"],
          ["RoCE 丢包 / 重传", "交换机没配 PFC", "端到端同优先级开 PFC"],
          ["找不到 RoCE 丢包计数", "看错计数器", "看 IB sysfs 的 counters"],
          ["DPDK 起不来", "把 mlx5 绑到 vfio-pci", "保留 mlx5_core，用 -a <bdf>"],
          ["跨型号刷固件变砖", "只看文件名不看 PSID", "永远按 PSID 匹配 + 先备份"],
      ],
      [4.55, 3.85, 3.83], font_size=10.2, header_size=10, first_bold=False)
textbox(s, 0.55, 6.42, 12.2, 0.30, "排障顺序：物理层 → 驱动/固件 → 配置 → 协议 → 应用。不要跳层。",
        size=10.5, bold=True, color=NAVY)
footer(s, 19)

# ---------- 20 agenda ----------
s = new_slide()
header(s, "08 · 课程设计", "90 分钟怎么讲", "如果只有 45 分钟：讲第 1、3、5 章，第 6 章留作课后材料")
segments = [
    ("0–5", "开场", 0.55, 0.85, NAVY2),
    ("5–20", "认知", 1.45, 2.05, NAVY2),
    ("20–40", "差异地图", 3.55, 2.75, GREEN_D),
    ("40–55", "现场 Demo", 6.35, 2.05, GREEN_D),
    ("55–70", "文档地图", 8.45, 2.05, AMBER),
    ("70–82", "排障演练", 10.55, 1.65, AMBER),
    ("82–90", "总结", 12.25, 0.50, RED),
]
rect(s, 0.55, 2.30, 12.23, 0.55, RGBColor(0xEE, 0xF2, 0xF7), None, True)
for label, name, l, w, color in segments:
    rect(s, l, 2.30, w - 0.04, 0.55, color, None, False)
    textbox(s, l + 0.04, 2.38, max(w - 0.10, 0.4), 0.22, label, size=8.2, bold=True, color=WHITE)
    textbox(s, l + 0.04, 2.60, max(w - 0.10, 0.4), 0.20, name, size=7.8, color=WHITE)
textbox(s, 0.55, 3.25, 12.2, 0.30, "每个模块的产出：一张图、一条命令、一份文档、一个坑。", size=11, color=GRAY)
# bottom three cards
outs = [
    ("讲完能做什么", "认卡、找文档、按检查单上机；不追求背命令。"),
    ("现场演示什么", "认卡、mlxlink、ibv_devinfo、sriov_numvfs、testpmd。"),
    ("课后留什么", "12 步检查单 + 14 份文档清单 + 12 个坑。"),
]
for i, (t, b) in enumerate(outs):
    l = 0.55 + i * 4.10
    rect(s, l, 4.10, 3.90, 1.85, CARD, BORDER, True, 0.7)
    textbox(s, l + 0.22, 4.28, 3.45, 0.35, t, size=13, bold=True, color=NAVY)
    textbox(s, l + 0.22, 4.78, 3.45, 0.95, b, size=10.5, color=GRAY, line=1.25)
textbox(s, 0.55, 6.35, 12.2, 0.30, "讲义第 8 章含完整时间表、演示脚本、互动问题与课后作业。",
        size=10, color=LIGHT)
footer(s, 20)

# ---------- 21 links ----------
s = new_slide()
header(s, "09 · 资料", "资料入口：把这几条链接带走", "完整 14 份清单与可点击链接见《CX6文档地图.md》")
links = [
    ("文档总入口", "docs.nvidia.com/networking", "所有手册/固件/工具的起点", NAVY2),
    ("CX6 Dx 手册", "networking-docs.nvidia.com/\nconnectx6dxhw", "上架、规格、固件升级、排障", GREEN_D),
    ("OFED 24.10", "networking-docs.nvidia.com/\nmlnxofedswum/24101140lts", "安装、RoCE、QoS、SR-IOV", GREEN_D),
    ("MFT / mlxconfig", "networking-docs.nvidia.com/\nmftswum/434118lts", "固件参数、刷机、链路诊断", NAVY2),
    ("DPDK mlx5", "doc.dpdk.org/guides/\nnics/mlx5.html", "数据面、flow steering、调优", AMBER),
    ("支持 KB", "enterprise-support.nvidia.com", "调优、计数器、配置示例", AMBER),
]
for i, (t, u, b, c) in enumerate(links):
    l = 0.55 + (i % 3) * 4.10
    top = 1.85 + (i // 3) * 2.15
    rect(s, l, top, 3.90, 1.93, CARD, BORDER, True, 0.7)
    rect(s, l, top, 0.08, 1.93, c, None, False)
    textbox(s, l + 0.20, top + 0.14, 3.45, 0.30, t, size=13, bold=True, color=NAVY)
    textbox(s, l + 0.20, top + 0.52, 3.50, 0.62, u, size=8.8, color=c, font=MONO, line=1.2)
    textbox(s, l + 0.20, top + 1.30, 3.50, 0.45, b, size=9.5, color=GRAY, line=1.15)
textbox(s, 0.55, 6.40, 12.23, 0.30, "建议：把《CX6文档地图.md》发给学员，链接可直接点击。",
        size=10, color=GRAY)
footer(s, 21)

# ---------- 22 closing ----------
s = new_slide(NAVY)
rect(s, 0, 0, 0.18, 7.5, GREEN, None, False)
textbox(s, 0.95, 0.85, 8.0, 0.30, "TAKEAWAYS", size=11, bold=True, color=GREEN)
textbox(s, 0.95, 1.35, 11.5, 0.70, "带走三句话", size=38, bold=True, color=WHITE)
lines = [
    ("01", "CX6 不是一张卡，是一个家族。", "VPI / Dx / Lx，三套固件、三套文档；先认卡，再谈配置。"),
    ("02", "文档按层找，不按卡找。", "卡手册 / OFED / MFT / DPDK / KB；每层回答不同的问题。"),
    ("03", "先认卡、再认栈、最后才调优。", "型号、PSID、固件、驱动、OS 五元组对齐，调优才有意义。"),
]
for i, (n, t, b) in enumerate(lines):
    y = 2.55 + i * 1.35
    textbox(s, 0.95, y, 0.55, 0.45, n, size=22, bold=True, color=GREEN)
    textbox(s, 1.55, y - 0.04, 10.8, 0.42, t, size=19, bold=True, color=WHITE)
    textbox(s, 1.55, y + 0.38, 10.8, 0.38, b, size=11.5, color=RGBColor(0xC9, 0xD4, 0xE2))
textbox(s, 0.95, 6.52, 11.8, 0.32,
        "谢谢  ·  Q&A  ·  资料：docs.nvidia.com/networking  |  networking-docs.nvidia.com",
        size=10, color=RGBColor(0x8F, 0xA6, 0xC0))

prs.save(OUT)
print("saved", OUT)
