# -*- coding: utf-8 -*-
"""Figures for the congestion-algorithm/tuning companion (Pillow)."""
from PIL import Image, ImageDraw, ImageFont
import os, math

S = 3
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
NAVY = "#0B2545"
BLUE = "#1F4E79"
TEAL = "#2A9D8F"
ORANGE = "#C26A12"
RED = "#B42318"
PURPLE = "#6D4C9F"
GRAY = "#5B6B7C"
LIGHT = "#F5F8FB"
WHITE = "#FFFFFF"
BORDER = "#D6DEE7"


def sc(v): return int(round(v * S))
def font(size, bold=False): return ImageFont.truetype(FONT_B if bold else FONT, sc(size))


def text(d, xy, s, size=18, color=NAVY, bold=False, anchor="la", align="left", spacing=1.25):
    d.multiline_text((sc(xy[0]), sc(xy[1])), s, font=font(size, bold), fill=color,
                     anchor=anchor, align=align, spacing=sc(size * (spacing - 1)))


def box(d, x, y, w, h, fill, outline, width=2.2, radius=10):
    d.rounded_rectangle([sc(x), sc(y), sc(x + w), sc(y + h)], radius=sc(radius),
                        fill=fill, outline=outline, width=sc(width))


def arrow(d, x1, y1, x2, y2, color, width=3.0, head=12, dashed=False):
    x1, y1, x2, y2 = sc(x1), sc(y1), sc(x2), sc(y2)
    if dashed:
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy)
        ux, uy = dx / ln, dy / ln
        pos = 0
        while pos < ln:
            end = min(pos + sc(10), ln)
            d.line([(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end)],
                   fill=color, width=sc(width))
            pos += sc(17)
    else:
        d.line([(x1, y1), (x2, y2)], fill=color, width=sc(width))
    ang = math.atan2(y2 - y1, x2 - x1)
    h = sc(head)
    p1 = (x2 - h * math.cos(ang - math.pi / 7), y2 - h * math.sin(ang - math.pi / 7))
    p2 = (x2 - h * math.cos(ang + math.pi / 7), y2 - h * math.sin(ang + math.pi / 7))
    d.polygon([(x2, y2), p1, p2], fill=color)


def fig_map():
    W, H = 1320, 650
    img = Image.new("RGB", (sc(W), sc(H)), WHITE)
    d = ImageDraw.Draw(img)
    text(d, (35, 18), "RoCE 拥塞控制算法地图（CX6 视角）", 26, NAVY, True)
    text(d, (35, 55), "先分清“谁是拥塞控制、谁是流控、谁只在新平台可用”", 15, GRAY)

    cols = [
        (40, "端到端速率控制", BLUE, "#EAF2FB", [
            ("DCQCN", "ECN + CNP；CX6 主线", "成熟、需 ECN/CNP QoS"),
            ("ZTR-RTT", "RTT + CNP；新平台", "少依赖交换机 ECN 配置"),
            ("TIMELY", "RTT；研究/业界方案", "非 CX6 原生"),
        ]),
        (475, "逐跳 / 链路机制", ORANGE, "#FFF7E8", [
            ("PFC", "流控，不是拥塞控制", "防瞬时溢出，会传播反压"),
            ("QCN 802.1Qau", "L2 CNM；遗留方案", "不是 RoCEv2 的 DCQCN"),
            ("IB Credit", "IB 链路信用", "不是 Ethernet PFC/ECN"),
        ]),
        (910, "可编程 CC", PURPLE, "#F3EEFA", [
            ("DOCA PCC", "自定义算法；BlueField-3", "DPA/DPACC；非 CX6 即用"),
            ("", "", ""),
            ("", "", ""),
        ]),
    ]
    for x, title, accent, fill, items in cols:
        text(d, (x + 5, 95), title, 21, accent, True)
        y = 135
        for name, sub, note in items:
            if not name:
                y += 105
                continue
            box(d, x, y, 370, 88, fill, accent, 2.0)
            text(d, (x + 18, y + 12), name, 22, NAVY, True)
            text(d, (x + 18, y + 45), sub, 15, accent, True)
            text(d, (x + 18, y + 66), note, 12, GRAY)
            y += 105

    d.rectangle([sc(40), sc(555), sc(1280), sc(625)], fill=LIGHT, outline=BORDER, width=sc(1))
    text(d, (60, 568), "CX6 的 RoCEv2 主线 = ECN 标记 + CNP 反馈 + DCQCN 速率控制；PFC 只做 lossless 兜底。",
         17, NAVY, True)
    text(d, (60, 596), "ZTR-RTT 与 PCC 属于更新一代的平台/框架；不要把它们的参数直接套到 CX6。",
         14, GRAY)
    out = os.path.join("assets", "fig_cc_map.png")
    img.save(out, dpi=(300, 300))
    print("saved", out, img.size)


def fig_dcqcn():
    W, H = 1320, 700
    img = Image.new("RGB", (sc(W), sc(H)), WHITE)
    d = ImageDraw.Draw(img)
    text(d, (35, 18), "DCQCN 状态机：降速、恢复与 α", 26, NAVY, True)
    text(d, (35, 55), "默认参数下，降速是“小步快跑”；恢复分 Fast Recovery / AI / HAI 三段", 15, GRAY)

    # State boxes
    box(d, 70, 160, 290, 110, "#EAF2FB", BLUE)
    text(d, (215, 185), "Fast Recovery", 23, NAVY, True, "ma")
    text(d, (215, 220), "向 TargetRate 快速靠拢", 14, GRAY, False, "ma")

    box(d, 515, 160, 290, 110, "#EAF2FB", BLUE)
    text(d, (660, 185), "Additive Increase", 23, NAVY, True, "ma")
    text(d, (660, 220), "TargetRate += AI", 14, GRAY, False, "ma")

    box(d, 960, 160, 290, 110, "#EAF2FB", BLUE)
    text(d, (1105, 185), "Hyper Increase", 23, NAVY, True, "ma")
    text(d, (1105, 220), "TargetRate += HAI", 14, GRAY, False, "ma")

    arrow(d, 360, 215, 513, 215, BLUE, 3, 12)
    text(d, (436, 190), "RPG_THRESHOLD", 13, GRAY, True, "ma")
    arrow(d, 805, 215, 958, 215, BLUE, 3, 12)
    text(d, (881, 190), "双计数器均过阈值", 12, GRAY, True, "ma")

    # CNP / decrease: after a CNP, DCQCN returns to Fast Recovery (not AI)
    box(d, 70, 410, 290, 110, "#FDECEC", RED)
    text(d, (215, 435), "收到 CNP", 23, RED, True, "ma")
    text(d, (215, 470), "Rate Decrease：R ← R(1-α/2^RPG_GD)", 12.5, GRAY, False, "ma")
    arrow(d, 215, 408, 215, 275, RED, 3, 12, dashed=True)
    text(d, (235, 335), "降速 → Fast Recovery；重置计时器/字节计数器", 12, RED, False, "la")

    # Alpha box
    box(d, 940, 390, 330, 145, "#EEF8F5", TEAL)
    text(d, (1105, 410), "α 更新", 21, TEAL, True, "ma")
    text(d, (1105, 445), "有 CNP：α ↑（向 1）\n无 CNP：α ↓（衰减）", 14, NAVY, False, "ma", "center")
    text(d, (1105, 500), "默认 g = 1019/1024", 12, GRAY, False, "ma")

    # Formula strip
    d.rectangle([sc(70), sc(575), sc(1250), sc(640)], fill=LIGHT, outline=BORDER, width=sc(1))
    text(d, (90, 590), "RPG_GD 越大 → 单次降速越温和；RPG_AI_RATE/RPG_HAI_RATE 越大 → 恢复越快、越易振荡。",
         15, NAVY, True)
    text(d, (90, 616), "默认值不是“最优值”，而是通用起点；任何调整都要用 incast 和 P99 验证。",
         13, GRAY)
    out = os.path.join("assets", "fig_dcqcn_state.png")
    img.save(out, dpi=(300, 300))
    print("saved", out, img.size)


def fig_ecn():
    W, H = 1320, 620
    img = Image.new("RGB", (sc(W), sc(H)), WHITE)
    d = ImageDraw.Draw(img)
    text(d, (35, 18), "ECN 标记曲线：Kmin、Kmax、Pmax", 26, NAVY, True)
    text(d, (35, 55), "队列超过 Kmin 后线性增加标记概率，到 Kmax 达到 Pmax；标记不是丢弃", 15, GRAY)

    x0, y0, x1, y1 = 110, 520, 1210, 120
    d.line([sc(x0), sc(y0), sc(x1), sc(y0)], fill=GRAY, width=sc(2))
    d.line([sc(x0), sc(y0), sc(x0), sc(y1)], fill=GRAY, width=sc(2))
    text(d, (x1, y0 + 10), "队列长度 q", 15, GRAY, False, "ra")
    text(d, (x0 - 8, y1 - 8), "标记概率 p", 15, GRAY, False, "ra")

    kmin, kmax = 470, 860
    pmax_y = 220
    # flat 0, ramp, flat pmax
    d.line([sc(x0), sc(y0), sc(kmin), sc(y0)], fill=BLUE, width=sc(4))
    d.line([sc(kmin), sc(y0), sc(kmax), sc(pmax_y)], fill=BLUE, width=sc(4))
    d.line([sc(kmax), sc(pmax_y), sc(x1), sc(pmax_y)], fill=BLUE, width=sc(4))
    for x, lab in ((kmin, "Kmin"), (kmax, "Kmax")):
        d.line([sc(x), sc(y0 - 8), sc(x), sc(y0 + 8)], fill=GRAY, width=sc(2))
        text(d, (x, y0 + 22), lab, 18, NAVY, True, "ma")
    d.line([sc(x0 - 8), sc(pmax_y), sc(x0 + 8), sc(pmax_y)], fill=GRAY, width=sc(2))
    text(d, (x0 - 15, pmax_y), "Pmax", 17, RED, True, "rm")

    text(d, (kmin - 10, 480), "0", 16, BLUE, True, "ma")
    text(d, (kmax + 10, pmax_y - 28), "Pmax", 16, RED, True, "ma")
    text(d, (250, 130), "过早标记：\n吞吐低、降速频繁", 15, ORANGE, True, "ma", "center")
    text(d, (1030, 130), "过晚标记：\nPFC/丢包先发生", 15, RED, True, "ma", "center")
    text(d, (660, 570), "q < Kmin: p=0      Kmin ≤ q < Kmax: p = Pmax·(q-Kmin)/(Kmax-Kmin)      q ≥ Kmax: p=Pmax",
         14, GRAY, False, "ma")

    out = os.path.join("assets", "fig_ecn_curve.png")
    img.save(out, dpi=(300, 300))
    print("saved", out, img.size)


if __name__ == "__main__":
    fig_map()
    fig_dcqcn()
    fig_ecn()
