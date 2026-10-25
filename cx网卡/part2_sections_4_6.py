
# -*- coding: utf-8 -*-
"""Sections 4-6."""
import os
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from docx_helpers import (
    NAVY, BLUE, TEAL, ORANGE, RED, GRAY, WHITE,
    LIGHT_BLUE, LIGHT_GRAY, LIGHT_GREEN, LIGHT_ORANGE, LIGHT_RED,
    BODY_FONT, HEAD_FONT,
    P, BULLETS, NUMBERED, H1, H2, H3, CAPTION, TABLE, CODE, CALLOUT, FIGURE,
)


def add_section_4(doc):
    H1(doc, "RoCEv2 拥塞控制：ECN 与 DCQCN", "4")
    P(doc, "RoCEv2 的拥塞控制不是交换机单独完成的。交换机负责“看见拥塞并标记”，接收端网卡负责“把标记变成 CNP”，发送端网卡负责“按 CNP 降速/恢复”。这三段合起来才是 DCQCN。")

    H2(doc, "ECN 的两个比特与三种角色", "4.1")
    P(doc, "ECN 是 IP 协议的扩展，用 Traffic Class 字段中的 2 bit 表示拥塞状态；NVIDIA 的这段实现针对 RoCEv2。它要求路径上所有节点（主机、路由器、交换机）都支持 ECN，否则标记无法端到端传递。[S4]")
    rows = [
        ("00", "Not-ECT", "不支持 ECN 的流量；拥塞时只能丢弃。"),
        ("01", "ECT(1)", "支持 ECN；可被交换机标记为 CE。"),
        ("10", "ECT(0)", "支持 ECN；可被交换机标记为 CE。"),
        ("11", "CE", "已遇到拥塞；接收端看到后生成 CNP。"),
    ]
    TABLE(doc, ["ECN 位", "名称", "含义"], rows, [2.4, 4.0, 9.8], font_size=8.6, first_col_bold=True)
    P(doc, "交换机在 Egress 队列上做标记：队列长度超过 Kmin 后，按概率把 ECT 包改成 CE；到 Kmax 时标记概率达到 Pmax。Cumulus 的默认 RoCE profile 把 Pmax 设为 100%，即在 Kmax 时所有 ECN-capable 包都被标记。标记本身不丢包，但如果拥塞继续，缓冲区最终仍会满，后续报文仍可能被丢弃。[S5][S12]")

    H2(doc, "DCQCN 的闭环", "4.2")
    NUMBERED(doc, [
        "**CP（交换机）**：监控 Egress 队列，按 Kmin/Kmax/Pmax 对经过的 RoCEv2 报文做 CE 标记。[S5]",
        "**NP（接收端网卡）**：收到 CE 标记的报文后，由硬件生成 CNP，按 QP 标识回送给发送端；不需要主机 CPU 参与。[S5]",
        "**RP（发送端网卡）**：收到 CNP 后更新 α，按 α 和 RPG_GD 做乘法降速；没有 CNP 时按定时器/字节计数器逐步恢复。[S5]",
        "**闭环稳定**：降速后队列下降 → 交换机停止标记 → CNP 减少 → RP 逐步升速；如果再次拥塞，循环重复。",
    ])
    P(doc, "注意 CNP 是“按流/QP”反馈的：一个 QP 拥塞，不会让同一网卡上的所有 QP 一起降速。这是 DCQCN 相对全局 pause 的关键优势，也是它必须和 PFC 分开理解的原因。[S5]")

    H2(doc, "拥塞点：交换机如何标记", "4.3")
    P(doc, "DCQCN 的拥塞点通常是交换机 Egress 队列。队列超过 Kmin 后，标记概率线性上升；到 Kmax 达到 Pmax。Kmin 太低会过早降速、吞吐受损；Kmin 太高会让缓冲先被填满，PFC 甚至丢包先发生。Kmax 与 Kmin 的间隔决定标记的“渐进程度”。[S5]")
    CALLOUT(doc, "单位陷阱", "Onyx 的 `show roce` 默认显示 `Min : 150 / Max : 1500`，单位是 KB（Onyx 命令文档明确 `minimum-absolute`/`maximum-absolute` 以 KB 计），即 150 KB–1.5 MB；Cumulus 的默认 RoCE profile 写的是 150000/1500000 字节，量级相同。两者数字不同，是因为显示单位不同，不是两套相距 1000 倍的阈值。配置前仍要确认 NOS、ASIC、TC 和单位，不能把 150 直接当字节。", "warn")
    P(doc, "NVIDIA 的 Onyx RoCE lossless 默认还把 CNP 放到 TC6 strict、RoCE 数据放 TC3 WRR 50%、其他流量放 TC0 WRR 50%。这是一套“让 CNP 先走”的默认调度，不是所有厂商都必须照搬的固定值。[S10][S11]")

    H2(doc, "通知点：CNP 如何回送", "4.4")
    P(doc, "NP 是接收端网卡。它看到 CE 标记后生成 CNP，CNP 里带有目标 QP，源/目的 IP 与数据流相反。CNP 默认使用 DSCP 48、PCP 6；NVIDIA 文档给的 `MIN_TIME_BETWEEN_CNPS` 默认是 4 µs，用来限制 CNP 的发送频率。[S5][S6]")
    BULLETS(doc, [
        "CNP 必须走低时延路径。Onyx 默认把它放 TC6 strict；如果 CNP 被排到数据后面，RP 的降速会晚一个队列周期。",
        "CNP 不应该被 PFC 暂停。NVIDIA 默认只对 RoCE priority 3 开 PFC，CNP 在 priority 6；把 CNP 放进 lossless priority 会引入不必要的反压风险。",
        "CNP 的 DSCP/PCP 必须与交换机信任模式和映射一致。DSCP 48 在默认映射里落到 SP6；如果你的 fabric 改过映射，需要同步修改 `CNP_DSCP`/`CNP_802P_PRIO`。",
    ])

    H2(doc, "反应点：α、降速与恢复", "4.5")
    P(doc, "RP 用 α 表示近期拥塞程度（0–1）。每个 `DCE_TCP_RTT` 周期更新一次：收到 CNP 时 α 向 1 靠近，没有 CNP 时 α 衰减。α 越大，单次降速越多。下面的公式按 NVIDIA 文档的参数语义整理；`g = DCE_TCP_G / 1024`。")
    CODE(doc, r"""
收到 CNP:     alpha <- (1 - g) * alpha + g
未收到 CNP:   alpha <- (1 - g) * alpha

降速:         CurrentRate <- CurrentRate * (1 - alpha / 2^RPG_GD)
恢复:         CurrentRate <- (CurrentRate + TargetRate) / 2
              TargetRate  <- TargetRate + AI   (Additive Increase)
              TargetRate  <- TargetRate + HAI  (Hyper Increase)
""", size=8.4)
    P(doc, "默认 `DCE_TCP_G=1019`（约 0.995）、`RPG_GD=11`。按公式直算，α=1 时单次降速比例约为 1/2048；这不是“一次 CNP 就砍一半”，而是依赖持续的 CNP 和 4 µs 的监控窗口小步快跑。把 `RPG_GD` 调小会让分母变小、单次降速更狠；调大则更温和。[S6]")
    rows = [
        ("Fast Recovery", "当前速率低于 TargetRate，且没有 CNP", "向 TargetRate 快速靠拢（通常取当前与目标的平均）"),
        ("Additive Increase (AI)", "定时器或字节计数器连续触发达到 `RPG_THRESHOLD`", "TargetRate 按 `RPG_AI_RATE` 增加，谨慎探测"),
        ("Hyper Increase (HAI)", "定时器和字节计数器都达到阈值，路径持续无拥塞", "TargetRate 按 `RPG_HAI_RATE` 增加，快速 reclaim 带宽"),
    ]
    TABLE(doc, ["阶段", "进入条件", "行为"], rows, [4.0, 6.4, 5.8], font_size=8.4, first_col_bold=True)
    P(doc, "`CLAMP_TGT_RATE` 控制连续 CNP 期间 TargetRate 是否每次都被拉低；默认关闭。它影响的是恢复速度，不是单次降速幅度。不要在没搞清恢复行为前同时改 `CLAMP_TGT_RATE` 和 `RPG_GD`。[S6]")

    H2(doc, "默认参数速览", "4.6")
    rows = [
        ("ROCE_CC_PRIO_MASK", "Enable（逐优先级）", "按优先级启用 DCQCN；255 表示 8 个优先级全开", "[S6][S15]"),
        ("DCE_TCP_G / dce_tcp_g", "1019", "α 更新权重（10 bit 定点）", "[S6]"),
        ("DCE_TCP_RTT / dce_tcp_rtt", "1 µs", "α 更新周期", "[S6]"),
        ("RPG_GD / rpg_gd", "11", "降速指数；越小越狠", "[S6]"),
        ("RATE_REDUCE_MONITOR_PERIOD", "4 µs", "CNP 观察窗口", "[S6]"),
        ("RPG_TIME_RESET", "300 µs", "升速定时器", "[S6]"),
        ("RPG_BYTE_RESET", "32767 × 64 B ≈ 2 MB", "升速字节计数器", "[S6]"),
        ("RPG_AI_RATE / RPG_HAI_RATE", "5 / 50 Mb/s", "AI / HAI 步长", "[S6]"),
        ("RPG_MIN_RATE", "1 Mb/s", "QP 最低速率", "[S6]"),
        ("CNP_DSCP / CNP_802P_PRIO", "48 / 6", "CNP 的 DSCP / PCP", "[S6]"),
        ("MIN_TIME_BETWEEN_CNPS", "4 µs", "CNP 最小间隔", "[S6]"),
    ]
    TABLE(doc, ["参数", "默认", "作用"], [r[:3] for r in rows], [6.2, 3.0, 6.8], font_size=8.2, first_col_bold=True)

    H2(doc, "DCQCN 做不到什么", "4.7")
    BULLETS(doc, [
        "**不能创造带宽**：持续超配、严重 incast、慢接收端，靠调 ECN 阈值解决不了。",
        "**不能替代 PFC**：如果业务要求零丢包，ECN 只能降低概率，最终仍需入口缓冲/PFC 兜底。",
        "**不能感知非 ECN 设备**：路径上有一个不标记 ECN 的瓶颈，DCQCN 就看不到它。[S4]",
        "**不能修复 CNP 丢失**：CNP 被丢、被 pause、被错误映射，RP 会误以为“路径不拥塞”。",
        "**不能跨 QP 公平**：DCQCN 按 QP 反馈；大量 QP 的公平性还取决于交换机队列和端点实现。",
    ])


def add_section_5(doc):
    H1(doc, "DCQCN 参数、默认值与调优", "5")
    P(doc, "这一章把“可以调什么”与“先调什么”分开。NVIDIA 的默认值是为通用场景选的，不是为你的 incast 模式选的；但默认值也是最安全的起点。除非有明确的计数器证据，否则不要一上来就改 α 或 RPG_GD。")

    H2(doc, "参数总表", "5.1")
    rows = [
        ("ROCE_CC_PRIO_MASK", "Enable", "按优先级启用 DCQCN。255 = 所有 8 个优先级；按 8 位掩码理解，priority 3 对应 8（bit3），写入前以设备 query 为准。", "写成 0 会关闭该优先级 CC；按端口命名时用 `_P1/_P2`。", "[S6][S15]"),
        ("DCE_TCP_G / dce_tcp_g", "1019", "α 的 EWMA 权重；10 bit 定点，1019/1024≈0.995。", "改变 α 的收敛速度；不要和 RPG_GD 同时调。", "[S6]"),
        ("DCE_TCP_RTT / dce_tcp_rtt", "1 µs", "α 更新周期。", "调大更平滑但反应慢；调小更敏感但可能抖动。", "[S6]"),
        ("INITIAL_ALPHA_VALUE", "1023", "第一次收到 CNP 时的 α 初值。", "调低会减弱首次降速；通常保持默认。", "[S6]"),
        ("RATE_TO_SET_ON_FIRST_CNP", "0", "首个 CNP 是否强制设定一个速率；0 表示不强制。", "非 0 会在首 CNP 直接跳到指定 Mb/s，风险高。", "[S6]"),
        ("RPG_MIN_DEC_FAC", "50%", "单次降速的最大比例。", "调低更温和；调高更激进。", "[S6]"),
        ("RPG_MIN_RATE", "1 Mb/s", "QP 最低速率。", "调高避免饿死但可能降不下来；调低可能长时间低吞吐。", "[S6]"),
        ("RPG_GD", "11", "降速公式的指数；越小降速越狠。", "优先保持默认；确需调整时每次只动 1。", "[S6]"),
        ("RATE_REDUCE_MONITOR_PERIOD", "4 µs", "两次降速之间的观察窗口。", "调大更平滑但反应慢；调小可能过度反应。", "[S6]"),
        ("CLAMP_TGT_RATE", "Disable", "控制连续 CNP 时 TargetRate 的更新方式。", "影响恢复速度；具体行为以本机参数说明为准。", "[S6]"),
        ("RPG_TIME_RESET", "300 µs", "升速定时器。", "调小恢复更快但更易再次拥塞；调大恢复慢。", "[S6]"),
        ("RPG_BYTE_RESET", "32767（64 B 单位，约 2 MB）", "升速字节计数器。", "调小恢复更快；调大对大流更保守。", "[S6]"),
        ("RPG_THRESHOLD", "1", "进入 AI/HAI 前需要的连续触发次数。", "调大更保守；默认 1 已很激进。", "[S6]"),
        ("RPG_AI_RATE", "5 Mb/s", "AI 阶段每次增加的 TargetRate。", "调大恢复快但可能过冲；调小恢复慢。", "[S6]"),
        ("RPG_HAI_RATE", "50 Mb/s", "HAI 阶段每次增加的 TargetRate。", "调大快速 reclaim 但易造成突发；调小更平滑。", "[S6]"),
        ("CNP_DSCP", "48", "CNP 的 IP DSCP。", "必须与交换机 trust/映射一致；默认映射到 SP6。", "[S6][S17]"),
        ("CNP_802P_PRIO", "6", "CNP 的 VLAN PCP。", "L2 trust 时使用；与 DSCP 同时配置可避免模式切换出错。", "[S6]"),
        ("MIN_TIME_BETWEEN_CNPS", "4 µs", "CNP 最小发送间隔。", "调大减少 CNP 开销但反应慢；调小更敏感但增加控制面压力。", "[S6]"),
    ]
    TABLE(doc, ["参数", "默认", "作用", "调整影响 / 风险"], [r[:4] for r in rows],
          [5.8, 2.2, 4.6, 3.4], font_size=7.6, first_col_bold=True)
    P(doc, "默认值来自 DOCA 3.5 文档，适用 ConnectX-4 及以后；不同固件/驱动可能显示不同默认值。调参前先用 `cat /sys/class/net/<if>/ecn/roce_rp/params/<param>` 或 `mlxconfig query` 读取本机实际值。[S6]")

    H2(doc, "如何读写 ECN 参数", "5.2")
    P(doc, "MLNX_OFED 把 RoCEv2 ECN 的 RP/NP 配置放在 sysfs 下，按设备、端口、优先级组织。启用某个优先级后，才能读写该优先级的参数。[S4]")
    CODE(doc, r"""
IF=ens1f0np0
P=3

# 1) 启用该优先级的 NP / RP（两端都建议启用，因为两端都可能收发）
echo 1 > /sys/class/net/$IF/ecn/roce_np/enable/$P
echo 1 > /sys/class/net/$IF/ecn/roce_rp/enable/$P

# 2) 确认启用状态
cat /sys/class/net/$IF/ecn/roce_np/enable/$P
cat /sys/class/net/$IF/ecn/roce_rp/enable/$P

# 3) 读取参数（不要盲目写）
cat /sys/class/net/$IF/ecn/roce_rp/params/rpg_gd
cat /sys/class/net/$IF/ecn/roce_rp/params/rpg_ai_rate
cat /sys/class/net/$IF/ecn/roce_np/params/cnp_dscp

# 4) 仅在明确需要时写入；写前记录原值
# echo 11 > /sys/class/net/$IF/ecn/roce_rp/params/rpg_gd
""", size=8.2)
    CALLOUT(doc, "sysfs 不是持久化配置", "ECN 的 enable 和 params 通常在驱动重载/重启后回到默认；必须纳入启动脚本或配置管理。写入前先备份原值，写入后用 `cat` 复核。", "warn")

    H2(doc, "调优顺序", "5.3")
    NUMBERED(doc, [
        "**先看交换机**：确认 ECN 在正确的 TC 上启用、Kmin/Kmax/Pmax 合理、CNP 走 strict。多数“DCQCN 不工作”其实是交换机没标记或 CNP 没被优先转发。",
        "**再看 NP**：确认接收端 ECN enable、CNP 生成计数在增长、CNP DSCP/PCP 与交换机映射一致。",
        "**再看 RP**：确认发送端 ECN enable、`ROCE_CC_PRIO_MASK` 覆盖了 RoCE priority、CNP 能被收到。",
        "**最后才动 α/速率参数**：先调交换机阈值，再调 RP 的 AI/HAI 或 RPG_GD；一次只动一个变量。",
        "**用 incast 验证**：单流通常不足以触发持续 ECN；至少 4:1、8:1 的多打一，才能稳定看到 CNP 和降速。",
        "**保留基线**：记录调参前后的吞吐、P99 时延、ECN 标记率、PFC pause、`out_of_sequence`。",
    ])

    H2(doc, "症状与参数方向", "5.4")
    rows = [
        ("吞吐低，ECN 标记率很高", "Kmin 太低 / Pmax 太高 / RP 降速过狠", "先抬高 Kmin 或降低 Pmax；再看 `RPG_GD` 是否过小。", "不要直接关 ECN，否则拥塞会转成丢包/PFC。"),
        ("吞吐低，ECN 标记率很低", "Kmin 太高 / 交换机未标记 / CNP 未生成", "查交换机 TC、ECN 开关、NP enable；不要先调 RP。", "标记率低但 PFC 高，说明 PFC 在替 ECN 干活。"),
        ("PFC pause 频繁，ECN 标记少", "PFC Xoff 太低 / ECN Kmin 太高 / 微突发", "先确认是否微突发；再评估抬高 Xoff、降低 Kmin。", "不要把 Xoff 无限抬高，会挤占 headroom。"),
        ("PFC pause 不多，但仍有丢包", "headroom 不足 / cable length 错 / Xoff 太高", "核对 cable length、MTU、速率、headroom；看 `no-buffer-discard`。", "这是缓冲问题，不是 CC 参数问题。"),
        ("CNP 计数不增长", "NP 未启用 / CNP 被丢 / DSCP 映射错", "查 NP enable、CNP 队列、交换机 SP6 映射。", "CNP 被 pause 也会表现为“不增长”。"),
        ("降速后恢复很慢", "AI/HAI 太小 / RPG_TIME_RESET 太大 / CLAMP 过保守", "小幅提高 AI/HAI 或降低 TIME_RESET；一次只改一个。", "恢复太快会再次拥塞，形成振荡。"),
        ("时延抖动大", "ECN 阈值过晚 / PFC 频繁 / 缓冲占用高", "看 buffer max usage、PFC pause duration、CNP 延迟。", "先定位是缓冲还是 CC，不要盲调 α。"),
    ]
    TABLE(doc, ["症状", "可能原因", "优先动作", "注意"], rows, [4.2, 4.6, 4.8, 2.4], font_size=8.0, first_col_bold=True)

    H2(doc, "不要这样调", "5.5")
    BULLETS(doc, [
        "不要同时改 `DCE_TCP_G`、`RPG_GD`、`RPG_AI_RATE`、`RPG_HAI_RATE`；出了问题无法归因。",
        "不要把 `RPG_MIN_RATE` 设得很低来“保护吞吐”；它可能让拥塞流长期占着少量带宽，恢复更慢。",
        "不要把 `RPG_HAI_RATE` 设得很大来“快速恢复”；突发会再次打满队列，形成锯齿。",
        "不要用 `RATE_TO_SET_ON_FIRST_CNP` 做“快速止血”；它绕过 α 的渐进降速，容易过冲。",
        "不要在生产环境用 `mlxconfig reset` 回滚；它会重置所有固件参数。用备份的逐项值恢复。",
    ])

    H2(doc, "A/B 测试方法", "5.6")
    P(doc, "每次只改变一个参数，保持拓扑、MTU、线缆、应用并发、消息大小不变。每组至少跑 3 次，取中位数；同时记录交换机侧 ECN 标记率、PFC pause、buffer max usage，以及主机侧吞吐、P99 时延、`out_of_sequence`、重传。只有“吞吐/时延改善，且 PFC/丢包没有恶化”才算有效。")
    CODE(doc, r"""
# 记录一次基线（示例）
ethtool -S $IF > baseline_$(date +%F_%H%M).txt
mlnx_qos -i $IF > baseline_qos_$(date +%F_%H%M).txt
cat /sys/class/net/$IF/ecn/roce_rp/params/rpg_gd >> baseline_ecn.txt

# 变更后至少观察 10 分钟稳定态，再做 incast
# 不要只看单流 ib_write_bw 的峰值
""", size=8.0)


def add_section_6(doc):
    H1(doc, "PFC 流控：原理、缓冲与阈值", "6")
    P(doc, "PFC 是 IEEE 802.1Qbb 的逐优先级暂停机制。它在一条物理链路上创建 8 个虚拟链路，可以单独暂停/恢复某个优先级，从而让 RoCE 走 lossless，而普通 TCP 继续走 best-effort。[S3][S8]")

    H2(doc, "PFC 的基本行为", "6.1")
    BULLETS(doc, [
        "**逐优先级**：PFC 只暂停指定 priority，其他 priority 继续发送；这比全局 pause 精细。[S8]",
        "**逐跳**：Pause 是链路本地行为；上游交换机/网卡收到后停止向该链路发送，不携带端到端语义。[S8][S12]",
        "**默认关闭**：NVIDIA Onyx 默认在所有端口、所有优先级关闭 PFC；必须显式开启。[S8]",
        "**物理口限制**：Onyx 明确 PFC 只支持物理端口，不支持隧道或 vSwitch 共享的逻辑接口。[S8]",
        "**Xoff/Xon**：接收侧缓冲达到 Xoff 发 Pause；降到 Xon 发 Xon（恢复）。[S8][S9]",
        "**不是零丢包**：headroom 不足、配置错误、PFC 风暴时仍然会丢包。[S10]",
    ])

    H2(doc, "缓冲模型：PG、TC 与 headroom", "6.2")
    P(doc, "交换机的入口和出口是两套缓冲。入口按 PG（Priority Group）管理，出口按 TC（Traffic Class）管理；PFC 的 Xoff/Xon 作用在入口 PG 上，ECN 的 Kmin/Kmax 作用在出口队列上。把两者混为一谈，是很多“PFC 配了但没用”的根源。[S9]")
    FIGURE(doc, os.path.join("assets", "fig_pfc_buffer.png"), 16.0)
    CAPTION(doc, "图 2  PFC 缓冲、Xoff/Xon 与 headroom 的概念关系（根据 [S8][S9][S12] 绘制，非按比例）")
    rows = [
        ("Ingress PG", "入口优先级组；PFC 的 reserved/headroom/Xoff/Xon 在这里。", "按 priority 分组，丢包前最后一道缓冲。"),
        ("Egress TC", "出口流量类；ECN 的 Kmin/Kmax 在这里。", "按 TC 排队，决定标记/调度。"),
        ("Reserved", "给某个 PG/TC 的保底缓冲，不被其他区域共享。", "Onyx 要求 lossless PG 的 reserved 至少覆盖 Xoff。[S9]"),
        ("Shared", "按 alpha/静态阈值动态共享的缓冲。", "可吸收突发，但不能保证不被别的流量占用。"),
        ("Headroom", "Xoff 之后仍在链路上的报文所需的额外入口缓冲。", "不足 → PFC 还没来得及生效就丢包。[S9]"),
    ]
    TABLE(doc, ["概念", "位置/作用", "要点"], rows, [3.4, 7.0, 5.6], font_size=8.4, first_col_bold=True)

    H2(doc, "Headroom 估算", "6.3")
    P(doc, "NVIDIA 文档明确指出：PFC 的 Xoff/Xon 阈值取决于带宽、链路时延、MTU 和分配到的缓冲大小；如果 headroom 不足，交换机会在 PFC 生效前丢包。Cumulus 文档还指出，PFC 缓冲计算是 IEEE 802.1Q-2012 定义的复杂问题，cable length 配错会导致“缓冲浪费/过早拥塞”或“PFC 还没触发就丢包”。[S9][S12]")
    P(doc, "下面是一个只用于量级校验的工程公式，不是 NVIDIA 的交换机计算公式：")
    CODE(doc, r"""
H_req ≈ 2 × C × T_prop + C × T_react + 2 × MTU

C       = 线速（byte/s），100GbE = 12.5e9 B/s
T_prop  = 线缆长度 / 传播速度，光纤/铜缆约 2e8 m/s
T_react = Pause 帧序列化 + PHY/MAC + 发送端响应（建议实测或取保守值）
2×MTU  = 报文粒度/量化余量

示例（仅说明量级）：
100GbE、100 m、MTU 4200 B、T_react≈1 µs
2×C×T_prop = 12,500 B
C×T_react  = 12,500 B
2×MTU      = 8,400 B
合计约 33.4 KB；加 30% 余量约 43 KB
""", size=8.1)
    CALLOUT(doc, "不要用这个公式替代厂商计算", "真实交换机按 cell、端口、PG、共享池和 ASIC 内部延迟计算 headroom；上面的公式只用来判断“自动计算的 headroom 是否在同一量级”。如果交换机自动计算可用，优先使用自动计算；Cumulus 文档也建议不要随意改默认阈值，让 NOS 动态配置。[S12]", "warn")

    H2(doc, "Xoff/Xon 设计规则", "6.4")
    BULLETS(doc, [
        "**reserved ≥ Xoff**：Onyx 明确要求 lossless PG 的 reserved 至少等于 Xoff，否则水线没有足够的实体缓冲承接。[S9]",
        "**Xon < Xoff，并留回差**：两者太近会频繁 pause/unpause，形成抖动；太远会长时间不恢复，吞吐受损。",
        "**Xoff 不能吃掉 headroom**：headroom 是 Xoff 之后的在途报文空间，不能把 reserved 全部用到 Xoff。",
        "**cable length 要填真实值**：填短了会低估在途报文，导致丢包；填长了会浪费缓冲、过早拥塞。[S12]",
        "**MTU 要一致**：路径 MTU 变大，headroom 需求也变大；不要让 RoCE 流量在途中被分片。",
        "**先自动、后手动**：能自动计算就不要手调；必须手调时，用 `no-buffer-discard`、`buffer max usage`、PFC pause duration 做闭环。",
    ])

    H2(doc, "PFC watchdog 与 PFC storm", "6.5")
    P(doc, "PFC 的副作用是反压会沿路径传播。如果某个接收端长期不 drain，缓冲区会一层层填满，Pause 帧会扩散成 PFC storm，严重时大面积停传。NVIDIA 用两类机制止损：交换机侧的 PFC watchdog，以及主机侧的 PFC stall prevention。[S8][S12][S3]")
    rows = [
        ("交换机 PFC watchdog", "检测某个 TC 持续处于 pause 状态；超过 polling/robustness 阈值后，停止处理该 TC 的 Pause，并丢弃新到该队列的报文，直到风暴解除。", "Cumulus 默认 polling 100 ms、robustness 3；Onyx 用 `pfc-wd` 开启。[S12][S8]"),
        ("主机 PFC stall prevention", "本端持续发送 Pause 超过超时后，停止发送 Pause，避免把整条链路拖死。", "默认 8 s；`auto` 模式为 100 ms。[S3]"),
        ("主机计数器", "`tx_pause_storm_warning_events`、`tx_pause_storm_error_events`。", "warning 是预警；error 表示已超过超时并采取动作。[S3]"),
        ("PFC 逐优先级计数器", "`prioN_tx_pause`、`prioN_rx_pause`、`prioN_tx_pause_duration`、`prioN_rx_pause_duration`。", "tx=本端发出的 Pause；rx=本端收到的 Pause。[S3]"),
    ]
    TABLE(doc, ["机制", "行为", "关键参数/计数器"], rows, [4.2, 8.2, 3.6], font_size=8.2, first_col_bold=True)
    CALLOUT(doc, "8 秒默认值偏长", "主机 stall prevention 默认 8 s，意味着最坏情况下 Pause 会持续很久；`auto` 把它缩短到 100 ms。是否切到 `auto` 要评估误触发风险：太短可能在正常反压时误停 Pause，导致丢包。建议先在实验环境验证，再决定是否作为生产默认。[S3]", "warn")

    H2(doc, "PFC 的代价", "6.6")
    BULLETS(doc, [
        "**缓冲成本**：每个 lossless priority 都要预留 headroom/reserved；端口越多、速率越高、线缆越长，成本越大。",
        "**HOL**：PFC 只隔离 priority，不隔离同一 priority 内的流；一条慢流仍可能挡住同 priority 的其他流。",
        "**风暴风险**：一个坏接收端可以把反压传播到整片 fabric；必须配合 watchdog 和监控。",
        "**配置复杂度**：PFC、trust、DSCP/PCP、buffer、cable length、DCBX 必须端到端一致；任何一处错配都可能“看似开启、实际无效”。",
        "**不是所有场景都需要**：能容忍重传的 L3/多租户业务，lossy + ECN 往往更简单、更稳。",
    ])

    H2(doc, "什么时候用 semi-lossless", "6.7")
    P(doc, "Onyx 提供 semi-lossless 模式：主机到 ToR 的方向使用 PFC 吸收微突发，fabric 内部保持 lossy，不把 pause 传播到整网。它适合“边缘微突发很严重，但全网 lossless 成本和风险太高”的场景。[S10]")
    P(doc, "semi-lossless 不是“半吊子 lossless”：它不保证端到端零丢包，只保证边缘能吸收瞬时突发。业务如果要求严格零丢包，仍然要设计完整的 lossless 域。")
