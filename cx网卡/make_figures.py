# -*- coding: utf-8 -*-
"""Simplified, readable diagrams for the ConnectX-6 CC/PFC guide (Pillow only)."""
from PIL import Image, ImageDraw, ImageFont
import os

S = 3  # supersampling; logical canvas scaled by 3
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

NAVY = "#0B2545"
BLUE = "#1F4E79"
TEAL = "#2A9D8F"
ORANGE = "#C26A12"
RED = "#B42318"
GRAY = "#5B6B7C"
LIGHT_BLUE = "#EEF4FA"
LIGHT_GREEN = "#EEF8F5"
WHITE = "#FFFFFF"
BORDER = "#D6DEE7"


def sc(v):
    return int(round(v * S))


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, sc(size))


def text(draw, xy, s, size=18, color=NAVY, bold=False, anchor="la", align="left", spacing=1.25):
    draw.multiline_text(
        (sc(xy[0]), sc(xy[1])), s, font=font(size, bold), fill=color,
        anchor=anchor, align=align, spacing=sc(size * (spacing - 1.0))
    )


def text_bg(draw, xy, s, size=18, color=NAVY, bold=False, anchor="ma", align="center",
            spacing=1.25, pad=5, bg=WHITE):
    f = font(size, bold)
    bbox = draw.multiline_textbbox(
        (sc(xy[0]), sc(xy[1])), s, font=f, anchor=anchor, align=align,
        spacing=sc(size * (spacing - 1.0))
    )
    draw.rounded_rectangle(
        [bbox[0] - sc(pad), bbox[1] - sc(pad), bbox[2] + sc(pad), bbox[3] + sc(pad)],
        radius=sc(3), fill=bg
    )
    draw.multiline_text(
        (sc(xy[0]), sc(xy[1])), s, font=f, fill=color,
        anchor=anchor, align=align, spacing=sc(size * (spacing - 1.0))
    )


def box(draw, x, y, w, h, fill, outline, width=2.2, radius=10):
    draw.rounded_rectangle(
        [sc(x), sc(y), sc(x + w), sc(y + h)],
        radius=sc(radius), fill=fill, outline=outline, width=sc(width)
    )


def arrow(draw, x1, y1, x2, y2, color, width=3.0, double=False, dashed=False, head=13):
    import math
    x1, y1, x2, y2 = sc(x1), sc(y1), sc(x2), sc(y2)
    w = sc(width)
    if dashed:
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        dash, gap = sc(12), sc(9)
        pos = 0
        while pos < length:
            end = min(pos + dash, length)
            draw.line([(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end)],
                      fill=color, width=w)
            pos += dash + gap
    else:
        draw.line([(x1, y1), (x2, y2)], fill=color, width=w)

    ang = math.atan2(y2 - y1, x2 - x1)
    h = sc(head)
    p1 = (x2 - h * math.cos(ang - math.pi / 7), y2 - h * math.sin(ang - math.pi / 7))
    p2 = (x2 - h * math.cos(ang + math.pi / 7), y2 - h * math.sin(ang + math.pi / 7))
    draw.polygon([(x2, y2), p1, p2], fill=color)
    if double:
        ang2 = ang + math.pi
        p3 = (x1 - h * math.cos(ang2 - math.pi / 7), y1 - h * math.sin(ang2 - math.pi / 7))
        p4 = (x1 - h * math.cos(ang2 + math.pi / 7), y1 - h * math.sin(ang2 + math.pi / 7))
        draw.polygon([(x1, y1), p3, p4], fill=color)


def architecture():
    W, H = 1320, 610
    img = Image.new("RGB", (sc(W), sc(H)), WHITE)
    d = ImageDraw.Draw(img)

    # ECN domain band
    d.rectangle([sc(25), sc(25), sc(1295), sc(100)], fill=LIGHT_GREEN, outline="#CFE6E2", width=sc(1.0))
    text(d, (45, 38), "ECN / DCQCN：端到端闭环", 24, TEAL, True)
    text(d, (45, 72), "CP 标记 CE  →  NP 生成 CNP  →  RP 调整速率", 15, GRAY, False)

    # CNP path
    arrow(d, 990, 128, 330, 128, TEAL, 2.6, dashed=True, head=12)
    text_bg(d, (660, 84), "CNP：DSCP 48 / PCP 6，strict", 16, TEAL, True, "ma")

    # Host A
    box(d, 50, 160, 280, 250, "#EAF2FB", BLUE, 2.4)
    text(d, (190, 192), "服务器 A", 30, NAVY, True, "ma")
    text(d, (190, 232), "ConnectX-6", 18, GRAY, False, "ma")
    text(d, (190, 278), "RP 反应点", 24, BLUE, True, "ma")
    text(d, (190, 320), "按 CNP 调整 QP 速率", 17, NAVY, False, "ma")

    # Switch
    box(d, 460, 150, 400, 270, "#FFF7E8", ORANGE, 2.6)
    text(d, (660, 184), "交换机", 30, NAVY, True, "ma")
    text(d, (660, 226), "CP 拥塞点", 24, ORANGE, True, "ma")
    text(d, (660, 270), "ECN 标记", 18, NAVY, False, "ma")
    text(d, (660, 310), "Egress 队列 / Kmin / Kmax", 16, GRAY, False, "ma")
    text(d, (660, 360), "Ingress PG / Xoff / Xon", 16, GRAY, False, "ma")

    # Host B
    box(d, 990, 160, 280, 250, "#EAF7F4", TEAL, 2.4)
    text(d, (1130, 192), "服务器 B", 30, NAVY, True, "ma")
    text(d, (1130, 232), "ConnectX-6", 18, GRAY, False, "ma")
    text(d, (1130, 278), "NP 通知点", 24, TEAL, True, "ma")
    text(d, (1130, 320), "生成 CNP 回送源端", 17, NAVY, False, "ma")

    # Data path
    arrow(d, 330, 455, 460, 455, BLUE, 3.4, head=13)
    arrow(d, 860, 455, 990, 455, BLUE, 3.4, head=13)
    text(d, (395, 430), "RoCEv2 数据", 18, BLUE, True, "ma")
    text(d, (925, 430), "CE 标记", 18, BLUE, True, "ma")

    # PFC band
    d.rectangle([sc(25), sc(500), sc(1295), sc(595)], fill=LIGHT_BLUE, outline=BORDER, width=sc(1.0))
    text(d, (45, 506), "PFC：逐跳链路反压（不提供端到端语义）", 20, BLUE, True)
    arrow(d, 330, 572, 460, 572, ORANGE, 2.8, double=True, head=12)
    arrow(d, 860, 572, 990, 572, ORANGE, 2.8, double=True, head=12)
    text(d, (395, 546), "PFC", 18, ORANGE, True, "ma")
    text(d, (925, 546), "PFC", 18, ORANGE, True, "ma")

    out = os.path.join("assets", "fig_architecture.png")
    img.save(out, dpi=(300, 300))
    print("saved", out, img.size)


def pfc_buffer():
    W, H = 1320, 470
    img = Image.new("RGB", (sc(W), sc(H)), WHITE)
    d = ImageDraw.Draw(img)

    text(d, (30, 15), "PFC 缓冲与阈值", 26, NAVY, True)
    text(d, (30, 50), "Xoff 触发 Pause；Xon 解除 Pause；两者之间留回差", 16, GRAY, False)

    # Headroom
    d.rounded_rectangle([sc(70), sc(95), sc(1250), sc(165)], radius=sc(8),
                        fill="#FFF1E6", outline=ORANGE, width=sc(2.2))
    text(d, (660, 130), "Headroom：吸收 Xoff 后仍在链路上的报文", 22, ORANGE, True, "mm")

    # Main reserved buffer
    x0, y0, w, h = 70, 240, 1180, 80
    d.rounded_rectangle([sc(x0), sc(y0), sc(x0 + w), sc(y0 + h)], radius=sc(8),
                        fill="#E8F0F8", outline=BLUE, width=sc(2.2))
    used_w = w * 0.66
    d.rectangle([sc(x0), sc(y0), sc(x0 + used_w), sc(y0 + h)], fill="#BFD3E8")
    text(d, (x0 + used_w / 2, y0 + h / 2), "Reserved 缓冲", 22, NAVY, True, "mm")

    # Xon / Xoff
    xon_x = x0 + w * 0.42
    xoff_x = x0 + w * 0.82
    for x, color in ((xon_x, TEAL), (xoff_x, RED)):
        y = y0 - 25
        while y < y0 + h + 35:
            d.line([sc(x), sc(y), sc(x), sc(min(y + 10, y0 + h + 35))], fill=color, width=sc(3))
            y += 18

    text_bg(d, (xon_x, y0 - 42), "占用降到 Xon", 16, TEAL, True, "ma")
    text_bg(d, (xoff_x, y0 - 42), "占用升到 Xoff", 16, RED, True, "ma")
    text_bg(d, (xon_x, y0 + h + 45), "Xon：停 Pause", 18, TEAL, True, "ma")
    text_bg(d, (xoff_x, y0 + h + 45), "Xoff：发 Pause", 18, RED, True, "ma")

    # Hysteresis bracket
    by = y0 + h + 20
    d.line([sc(xon_x), sc(by), sc(xoff_x), sc(by)], fill=GRAY, width=sc(1.4))
    d.polygon([(sc(xon_x), sc(by)), (sc(xon_x + 6), sc(by - 5)), (sc(xon_x + 6), sc(by + 5))], fill=GRAY)
    d.polygon([(sc(xoff_x), sc(by)), (sc(xoff_x - 6), sc(by - 5)), (sc(xoff_x - 6), sc(by + 5))], fill=GRAY)
    text_bg(d, ((xon_x + xoff_x) / 2, by - 14), "回差", 16, GRAY, True, "mb")

    # Headroom arrow
    arrow(d, 70, 165, 70, 235, ORANGE, 2.0, head=10)
    text(d, (88, 195), "单独预留\n不能全用到 Xoff", 14, ORANGE, False, "lm", "left", 1.3)

    # Bottom note
    text(d, (660, 442), "Xon < Xoff；lossless PG 的 reserved 至少覆盖 Xoff", 16, GRAY, False, "ma")

    out = os.path.join("assets", "fig_pfc_buffer.png")
    img.save(out, dpi=(300, 300))
    print("saved", out, img.size)


if __name__ == "__main__":
    architecture()
    pfc_buffer()
