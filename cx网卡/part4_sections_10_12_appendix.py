# -*- coding: utf-8 -*-
"""Sections 10-12, appendices, and the document entry point."""
import os
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.section import WD_SECTION

from docx_helpers import (
    NAVY, BLUE, TEAL, ORANGE, RED, GRAY, WHITE, BORDER,
    LIGHT_BLUE, LIGHT_GRAY, LIGHT_GREEN, LIGHT_ORANGE, LIGHT_RED,
    BODY_FONT, HEAD_FONT,
    P, BULLETS, NUMBERED, H1, H2, H3, CAPTION, TABLE, CODE, CALLOUT, FIGURE,
    set_run_font, set_paragraph_format, add_rich_text, add_hyperlink,
    set_cell_background, set_cell_margins, set_cell_width,
    set_table_borders, set_repeat_table_header, set_row_cant_split,
    add_header_footer, start_page_numbering, setup_styles,
)
from common import DOC_TITLE, DOC_SUBTITLE, DOC_VERSION, DOC_DATE, OUT_DOCX, SOURCES
from part1_front_sections_1_3 import add_cover, add_front_matter, add_section_1, add_section_2, add_section_3
from part2_sections_4_6 import add_section_4, add_section_5, add_section_6
from part3_sections_7_9 import add_section_7, add_section_8, add_section_9


def add_body_start(doc):
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(1.9)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)
    add_header_footer(sec, DOC_TITLE)
    start_page_numbering(sec, 1)


def add_section_10(doc):
    H1(doc, "运维监控、故障排查与应急", "10")
    P(doc, "PFC/ECN 的故障往往不是“完全不通”，而是“吞吐掉一半”“时延尖刺”“偶尔重传”。这类问题必须靠计数器定位，不能靠猜。下面给出最小监控集、排障矩阵和三个应急 runbook。")

    H2(doc, "最小监控集", "10.1")
    rows = [
        ("PFC pause 速率", "`prio3_tx_pause`、`prio3_rx_pause` 的增量", "相对基线持续升高", "> 基线 5 倍或持续 10 分钟", "查缓冲/ECN/接收端 drain"),
        ("PFC 风暴", "`tx_pause_storm_warning_events`、`tx_pause_storm_error_events`", "warning > 0", "error > 0", "立即止损，见 10.4"),
        ("丢失", "switch `no-buffer-discard`、`out_of_buffer`", "> 0", "持续增长", "lossless 已破，查 headroom/cable"),
        ("ECN 标记率", "ECN marked / RoCE TC packets", "> 30% 持续", "> 80% 持续", "ECN 过激或拥塞严重"),
        ("CNP", "NP 生成计数、RP 处理计数", "CNP 不增长", "ECN 高但 CNP 低", "查 NP/CNP 队列/映射"),
        ("缓冲", "PG/TC max usage", "> 70% 分配", "> 90% 或接近上限", "扩容/调 pool/降超配"),
        ("重传/乱序", "`out_of_sequence` 等 RoCE 重传/乱序计数器（名称以实际 `ls` 为准）", "相对基线升高", "持续升高", "查丢包/链路/MTU"),
        ("链路", "FEC/BER、CRC、link down", "任何新增", "持续", "换线/换模块/查光功率"),
    ]
    rows4 = [(r[0], r[1], f"预警：{r[2]}\n严重：{r[3]}", r[4]) for r in rows]
    TABLE(doc, ["指标", "来源", "阈值（预警 / 严重）", "动作"], rows4, [3.0, 6.2, 4.0, 2.8], font_size=8.0, first_col_bold=True)
    P(doc, "阈值是建议起点，不是通用标准；请按业务基线调整。关键是“趋势 + 组合”：单独一个 PFC 计数高不一定有问题，PFC 高 + ECN 低 + 丢包增长才是危险组合。")

    H2(doc, "排障矩阵", "10.2")
    rows = [
        ("RoCE 能通但吞吐只有一半", "ECN 过激、PFC 频繁、MTU/FEC、PCIe 瓶颈", "看 ECN 标记率、PFC pause、`ethtool -S` 错误、`mlxlink`", "先分离是网络还是主机；不要先调 CC 参数"),
        ("时延周期性尖刺", "PFC headroom 不足、buffer 满、CNP 延迟", "看 buffer max usage、pause duration、CNP 计数", "先保证不丢包，再谈降时延"),
        ("PFC 配了但计数为 0", "priority 不匹配、PFC 未真正 enable、DCBX 覆盖", "`mlnx_qos -i`、交换机 oper 状态、抓包看 PFC", "先让 PFC 真正生效，再调阈值"),
        ("PFC 计数高但无丢包", "ECN 阈值太高、PFC 在替 ECN 干活", "看 ECN 标记率与 CNP", "降低 ECN Kmin / 提高 Pmax，让 ECN 先动作"),
        ("no-buffer-discard 增长", "headroom 不足、cable length 错、Xoff 太高", "看 buffer max usage、cable_len、MTU", "按第 6 章重算，不要只加 Xoff"),
        ("ECN 标记高但吞吐不降", "RP 未 enable、CNP 没回来、priority mask 错", "看 RP enable、CNP 计数、`ROCE_CC_PRIO_MASK`", "先修 CNP 路径，再调阈值"),
        ("CNP 计数低", "NP 未 enable、CNP 被丢/被 pause、DSCP 映射错", "看 NP enable、TC6 strict、DSCP 48 映射", "CNP 必须独立且最高优先"),
        ("重启后配置丢失", "PFC/trust/ECN sysfs 非持久", "对比重启前后 `mlnx_qos`/enable", "纳入 systemd/Ansible/Network Operator"),
        ("换固件后行为变化", "默认值/参数名变化", "对比 `mlxconfig query`、release notes", "按新固件重建基线"),
        ("PFC 风暴/大面积停传", "接收端不 drain、缓冲连锁占满、watchdog 未开", "看 storm 计数、watchdog 状态、buffer", "按 10.4 止损"),
    ]
    TABLE(doc, ["症状", "可能原因", "先看什么", "处理原则"], rows, [4.2, 5.0, 4.2, 2.6], font_size=7.9, first_col_bold=True)

    H2(doc, "Runbook 1：PFC pause 持续升高", "10.3")
    NUMBERED(doc, [
        "确认范围：是单端口、单 priority，还是多端口/多 priority？先看 `prio3_tx_pause` 和交换机 PFC 计数。",
        "判断方向：`tx_pause` 高是本端接收侧拥塞；`rx_pause` 高是本端被对端反压。不要把方向搞反。",
        "查接收端 drain：应用是否停止读取、QP 是否 hung、CPU/内存/GPU 是否瓶颈。",
        "查缓冲：`buffer max usage` 是否接近分配值；`no-buffer-discard` 是否增长。",
        "查 ECN：如果 ECN 标记很低，说明 PFC 在替 ECN 干活；先调 ECN 阈值，让发送端降速。",
        "查线缆/MTU：cable length 是否准确、MTU 是否一致、是否有 FEC/CRC 错误。",
        "临时缓解：降低非关键流量、限制 incast 源、扩大 lossless pool；不要盲目把 Xoff 调高。",
        "如果出现 storm 计数，转 Runbook 3。",
    ])

    H2(doc, "Runbook 2：ECN 标记了但吞吐不恢复", "10.4")
    NUMBERED(doc, [
        "确认交换机 ECN 标记在正确的 TC（RoCE TC3），不是普通 TC0。",
        "确认 NP 收到 CE 并生成 CNP：看 NP enable、CNP 计数、CNP DSCP/PCP。",
        "确认 CNP 没被丢/被 pause：CNP 应走 strict TC6；检查 PFC 是否误开在 priority 6。",
        "确认 RP 收到 CNP：看 RP enable、`ROCE_CC_PRIO_MASK` 是否覆盖 priority 3、QP 是否在该 priority。",
        "确认降速不是过激：`RPG_GD` 是否被改小、`RPG_AI_RATE`/`RPG_HAI_RATE` 是否过小、`RPG_MIN_RATE` 是否太低。",
        "确认恢复路径：CNP 停止后，AI/HAI 是否能让速率回来；如果回不来，查 `CLAMP_TGT_RATE`、`RPG_TIME_RESET`。",
        "如果 CNP 路径正常但吞吐仍低，查主机/应用瓶颈（PCIe、NUMA、QP 数、消息大小）。",
    ])

    H2(doc, "Runbook 3：PFC 风暴/大面积停传", "10.5")
    CALLOUT(doc, "止损优先于根因", "PFC 风暴会沿路径扩散，等待根因分析可能让整片 fabric 停摆。先隔离/止损，再保留现场（计数器、日志、抓包）。", "risk")
    NUMBERED(doc, [
        "确认 storm：交换机 PFC watchdog 状态、`tx_pause_storm_error_events`、多端口 PFC pause 同时升高。",
        "隔离：在维护窗口内关闭问题端口/priority 的 PFC，或把该端口从 pool 中摘除；记录操作时间。",
        "保护：确认交换机 PFC watchdog 已开启；如果没有，按厂商命令开启（Onyx `pfc-wd`，Cumulus `qos pfc-watchdog`）。",
        "查接收端：应用是否 hang、QP 是否没有 post receive、GPU/存储是否停止 drain。",
        "查环路/错配：是否有 PFC 配置成环、priority 映射错、两个 lossless pool 互相反压。",
        "恢复：先恢复接收端 drain，再逐步恢复 PFC；不要一次性全网重启。",
        "复盘：补 headroom/ECN 调优、加 storm 告警、把 watchdog 纳入基线。",
    ])

    H2(doc, "变更管理", "10.6")
    BULLETS(doc, [
        "变更前：记录基线、确认回滚、通知业务、准备维护窗口；PFC/ECN 变更可能造成瞬时丢包。",
        "变更中：一次只改一个平面；每步后用最小命令验证（PFC 状态、ECN enable、CNP 计数）。",
        "变更后：至少观察 24 小时；看 PFC/ECN/丢包/时延趋势，不只看峰值吞吐。",
        "文档：把“为什么改、改了什么、验证结果、回滚命令”写进变更记录。",
    ])

    H2(doc, "容量与扩容", "10.7")
    P(doc, "PFC/ECN 调优不能替代容量规划。出现以下信号时，优先考虑扩容/改造，而不是继续调参数：")
    BULLETS(doc, [
        "ECN 标记率长期 > 80%，且降速后吞吐仍达不到 SLO。",
        "PFC pause 长期占空比高，增加缓冲也只是把问题推迟。",
        "incast 规模持续增长，单靠端点 CC 无法收敛。",
        "`no-buffer-discard` 在扩容前持续增长，说明 lossless 已经不可维持。",
    ])


def add_section_11(doc):
    H1(doc, "风险、限制与回滚", "11")
    P(doc, "这一章是给变更评审看的。PFC/ECN 不是“开了就完事”的特性；它们会改变拥塞传播方式，必须带着风险和回滚方案上线。")

    H2(doc, "风险登记", "11.1")
    rows = [
        ("PFC 风暴", "高", "接收端不 drain、缓冲连锁占满、watchdog 未开", "开 watchdog、监控 storm 计数、隔离 lossless 域"),
        ("优先级错配", "高", "应用/PFC/ECN/交换机映射不一致", "用一致性矩阵逐层核对；抓包验证"),
        ("headroom 不足", "高", "cable length/MTU/速率错配", "按最坏情况计算；用 `no-buffer-discard` 验证"),
        ("CNP 被丢/被 pause", "高", "CNP 与数据同 TC、DSCP 映射错", "CNP strict TC6；不要对 CNP priority 开 PFC"),
        ("ECN 调参过激", "中", "Kmin 太低、RPG_GD 太小、AI/HAI 太小", "一次只改一个；incast 验证"),
        ("运行时配置丢失", "中", "PFC/trust/ECN 非持久", "systemd/Ansible/Network Operator；重启验收"),
        ("固件/驱动差异", "中", "默认值、参数名、特性集合变化", "升级前查 release notes；升级后重建基线"),
        ("变更中断", "高", "RoCE 模式切换、mlxconfig 重启、PFC 关闭", "维护窗口、逐台滚动、回滚预案"),
    ]
    TABLE(doc, ["风险", "等级", "触发条件", "缓解"], rows, [3.4, 1.6, 5.8, 5.2], font_size=8.1, first_col_bold=True)

    H2(doc, "本文的限制", "11.2")
    BULLETS(doc, [
        "本文基于公开文档整理，未在读者的具体硬件/固件/业务上做实测；性能数字和阈值必须按现场基线调整。",
        "NVIDIA 文档会随版本变化；同一参数在不同固件上可能名称/默认值不同。",
        "Onyx 与 Cumulus 的默认值只是示例，不代表所有 NVIDIA 交换机/所有 NOS 版本。",
        "PFC 的 headroom 公式是工程校验公式，不是交换 ASIC 的精确计算公式；不能替代厂商工具。",
        "本文不覆盖 InfiniBand 的 credit/IB CC、Windows/WinOF-2、非 NVIDIA 交换机的私有实现。",
        "本文不构成性能承诺；PFC/ECN 不能解决带宽不足、应用设计缺陷、慢接收端等根本问题。",
    ])

    H2(doc, "回滚方案", "11.3")
    rows = [
        ("关闭 PFC", "`mlnx_qos -i $IF --pfc 0,0,0,0,0,0,0,0`", "可能立刻丢包；仅维护窗口"),
        ("关闭 ECN", "`echo 0 > .../ecn/roce_rp/enable/$P`、NP 同理", "DCQCN 停止；拥塞可能转成丢包/PFC"),
        ("恢复 PFC 配置", "按备份的 `mlnx_qos` 输出重放", "逐台执行；验证 oper 状态"),
        ("恢复固件参数", "按备份逐项 `mlxconfig set`，不要 `reset`", "需要重启；可能中断"),
        ("恢复交换机", "恢复配置 checkpoint / 重新应用旧 profile", "可能 toggle 接口"),
        ("恢复应用 ToS", "回退应用/中间件配置", "按应用灰度"),
    ]
    TABLE(doc, ["变更", "回滚动作", "影响"], rows, [3.4, 7.2, 5.6], font_size=8.2, first_col_bold=True)
    CODE(doc, r"""
# 最小回滚示例（先确认变量）
mlnx_qos -i $IF --pfc 0,0,0,0,0,0,0,0
echo 0 > /sys/class/net/$IF/ecn/roce_rp/enable/3
echo 0 > /sys/class/net/$IF/ecn/roce_np/enable/3

# 固件参数：用变更前备份的逐项值恢复，不要直接 reset
# mlxconfig -d $DEV -y set ROCE_CC_PRIO_MASK=<old> CNP_DSCP=<old> CNP_802P_PRIO=<old>
# reboot
""", size=8.0)
    CALLOUT(doc, "不要用 reset 做回滚", "`mlxconfig reset` 会把所有固件参数恢复默认，包括 SR-IOV、链路类型、启动项等；在生产环境这是高风险操作。正确做法是变更前备份 `mlxconfig query`，回滚时逐项恢复。[S14]", "risk")

    H2(doc, "停止条件", "11.4")
    P(doc, "出现以下任一情况，停止变更并回滚，不要继续“再调一个参数试试”：")
    BULLETS(doc, [
        "lossless priority 出现持续 `no-buffer-discard`。",
        "PFC storm 计数增长，或交换机出现大面积 pause。",
        "业务吞吐/P99 超过 SLO，且 10 分钟内无法定位。",
        "CNP 计数异常下降，ECN 标记高但发送端不降速。",
        "重启后关键配置未恢复，且无法在窗口内修复。",
    ])


def add_section_12(doc):
    H1(doc, "结论与检查清单", "12")
    P(doc, "ConnectX-6 的 RoCEv2 稳定性，不取决于某一个“神奇参数”，而取决于四件事：分类正确、PFC 域正确、ECN/CNP 闭环正确、缓冲与运维正确。把这四件事做成可验证的基线，比追求一套“最优参数”更重要。")

    H2(doc, "五条结论", "12.1")
    NUMBERED(doc, [
        "**PFC 是逐跳流控，DCQCN 是端到端拥塞控制**；两者互补，不能互相替代。[S3][S5][S8]",
        "**Lossless 需要 PFC + ECN 一起设计**；只开 PFC 会把拥塞变成反压，只开 ECN 在严重 incast 下仍可能丢包。[S10][S13]",
        "**默认值是最好的起点**：RoCE priority 3 / DSCP 26、CNP 48/6、ECN 150 KB–1.5 MB、DCQCN 默认参数；先基线，再调优。[S6][S10][S12][S13]",
        "**PFC 的成败在 headroom、cable length、Xoff/Xon、watchdog**；这些比“把 Xoff 调大”更重要。[S8][S9][S12]",
        "**运行时配置不是持久的**；PFC/trust/ECN 要纳入启动项，固件参数用 mlxconfig 并重启。[S14][S15]",
    ])

    H2(doc, "上线前检查清单", "12.2")
    checklist = [
        "已确认端口是 Ethernet，VPI 卡没有停留在 IB 模式。",
        "已记录固件/驱动/交换机 NOS 版本与 `mlxconfig query` 基线。",
        "已确定 lossless/lossy/semi-lossless 模式，并得到业务确认。",
        "RoCE、CNP、普通流量使用不同 priority/TC；CNP 走 strict。",
        "应用/QP 已设置正确的 ToS/DSCP；不是“默认 priority 0”。",
        "主机 trust 与 fabric 的 L2/L3 方案一致。",
        "PFC 只开在 RoCE priority；交换机与主机两端一致。",
        "ECN 在正确的 TC 启用；Kmin/Kmax/Pmax 已按平台单位确认。",
        "CNP 的 DSCP/PCP 与交换机映射一致；CNP 不会被 PFC 暂停。",
        "headroom/Xoff/Xon/cable length/MTU 按最坏情况核对。",
        "PFC watchdog 与主机 stall prevention 已评估并配置。",
        "已用 4:1/8:1 incast 验证，不只看单流。",
        "`no-buffer-discard`、`tx_pause_storm_*`、`out_of_sequence` 已纳入监控。",
        "运行时配置已纳入 systemd/Ansible/Network Operator，并做过重启测试。",
        "回滚方案已演练；没有用 `mlxconfig reset` 作为回滚手段。",
    ]
    for item in checklist:
        p = doc.add_paragraph()
        set_paragraph_format(p, before=1, after=2, line=1.25, left_indent=0.55)
        p.paragraph_format.first_line_indent = Cm(-0.45)
        r = p.add_run("☐  ")
        set_run_font(r, BODY_FONT, 10.5, False, BLUE)
        add_rich_text(p, item, 10.0, NAVY)

    H2(doc, "下一步", "12.3")
    BULLETS(doc, [
        "用第 9 章的模板做一次完整基线，不要直接上生产调参。",
        "把第 10 章的指标接入现有监控；没有监控就不要开 PFC。",
        "把第 11 章的风险登记和回滚方案交给变更评审。",
        "固件/驱动/交换机 NOS 升级后，重新核对本文的默认值与命令。",
    ])


def add_appendix_a(doc):
    H1(doc, "附录 A  命令速查", "A")
    P(doc, "以下命令用于快速复制；执行前先替换 `$IF`、`$DEV`、`$P`。不同版本参数名可能不同，以 `--help`/`query` 为准。")

    H2(doc, "A.1 主机侧")
    CODE(doc, r"""
# 盘点
lspci -d 15b3: -nn
ethtool -i $IF
ofed_info -s
mst start && mst status -v

# 备份
mlxconfig -d $DEV query > mlxconfig.before.txt
mlnx_qos -i $IF > mlnx_qos.before.txt
ethtool -S $IF > ethtool.before.txt

# PFC / trust / cable length
mlnx_qos -i $IF --dcbx=os
mlnx_qos -i $IF --trust=dscp
mlnx_qos -i $IF --pfc 0,0,0,1,0,0,0,0
mlnx_qos -i $IF --cable_len=100
mlnx_qos -i $IF --dscp2prio set,26,3
mlnx_qos -i $IF --dscp2prio set,48,6

# ECN
echo 1 > /sys/class/net/$IF/ecn/roce_np/enable/$P
echo 1 > /sys/class/net/$IF/ecn/roce_rp/enable/$P
cat /sys/class/net/$IF/ecn/roce_rp/params/rpg_gd

# 核对
mlnx_qos -i $IF
ethtool -S $IF | grep -E "prio${P}_(rx|tx)_pause|pause_storm"
""", size=7.8)

    H2(doc, "A.2 固件侧")
    CODE(doc, r"""
# 查询
mlxconfig -d $DEV query | grep -E 'ROCE_CC|CNP_|LINK_TYPE'

# 只开 priority 3；如参数带端口后缀，用 _P1/_P2
mlxconfig -d $DEV -y set ROCE_CC_PRIO_MASK=8 CNP_DSCP=48 CNP_802P_PRIO=6

# 复核 + 重启
mlxconfig -d $DEV query | grep -E 'ROCE_CC|CNP_'
reboot
""", size=8.0)

    H2(doc, "A.3 交换机侧")
    CODE(doc, r"""
# Onyx
roce lossless
show roce
show interfaces ethernet 1/1 counters roce
show interfaces ethernet 1/1 counters pfc prio 3
show dcb priority-flow-control interface ethernet 1/1

# Cumulus
nv set qos roce mode lossless
nv set qos pfc default-global switch-priority 3
nv set qos pfc default-global cable-length 100
nv config apply
nv show qos roce
nv show interface swp1 qos roce counters
nv show interface swp1 qos pfc-watchdog
""", size=7.8)

    H2(doc, "A.4 回滚")
    CODE(doc, r"""
mlnx_qos -i $IF --pfc 0,0,0,0,0,0,0,0
echo 0 > /sys/class/net/$IF/ecn/roce_rp/enable/$P
echo 0 > /sys/class/net/$IF/ecn/roce_np/enable/$P
# 固件参数按备份逐项恢复；不要直接 mlxconfig reset
""", size=8.0)
    P(doc, "回滚后至少确认以下四项，再宣布恢复：")
    BULLETS(doc, [
        "PFC 已关闭或恢复到变更前状态；交换机侧 PFC oper 状态与主机一致。",
        "ECN 的 RP/NP enable 与参数已恢复；业务不再出现持续降速。",
        "业务吞吐/P99 恢复；`no-buffer-discard`、`out_of_sequence` 没有继续增长。",
        "记录回滚时间线、影响范围、根因和后续动作，更新变更记录。",
    ])


def add_appendix_b(doc):
    H1(doc, "附录 B  DCQCN 参数总表", "B")
    P(doc, "下表把 DOCA 3.5 文档中的参数、默认值、单位和调优含义集中在一起。默认值适用 ConnectX-4 及以后；实际值以本机 `cat`/`mlxconfig query` 为准。[S6]")
    rows = [
        ("ROCE_CC_PRIO_MASK", "Enable", "8-bit mask", "按 priority 启用 DCQCN；255=全开，8=priority3"),
        ("DCE_TCP_G / dce_tcp_g", "1019", "10-bit fixed", "α 更新权重；1019/1024≈0.995"),
        ("DCE_TCP_RTT / dce_tcp_rtt", "1", "µs", "α 更新周期"),
        ("INITIAL_ALPHA_VALUE", "1023", "10-bit fixed", "首个 CNP 的 α 初值"),
        ("RATE_TO_SET_ON_FIRST_CNP", "0", "Mb/s", "首个 CNP 强制速率；0=不强制"),
        ("RPG_MIN_DEC_FAC", "50", "%", "单次降速上限"),
        ("RPG_MIN_RATE", "1", "Mb/s", "QP 最低速率"),
        ("RPG_GD", "11", "exponent", "降速指数；越小越狠"),
        ("RATE_REDUCE_MONITOR_PERIOD", "4", "µs", "CNP 观察窗口"),
        ("CLAMP_TGT_RATE", "Disable", "bool", "连续 CNP 时 TargetRate 更新方式"),
        ("RPG_TIME_RESET", "300", "µs", "升速定时器"),
        ("RPG_BYTE_RESET", "32767", "64 B units", "升速字节计数器；约 2 MB"),
        ("RPG_THRESHOLD", "1", "count", "AI/HAI 前的连续触发次数"),
        ("RPG_AI_RATE", "5", "Mb/s", "AI 步长"),
        ("RPG_HAI_RATE", "50", "Mb/s", "HAI 步长"),
        ("CNP_DSCP", "48", "0–63", "CNP IP DSCP"),
        ("CNP_802P_PRIO", "6", "0–7", "CNP VLAN PCP"),
        ("MIN_TIME_BETWEEN_CNPS", "4", "µs", "CNP 最小间隔"),
    ]
    TABLE(doc, ["参数", "默认", "单位/编码", "说明"], rows, [5.8, 2.0, 3.0, 5.2], font_size=8.0, first_col_bold=True)
    CALLOUT(doc, "关于 RPG_GD 的编码", "DOCA 文档对 `RPG_GD` 的“定点编码”描述较特殊，但降速公式明确使用 `2^RPG_GD`，默认值为 11。不要把它当成线性的百分比；修改前先用 sysfs 读取实际值，并在实验环境验证单次降速幅度。[S6]", "warn")
    P(doc, "`RPG_BYTE_RESET` 的单位是 64 字节，32767×64 B≈2 MB；不要误读成 32 KB。`DCE_TCP_RTT` 与 `RATE_REDUCE_MONITOR_PERIOD` 在 DOCA 表中的单位是 µs，默认分别是 1 和 4。[S6]")


def add_appendix_c(doc):
    H1(doc, "附录 C  官方原文证据摘录", "C")
    P(doc, "下表摘录支撑本文关键结论的官方原文（节选），并给出中文释义与出处。完整上下文请打开附录 D 的链接。")
    rows = [
        ("PFC 是按优先级暂停", "\"Priority Flow Control (PFC) IEEE 802.1Qbb applies pause functionality to specific classes of traffic on the Ethernet link.\"", "PFC 把暂停作用于特定流量类，而不是整条链路。", "[S3]"),
        ("PFC 的 8 个虚拟链路", "\"PFC creates eight separate virtual links on the physical link and allows any of these links to be paused and restarted independently...\"", "一条物理链路上有 8 个可独立暂停/恢复的虚拟链路。", "[S8]"),
        ("PFC 默认关闭", "\"Keeps flow control disabled for all priorities on all ports by default\"", "默认所有端口、所有优先级都关闭流控。", "[S8]"),
        ("PFC 只支持物理口", "\"Supports flow control only on physical ports, not on logical interfaces...\"", "PFC 只作用于物理端口，不作用于隧道/逻辑接口。", "[S8]"),
        ("Lossless 不等于零丢包", "\"In this context, lossless does not mean that packets are absolutely never lost.\"", "lossless 不意味着绝对不丢包。", "[S10]"),
        ("ECN 需要全路径支持", "\"This feature requires all nodes in the path ... to support ECN to ensure reliable communication.\"", "ECN 需要路径上所有节点支持。", "[S4]"),
        ("DCQCN 的三角色", "\"The CP is typically the network switch.\" / \"The NP is the receiving NIC.\" / \"The RP is the sending NIC.\"", "CP=交换机，NP=接收网卡，RP=发送网卡。", "[S5]"),
        ("PFC 缓冲与 cable length", "\"Incorrect cable length settings cause wasted buffer space ... or packet drops...\"", "cable length 配错会导致缓冲浪费或丢包。", "[S12]"),
        ("reserved 至少覆盖 Xoff", "\"The reserved allocation for this buffer should be at least the value of Xoff...\"", "lossless PG 的 reserved 至少应等于 Xoff。", "[S9]"),
        ("主机 stall prevention 默认 8 秒", "\"The stall prevention timeout is configured to 8 seconds by default. Auto mode sets ... 100 msec.\"", "默认 8 秒；auto 为 100 ms。", "[S3]"),
        ("运行时配置非持久", "\"Configure pfc ... set trust to dscp ... Non-persistent (need to be applied after each boot)\"", "PFC/trust/ToS 等运行时配置需要每次启动后重新应用。", "[S15]"),
        ("mlxconfig 持久化", "\"The configuration is kept after reset.\" / \"...reboot the system.\"", "mlxconfig 配置跨 reset 保留，但需要重启生效。", "[S14]"),
        ("CNP 默认 DSCP/PCP", "\"CNP_DSCP ... 48\" / \"CNP_802P_PRIO ... 6\"", "CNP 默认 DSCP 48、PCP 6。", "[S6]"),
        ("RoCE 只有 4 个 ToS 值", "\"With RoCE, there can only be 4 predefined ToS values for the purpose of QoS mapping.\"", "RoCE 的 ToS→QoS 映射只有 4 个预定义值。", "[S2]"),
        ("RoCEv2 需要 lossless 流控", "\"RoCEv2 requires flow control for lossless Ethernet.\"", "要实现 lossless Ethernet，RoCEv2 需要流控。", "[S13]"),
    ]
    TABLE(doc, ["结论", "官方原文（节选）", "中文释义", "出处"], rows, [3.2, 7.4, 3.8, 1.6], font_size=7.6, first_col_bold=True)


def add_appendix_d(doc):
    H1(doc, "附录 D  参考文档与链接", "D")
    P(doc, "以下 17 份文档是本文的事实来源；访问日期均为 2026-10-25。链接可能随 NVIDIA 文档版本更新而变化，若失效请用标题在 NVIDIA Networking Docs 中检索。")

    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table, BORDER, 4)
    widths = [1.1, 7.0, 5.4, 2.5]
    for i, w in enumerate(widths):
        table.columns[i].width = Cm(w)
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    headers = ["ID", "文档（版本）", "本文用途", "链接"]
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    set_row_cant_split(hdr)
    for i, h in enumerate(headers):
        cell = hdr.cells[i]
        set_cell_width(cell, widths[i])
        set_cell_background(cell, NAVY)
        set_cell_margins(cell, 0.07, 0.07, 0.10, 0.10)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        set_paragraph_format(p, before=0, after=0, line=1.1, align=WD_ALIGN_PARAGRAPH.CENTER)
        r = p.add_run(h)
        set_run_font(r, HEAD_FONT, 8.6, True, WHITE)

    for idx, s in enumerate(SOURCES):
        tr = table.add_row()
        set_row_cant_split(tr)
        vals = [s["id"], s["title"] + "\n" + s["version"], s["use"], "打开"]
        for i, val in enumerate(vals):
            cell = tr.cells[i]
            set_cell_width(cell, widths[i])
            set_cell_margins(cell, 0.05, 0.05, 0.09, 0.09)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if idx % 2 == 1:
                set_cell_background(cell, "F7F9FC")
            p = cell.paragraphs[0]
            set_paragraph_format(p, before=0, after=0, line=1.15,
                                 align=WD_ALIGN_PARAGRAPH.CENTER if i in (0, 3) else WD_ALIGN_PARAGRAPH.LEFT)
            if i == 3:
                add_hyperlink(p, s["url"], "官方页面", color=BLUE, size=7.8)
            else:
                for j, part in enumerate(str(val).split("\n")):
                    if j:
                        p.add_run().add_break()
                    r = p.add_run(part)
                    set_run_font(r, BODY_FONT, 7.8, i == 0, NAVY)

    P(doc, "延伸阅读（NVIDIA 企业支持社区，可能需要登录）：")
    for title, url in [
        ("Understanding RoCEv2 Congestion Management", "https://enterprise-support.nvidia.com/s/article/understanding-rocev2-congestion-management"),
        ("RDMA/RoCE Solutions", "https://enterprise-support.nvidia.com/s/article/rdma-roce-solutions"),
        ("Recommended Network Configuration Examples for RoCE Deployment", "https://enterprise-support.nvidia.com/s/article/recommended-network-configuration-examples-for-roce-deployment"),
    ]:
        p = doc.add_paragraph()
        set_paragraph_format(p, before=0, after=2, line=1.2, left_indent=0.55)
        p.paragraph_format.first_line_indent = Cm(-0.38)
        r = p.add_run("• ")
        set_run_font(r, BODY_FONT, 9.5, True, BLUE)
        add_hyperlink(p, url, title, color=BLUE, size=8.2)

    H2(doc, "文档维护")
    P(doc, "建议在以下时机复核本文：① 固件/驱动大版本升级；② 交换机 NOS 升级；③ 新增 lossless 业务或改变超配比；④ 发生 PFC 风暴/大面积丢包后；⑤ 每季度例行。复核时至少重跑第 9 章的单流、incast、重启持久化和回滚四项。")
    H2(doc, "免责声明")
    P(doc, "NVIDIA 文档会随固件、驱动、交换机 NOS 版本变化；同一参数在不同型号上也可能有不同默认值。本文给出的命令和数值用于建立可复现的基线，不构成对任何特定集群的性能承诺。生产变更前必须在同等固件/驱动的实验环境验证，并准备回滚方案。")


def main():
    doc = Document()
    setup_styles(doc)
    add_cover(doc)
    add_front_matter(doc)
    add_body_start(doc)
    add_section_1(doc)
    add_section_2(doc)
    add_section_3(doc)
    add_section_4(doc)
    add_section_5(doc)
    add_section_6(doc)
    add_section_7(doc)
    add_section_8(doc)
    add_section_9(doc)
    add_section_10(doc)
    add_section_11(doc)
    add_section_12(doc)
    add_appendix_a(doc)
    add_appendix_b(doc)
    add_appendix_c(doc)
    add_appendix_d(doc)

    doc.core_properties.title = DOC_TITLE
    doc.core_properties.subject = DOC_SUBTITLE
    doc.core_properties.author = "网络技术整理"
    doc.core_properties.keywords = "ConnectX-6, RoCEv2, DCQCN, ECN, PFC, Congestion Control"
    doc.core_properties.comments = "Based on public NVIDIA documentation; see Appendix D."
    doc.save(OUT_DOCX)
    print("saved", OUT_DOCX)


if __name__ == "__main__":
    main()
