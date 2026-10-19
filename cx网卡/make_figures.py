# -*- coding: utf-8 -*-
"""Generate the diagrams used by the CX6 lecture handout and slide deck."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path("assets")
OUT.mkdir(exist_ok=True)

# ---------- palette ----------
NAVY = (11, 31, 58)
NAVY2 = (22, 50, 88)
GREEN = (118, 185, 0)
GREEN_D = (78, 128, 0)
TEAL = (0, 150, 148)
AMBER = (232, 155, 0)
TEXT = (26, 32, 44)
MUTED = (96, 108, 126)
LINE = (214, 221, 230)
WHITE = (255, 255, 255)
BG = (247, 249, 252)
BLUE_L = (232, 240, 250)
GREEN_L = (236, 246, 224)
AMBER_L = (255, 246, 224)
GRAY_L = (241, 244, 248)

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
MONO = "C:/Windows/Fonts/consola.ttf"


def f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def fm(size):
    return ImageFont.truetype(MONO, size)


def wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            trial = cur + ch
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
    return lines


def draw_para(draw, xy, text, font, fill, max_w, line_gap=8, align="left"):
    x, y = xy
    lines = wrap(draw, text, font, max_w)
    lh = font.size * 1.35
    for line in lines:
        if align == "center":
            w = draw.textlength(line, font=font)
            draw.text((x + (max_w - w) / 2, y), line, font=font, fill=fill)
        else:
            draw.text((x, y), line, font=font, fill=fill)
        y += lh + line_gap
    return y


def rrect(draw, box, radius, fill, outline=None, width=2, shadow=True):
    x0, y0, x1, y1 = box
    if shadow:
        draw.rounded_rectangle((x0 + 8, y0 + 10, x1 + 8, y1 + 10), radius=radius,
                               fill=(226, 231, 238))
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw, xy, text, font, fill, fg=WHITE, padx=22, pady=10):
    x, y = xy
    w = draw.textlength(text, font=font)
    h = font.size + pady * 2
    draw.rounded_rectangle((x, y, x + w + padx * 2, y + h), radius=h // 2, fill=fill)
    draw.text((x + padx, y + pady - 2), text, font=font, fill=fg)
    return w + padx * 2


# =========================================================
# Figure 1 - stack comparison
# =========================================================
def fig_stack():
    W, H = 2400, 1350
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((100, 52), "同一件事，两套栈", font=f(64, True), fill=NAVY)
    d.text((100, 138), "自研网卡通常只有一个入口；ConnectX-6 把能力分散在六个标准层里",
           font=f(29), fill=MUTED)

    # headers
    lx, rx, cw = 100, 1270, 1030
    rrect(d, (lx, 220, lx + cw, 290), 14, NAVY2, None, shadow=False)
    d.text((lx + 30, 237), "自研网卡（典型形态）", font=f(30, True), fill=WHITE)
    rrect(d, (rx, 220, rx + cw, 290), 14, GREEN_D, None, shadow=False)
    d.text((rx + 30, 237), "NVIDIA ConnectX-6（标准分层）", font=f(30, True), fill=WHITE)

    left = [
        ("L5  运维面", "厂商 CLI / 私有 REST / 单一日志入口"),
        ("L4  配置面", "私有配置文件 + 厂商工具"),
        ("L3  数据面", "自研 PMD / 内核驱动 / 私有流表"),
        ("L2  驱动", "自研驱动，与固件强绑定"),
        ("L1  固件", "私有格式，随驱动包发布"),
        ("L0  硬件", "自研 ASIC / FPGA"),
    ]
    right = [
        ("L5  运维面", "ethtool · devlink · sysfs · mlxlink"),
        ("L4  配置面", "mlxconfig · mlnx_qos · iproute2 · tc"),
        ("L3  数据面", "RDMA verbs · DPDK mlx5 · OVS ASAP² · NVMe-oF"),
        ("L2  驱动", "mlx5_core（inbox 或 DOCA-OFED）"),
        ("L1  固件", "MFT 工具链（mlxfwmanager / flint）"),
        ("L0  硬件", "CX6 VPI · CX6 Dx · CX6 Lx"),
    ]

    y0, bh, gap = 318, 128, 18
    for i, ((ln, lt), (rn, rt)) in enumerate(zip(left, right)):
        y = y0 + i * (bh + gap)
        rrect(d, (lx, y, lx + cw, y + bh), 12, WHITE, LINE, 2)
        d.rectangle((lx, y + 18, lx + 8, y + bh - 18), fill=(150, 160, 175))
        d.text((lx + 30, y + 20), ln, font=f(21, True), fill=MUTED)
        draw_para(d, (lx + 30, y + 55), lt, f(26), TEXT, cw - 60, line_gap=2)

        rrect(d, (rx, y, rx + cw, y + bh), 12, WHITE, (198, 220, 170), 2)
        d.rectangle((rx, y + 18, rx + 8, y + bh - 18), fill=GREEN)
        d.text((rx + 30, y + 20), rn, font=f(21, True), fill=GREEN_D)
        draw_para(d, (rx + 30, y + 55), rt, f(26), TEXT, cw - 60, line_gap=2)

    # centre arrows and labels
    cy = y0 + 3 * (bh + gap) - gap // 2
    for dy, label in [(-250, "标准接口"), (0, "多层可替换"), (250, "版本矩阵")]:
        yy = cy + dy
        d.line((1150, yy, 1250, yy), fill=NAVY, width=5)
        d.polygon([(1150, yy), (1166, yy - 10), (1166, yy + 10)], fill=NAVY)
        d.polygon([(1250, yy), (1234, yy - 10), (1234, yy + 10)], fill=NAVY)
        tw = d.textlength(label, font=f(20, True))
        d.rounded_rectangle((1200 - tw / 2 - 12, yy - 44, 1200 + tw / 2 + 12, yy - 8),
                            radius=8, fill=BG)
        d.text((1200 - tw / 2, yy - 40), label, font=f(20, True), fill=NAVY)

    # bottom callout
    rrect(d, (100, 1205, 2300, 1305), 14, (255, 255, 255), GREEN, 3, shadow=False)
    d.rectangle((100, 1205, 112, 1305), fill=GREEN)
    d.text((140, 1222), "课程的主线：", font=f(25, True), fill=GREEN_D)
    d.text((330, 1220), "不要问“CX6 的配置命令是什么”，先问“这件事归哪一层管”。",
           font=f(27), fill=TEXT)

    img.save(OUT / "fig_stack_compare.png", quality=95)
    print("saved", OUT / "fig_stack_compare.png")


# =========================================================
# Figure 2 - 12 difference points
# =========================================================
def fig_map():
    W, H = 2400, 1350
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((100, 48), "差异通常落在哪里：12 个落点", font=f(60, True), fill=NAVY)
    d.text((100, 128), "从“认卡”到“调优”，每一个落点都对应一组标准工具和一份文档",
           font=f(28), fill=MUTED)

    # legend
    x = 100
    for label, color in [("① 识别与版本", NAVY2), ("② 配置与数据面", GREEN_D), ("③ 生态与运维", AMBER)]:
        x += pill(d, (x, 188), label, f(20, True), color) + 18

    items = [
        ("01", "认卡与型号", "lspci · mlxfwmanager --query", "先分清 VPI / Dx / Lx", NAVY2),
        ("02", "驱动安装", "inbox mlx5_core vs DOCA-OFED", "版本线与 OS 兼容矩阵", NAVY2),
        ("03", "固件升级", "mlxfwmanager · mlxfwreset", "PSID 与固件分支必须匹配", NAVY2),
        ("04", "固件参数", "mlxconfig q / set / backup", "改完要重启或 fwreset", NAVY2),
        ("05", "设备命名", "netdev · ibdev · representor", "一张卡至少五个名字", GREEN_D),
        ("06", "链路与光模块", "ethtool -m · mlxlink", "物理层问题先看这里", GREEN_D),
        ("07", "队列与中断", "ethtool -L / -G / -C", "改队列会重置 RSS 表", GREEN_D),
        ("08", "Offload", "ethtool -K · tc flower", "软件能看到的不等于硬件在做", GREEN_D),
        ("09", "RoCE 与 QoS", "cma_roce_mode · mlnx_qos", "PFC 必须端到端配置", GREEN_D),
        ("10", "SR-IOV", "sriov_numvfs · switchdev", "VF 未解绑不能切模式", AMBER),
        ("11", "DPDK / OVS", "bifurcated · ASAP²", "不要把 mlx5 绑到 vfio-pci", AMBER),
        ("12", "调优与监控", "tuned · sysfs · devlink health", "四个计数器来源要对上", AMBER),
    ]

    cw, ch, gx, gy = 700, 228, 40, 30
    x0, y0 = 100, 252
    for i, (num, title, cmd, note, color) in enumerate(items):
        col, row = i % 3, i // 3
        x = x0 + col * (cw + gx)
        y = y0 + row * (ch + gy)
        fill = {NAVY2: BLUE_L, GREEN_D: GREEN_L, AMBER: AMBER_L}[color]
        rrect(d, (x, y, x + cw, y + ch), 16, WHITE, LINE, 2)
        d.rectangle((x, y, x + 10, y + ch), fill=color)
        d.rounded_rectangle((x + 28, y + 24, x + 100, y + 78), radius=12, fill=color)
        d.text((x + 44, y + 32), num, font=f(28, True), fill=WHITE)
        d.text((x + 118, y + 28), title, font=f(30, True), fill=NAVY)
        draw_para(d, (x + 28, y + 96), cmd, fm(21), color, cw - 56, line_gap=1)
        draw_para(d, (x + 28, y + 152), note, f(21), MUTED, cw - 56, line_gap=1)

    img.save(OUT / "fig_difference_map.png", quality=95)
    print("saved", OUT / "fig_difference_map.png")


# =========================================================
# Figure 3 - documentation map
# =========================================================
def fig_docs():
    W, H = 2400, 1350
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((100, 48), "CX6 文档地图：按层找，不要按“卡”找", font=f(58, True), fill=NAVY)
    d.text((100, 126), "同一张卡，六层文档；每层回答不同的问题",
           font=f(28), fill=MUTED)

    rows = [
        ("L5", "应用 / 生态", "DPDK mlx5 PMD · rdma-core · OVS · SPDK", "写代码、做卸载、跑存储", GREEN_D),
        ("L4", "配置 / 工具", "ethtool · devlink · mlnx_qos · sysfs", "日常配置与排障", GREEN_D),
        ("L3", "驱动 / 栈", "MLNX_OFED 24.10 · DOCA-OFED · Release Notes", "安装、升级、兼容性", NAVY2),
        ("L2", "固件工具", "MFT · mlxconfig · mlxlink · mlxfwmanager", "改卡、刷机、看链路", NAVY2),
        ("L1", "硬件手册", "CX6 VPI User Manual · CX6 Dx User Manual", "上架、接线、规格", AMBER),
        ("L0", "发布 / 兼容", "Firmware Release Notes · Compatibility Matrix", "选版本、查支持", AMBER),
    ]

    x0, y0, w, h, gap = 100, 218, 2200, 150, 18
    for i, (lid, lname, docs, when, color) in enumerate(rows):
        y = y0 + i * (h + gap)
        rrect(d, (x0, y, x0 + w, y + h), 14, WHITE, LINE, 2)
        d.rectangle((x0, y, x0 + 12, y + h), fill=color)
        # layer badge
        d.rounded_rectangle((x0 + 34, y + 34, x0 + 148, y + 116), radius=12,
                            fill=color)
        d.text((x0 + 58, y + 48), lid, font=f(34, True), fill=WHITE)

        d.text((x0 + 190, y + 28), lname, font=f(26, True), fill=color)
        draw_para(d, (x0 + 190, y + 70), docs, f(25), TEXT, 1230, line_gap=2)

        d.line((x0 + 1480, y + 28, x0 + 1480, y + h - 28), fill=LINE, width=2)
        d.text((x0 + 1520, y + 28), "什么时候看", font=f(19, True), fill=MUTED)
        draw_para(d, (x0 + 1520, y + 66), when, f(23), TEXT, 620, line_gap=2)

    # right edge note
    d.text((100, 1252), "入口：docs.nvidia.com/networking  ·  networking-docs.nvidia.com  ·  enterprise-support.nvidia.com",
           font=f(22), fill=MUTED)

    img.save(OUT / "fig_doc_map.png", quality=95)
    print("saved", OUT / "fig_doc_map.png")


# =========================================================
# Figure 4 - one card, many names
# =========================================================
def fig_names():
    W, H = 2400, 1000
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((100, 44), "一张卡，至少五个名字", font=f(58, True), fill=NAVY)
    d.text((100, 120), "排障的第一步不是看日志，而是建立 PCI · netdev · ibdev · VF/representor · MST 的映射",
           font=f(26), fill=MUTED)

    # central card
    cx0, cy0, cw, ch = 850, 190, 700, 128
    rrect(d, (cx0, cy0, cx0 + cw, cy0 + ch), 16, NAVY2, None, shadow=True)
    d.text((cx0 + 30, cy0 + 20), "PCI 设备（BDF）", font=f(20, True), fill=(180, 205, 230))
    d.text((cx0 + 30, cy0 + 56), "0000:3b:00.0", font=fm(40), fill=WHITE)

    # horizontal bus
    bus_y = 375
    d.line((100, bus_y, 2300, bus_y), fill=(170, 183, 200), width=4)
    d.line((1200, cy0 + ch, 1200, bus_y), fill=(170, 183, 200), width=4)

    nodes = [
        ("PF netdev", "ens1f0np0", "ip link · ethtool", 100, BLUE_L, NAVY2),
        ("RDMA 设备", "mlx5_0", "ibv_devinfo · rdma link", 550, BLUE_L, NAVY2),
        ("VF netdev", "ens1f0v0", "虚拟机内 ip link", 1000, GREEN_L, GREEN_D),
        ("VF representor", "pf0vf0", "switchdev 模式", 1450, GREEN_L, GREEN_D),
        ("MFT 设备", "/dev/mst/\nmt4123_pciconf0", "mlxconfig · mlxlink", 1900, AMBER_L, AMBER),
    ]

    nw, nh, ny = 400, 178, 435
    for label, name, tool, x, fill, color in nodes:
        cx = x + nw / 2
        d.line((cx, bus_y, cx, ny), fill=(170, 183, 200), width=3)
        d.ellipse((cx - 7, bus_y - 7, cx + 7, bus_y + 7), fill=color)
        rrect(d, (x, ny, x + nw, ny + nh), 14, fill, color, 2)
        d.text((x + 22, ny + 16), label, font=f(20, True), fill=color)
        draw_para(d, (x + 22, ny + 46), name, fm(25), TEXT, nw - 44, line_gap=1)
        d.text((x + 22, ny + 136), "看这里：" + tool, font=f(17), fill=MUTED)

    # three common misreadings
    notes = [
        ("把 VF 当 PF", "ens1f0v0 是虚拟机里的口，不是主机 PF。"),
        ("在 ethtool 找 RoCE 计数", "RoCE 计数在 IB sysfs，不在 netdev。"),
        ("把 MST 名当固定值", "mt4123 只是 CX6 常见值，以 mst status -v 为准。"),
    ]
    for i, (t, s) in enumerate(notes):
        x = 100 + i * 750
        rrect(d, (x, 650, x + 700, 785), 12, WHITE, LINE, 2, shadow=False)
        d.rectangle((x, 650, x + 7, 785), fill=(150, 160, 175))
        d.text((x + 24, 666), t, font=f(23, True), fill=NAVY)
        draw_para(d, (x + 24, 706), s, f(20), MUTED, 650, line_gap=1)

    # callout
    rrect(d, (100, 850, 2300, 930), 12, WHITE, GREEN, 3, shadow=False)
    d.text((130, 868), "建议：把这张映射表写进你们的《上机检查单》，比记住任何一条命令都重要。",
           font=f(26, True), fill=GREEN_D)

    img.save(OUT / "fig_names_map.png", quality=95)
    print("saved", OUT / "fig_names_map.png")


if __name__ == "__main__":
    fig_stack()
    fig_map()
    fig_docs()
    fig_names()
