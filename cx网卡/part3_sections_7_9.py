# -*- coding: utf-8 -*-
"""Sections 7-9."""
import os
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from docx_helpers import (
    NAVY, BLUE, TEAL, ORANGE, RED, GRAY, WHITE,
    LIGHT_BLUE, LIGHT_GRAY, LIGHT_GREEN, LIGHT_ORANGE, LIGHT_RED,
    BODY_FONT, HEAD_FONT,
    P, BULLETS, NUMBERED, H1, H2, H3, CAPTION, TABLE, CODE, CALLOUT, FIGURE,
)


def add_section_7(doc):
    H1(doc, "端到端设计：优先级、PFC 域与 ECN 域", "7")
    P(doc, "设计阶段只做三件事：把流量分对类、把 PFC 限制在正确的域、把 ECN/DCQCN 覆盖到整条路径。配置命令是最后一步；分类和域设计错了，命令再对也不会稳定。")

    H2(doc, "设计原则", "7.1")
    NUMBERED(doc, [
        "**一个 lossless priority 只承载一类业务**：RoCE 数据放独立 priority；不要把普通 TCP、管理流量、存储流量混进同一个 lossless class。",
        "**CNP 独立且最高优先**：CNP 走 strict priority，不与 RoCE 数据共享队列；否则拥塞时 CNP 自己也被排队。",
        "**PFC 域尽量靠近端点**：PFC 是逐跳反压，扩得越大，风暴影响面越大；跨 L3/WAN 不要依赖 PFC。",
        "**ECN 域覆盖全路径**：所有可能成为瓶颈的交换机都要支持 ECN，并在正确的 TC 上标记；否则 DCQCN 看不到瓶颈。",
        "**PFC 先于丢包、晚于 ECN**：目标是 ECN 先触发、PFC 兜底；但两者作用在不同缓冲，不能只比较数值，要用计数器验证。",
        "**缓冲按最坏情况设计**：最大 MTU、最长线缆、最高速率、最多 lossless priority；不要按平均值算 headroom。",
        "**可观测**：每个 priority 的 PFC、ECN、丢包、缓冲使用率都能被采集；否则无法调优。",
        "**可回滚**：每次只改一个平面（分类/PFC/ECN/缓冲），保留上一版配置。",
    ])

    H2(doc, "优先级与一致性矩阵", "7.2")
    P(doc, "下面是 NVIDIA 文档中常见的 RoCE 默认规划：RoCE 数据 priority 3、DSCP 26；CNP priority 6、DSCP 48。它不是协议强制值，但作为起点最容易与 NVIDIA 的默认 profile 对齐。")
    rows = [
        ("RoCEv2 数据", "DSCP 26 / PCP 3", "3", "3", "开（仅此 priority）", "开", "lossless 主业务"),
        ("CNP", "DSCP 48 / PCP 6", "6", "6", "不开", "默认不启用", "strict，不应被 pause"),
        ("普通 TCP/管理", "DSCP 0 / PCP 0", "0", "0", "不开", "可开", "lossy/best effort"),
    ]
    TABLE(doc, ["流量", "标记（典型）", "SP", "TC", "PFC", "ECN", "说明"], rows,
          [3.0, 3.4, 1.2, 1.2, 2.6, 1.4, 3.2], font_size=8.0, first_col_bold=True)
    P(doc, "一致性矩阵比单条命令重要。下面任何一行不匹配，都可能表现为“PFC 配了但不生效”或“ECN 标记了但 CNP 回不来”。")
    rows = [
        ("应用", "RoCE QP 设置 ToS/DSCP=26；CNP 由网卡生成", "应用不设 ToS，流量落到 priority 0", "用 `tcpdump -v` 看 TOS，或看交换机 ECN/PFC 计数是否增长"),
        ("网卡 trust", "DSCP（L3）或 PCP（L2），与 fabric 一致", "trust PCP 但网络只改 DSCP", "`mlnx_qos -i $IF` 看 trust；抓包看 PCP/DSCP"),
        ("网卡 PFC", "priority 3 = 1，其余 0", "PFC 开在 priority 4", "`mlnx_qos -i $IF` 看 PFC 配置"),
        ("网卡 ECN", "roce_rp/roce_np 的 priority 3 都 enable", "只开 RP 或只开 NP", "`cat .../enable/3`"),
        ("交换机 ingress", "trust DSCP/PCP；DSCP26→SP3，DSCP48→SP6", "trust L2 但只配 DSCP", "`show qos` / `nv show qos`"),
        ("交换机 egress", "TC3 为 RoCE，TC6 为 CNP strict", "CNP 和 RoCE 共用一个 TC", "`show roce` / `nv show qos roce`"),
        ("缓冲", "PG3 lossless，headroom/Xoff/Xon 合理", "PG3 仍是 lossy", "`show buffers` / `nv show qos roce`"),
    ]
    TABLE(doc, ["层", "正确状态", "常见错配", "验证"], rows, [3.0, 5.6, 4.0, 3.6], font_size=8.0, first_col_bold=True)

    H2(doc, "L2/PCP 还是 L3/DSCP", "7.3")
    rows = [
        ("标记位置", "VLAN 标签的 PCP（3 bit）", "IP 头的 DSCP（6 bit）"),
        ("交换机 trust", "L2 或 both", "L3 或 both"),
        ("适用", "同子网、裸金属、传统 L2 fabric", "路由、多租户、RoCEv2 主流"),
        ("前提", "端到端 VLAN 标签存在", "应用/QP 设置 ToS；路径设备保留 DSCP"),
        ("风险", "VLAN 重写/剥离导致 PCP 丢失", "应用未设 ToS，流量落到默认 priority"),
        ("NVIDIA 默认", "Onyx 默认 trust L2；RoCE lossless 用 L3", "Cumulus RoCE 默认 trust pcp,dscp"),
    ]
    TABLE(doc, ["维度", "L2 / PCP", "L3 / DSCP"], rows, [3.2, 6.2, 6.6], font_size=8.3, first_col_bold=True)
    P(doc, "选择建议：能端到端控制应用 ToS、且 fabric 是 L3 的，优先 DSCP；只能在 L2 内闭环、且 VLAN 可控的，用 PCP。不要在同一 lossless class 里同时依赖 PCP 和 DSCP 两套映射，除非你已经验证两者一致。")
    CALLOUT(doc, "SR-IOV 的顺序", "MLNX_OFED 文档明确：trust state 应在启用 SR-IOV 之前设置，以便传播到 VF。先在 PF 上把 trust/PFC 配好，再开 VF；否则 VF 可能看不到正确的优先级映射。[S2]", "warn")

    H2(doc, "PFC 域与 ECN 域", "7.4")
    CODE(doc, r"""
主机 A ──PFC── Leaf1 ──PFC── Spine ──PFC── Leaf2 ──PFC── 主机 B
   |______________________ PFC：逐跳、L2、可扩散 ______________________|
   |______________________ ECN/DCQCN：端到端、L3 ________________________|

原则：
- PFC 只解决“这一跳的入口缓冲快满了”；不解决“整条路径谁该降速”。
- ECN 标记可以跨 L3；CNP 从接收端回到发送端，必须被优先转发。
- 跨 WAN/跨租户边界不要依赖 PFC；那里用 ECN + 重传/应用限速。
""", size=8.2)
    BULLETS(doc, [
        "**PFC 域**：从主机网卡到 ToR，或到 leaf 的 lossless 边界；域内每一跳都要开 PFC、配好缓冲。",
        "**ECN 域**：所有可能拥塞的 L3 设备；至少覆盖 leaf/spine 的 RoCE TC。",
        "**边界设备**：如果 PFC 只到 ToR，ToR 到 spine 的链路按 lossy 设计，必须确保 ECN 能吸收溢出；否则会在边界丢包。",
        "**CNP 路径**：CNP 从接收端回到发送端，可能经过与数据不同的路径；每条可能路径都要保证 CNP 的 DSCP/PCP 和 strict 队列。",
    ])

    H2(doc, "三种部署模式", "7.5")
    rows = [
        ("Lossless", "PFC + ECN/DCQCN", "存储、HPC、AI 训练等对丢包/重传敏感、fabric 可控的场景", "配置复杂、PFC storm、缓冲成本高", "[S10][S13]"),
        ("Lossy", "ECN/DCQCN，无 PFC", "可重传、多租户、跨 L3、运维希望更简单的场景", "时延/抖动、乱序、重传；拥塞严重时仍会丢包", "[S10][S13]"),
        ("Semi-lossless", "边缘单向 PFC；fabric 保持 lossy/ECN", "主机到 ToR 微突发严重、但不想把 pause 扩散到全网", "不是端到端零丢包；边界仍需 ECN/缓冲", "[S10]"),
    ]
    TABLE(doc, ["模式", "机制", "适用", "代价/风险", "依据"], rows, [2.8, 3.6, 5.0, 3.0, 1.6], font_size=8.1, first_col_bold=True)
    P(doc, "选择顺序：先问业务能否容忍重传/乱序；不能才上 lossless。不要因为“PFC 听起来更稳”就默认全闪；PFC 的运维复杂度往往高于 ECN。")

    H2(doc, "带宽、超配与缓冲", "7.6")
    BULLETS(doc, [
        "PFC/ECN 都不创造带宽。持续 2:1、4:1 超配下的 incast，靠调阈值只能缓解，不能根治；先做流量工程/拥塞源控制。",
        "缓冲不是越大越好：大缓冲会抬高排队时延，也会让 ECN 反应变慢；按 BDP + 突发 + MTU 设计，而不是“能给多少给多少”。",
        "lossless 缓冲要按“最坏端口组合”算：多个 ingress 同时打一个 egress 时，headroom 和 shared pool 都会被放大。",
        "如果 PFC pause 长期很高但 ECN 标记很低，说明 ECN 没有承担主要工作；先调 ECN，而不是继续加缓冲。",
        "如果 `no-buffer-discard` 在增长，说明 lossless 已经破了；先查 cable length/headroom/Xoff，再谈 CC 参数。",
    ])

    H2(doc, "两个参考场景", "7.7")
    H3(doc, "场景 A：单 ToR、小规模 lossless RoCE")
    BULLETS(doc, [
        "主机双口接同一 ToR（或双 ToR，按 MC-LAG/MLAG 设计），ToR 上 RoCE priority 3 开 PFC，CNP priority 6 strict。",
        "ToR 的 ECN 阈值按默认 RoCE profile 起步；用 4:1/8:1 incast 验证 ECN 标记和 PFC pause 都在可控范围。",
        "主机 `mlnx_qos --pfc 0,0,0,1,0,0,0,0`，`--trust=dscp`，`--cable_len` 填实际值；ECN RP/NP priority 3 都开。",
        "适合：小规模存储、单租户 HPC；不适合：跨 WAN、强多租户。",
    ])
    H3(doc, "场景 B：Leaf-Spine、RoCEv2 over L3")
    BULLETS(doc, [
        "主机到 leaf 可以 lossless（PFC 只到 leaf），leaf-spine 走 ECN；所有 leaf/spine 的 RoCE TC 都开 ECN。",
        "CNP 的 DSCP 48 在全路径映射到 strict TC6；确保 spine 不会把 CNP 排到数据后面。",
        "如果业务能重传，优先 lossy + ECN，避免 PFC 跨 spine 扩散；如果必须 lossless，PFC 域要显式限定，并开 watchdog。",
        "适合：AI/HPC 多级 fabric；需要严格的 buffer/ECN 调优和监控。",
    ])

    H2(doc, "反模式", "7.8")
    BULLETS(doc, [
        "所有 priority 都开 PFC，“反正不丢包”；结果普通 TCP 也会反压，风暴影响面最大。",
        "PFC 开在 priority 4，ECN/应用用 priority 3；计数器全是 0，误以为“没拥塞”。",
        "CNP 和 RoCE 数据共用一个 TC；拥塞时 CNP 被数据挡住，DCQCN 反应迟滞。",
        "只在主机开 PFC，交换机没开；主机发 Pause，交换机不理会或不对称。",
        "cable length 随便填 1 m；高估缓冲、低估在途，PFC 还没生效就丢包。",
        "把 `no-buffer-discard` 当成“正常重传”；lossless 设计里它应该是 0 或接近 0。",
        "在生产环境用 `mlxconfig reset` 回滚；把所有固件参数一起清掉。",
        "不记录基线，调参后只看吞吐峰值；P99 时延和 PFC 风暴被忽略。",
    ])


def add_section_8(doc):
    H1(doc, "实施步骤：从基线到上线", "8")
    P(doc, "这一章给出一条可以照着执行的路径。命令中的 `$IF`、`$DEV`、`$P` 是占位符；执行前先替换成实际接口、MST 设备和优先级。不同固件/驱动的参数名可能带 `_P1/_P2` 后缀，先 query 再 set。")

    H2(doc, "Step 0：盘点与备份", "8.1")
    CODE(doc, r"""
# 1) 确认网卡、驱动、固件
lspci -d 15b3: -nn
ethtool -i $IF
ofed_info -s
mlxfwmanager --query

# 2) 找到 MST 设备
mst start
mst status -v

# 3) 备份当前配置（非常重要）
mkdir -p /root/roce-baseline
mlxconfig -d $DEV query > /root/roce-baseline/mlxconfig.before.txt
mlnx_qos -i $IF > /root/roce-baseline/mlnx_qos.before.txt
ethtool -S $IF > /root/roce-baseline/ethtool.before.txt
cat /sys/class/net/$IF/ecn/roce_rp/enable/$P \
  > /root/roce-baseline/ecn_rp_enable.before.txt 2>/dev/null || true
""", size=8.0)
    CALLOUT(doc, "先确认端口是 Ethernet", "VPI 卡可能当前是 IB 模式。`mlxconfig query` 看 `LINK_TYPE_P1/P2`；如果是 IB，先确认业务允许切换到 Ethernet，并预留重启/中断窗口。不要把 Ethernet 的 PFC 命令套到 IB 端口。", "warn")

    H2(doc, "Step 1：固件侧（持久化）", "8.2")
    P(doc, "固件侧主要设置三件事：哪些 priority 启用 DCQCN、CNP 的 DSCP/PCP、以及（必要时）端口链路类型。`mlxconfig` 的配置跨重启保留，修改后需要重启才能生效。[S14]")
    CODE(doc, r"""
# 1) 先看参数名和当前值
mlxconfig -d $DEV query | grep -E 'ROCE_CC|CNP_|LINK_TYPE'

# 2) 只对 priority 3 启用 DCQCN（按 8 位掩码理解 bit3=8；先 query 确认）
#    如果 query 显示参数带端口后缀，则用 ROCE_CC_PRIO_MASK_P1 / CNP_DSCP_P1 ...
mlxconfig -d $DEV -y set \
  ROCE_CC_PRIO_MASK=8 \
  CNP_DSCP=48 \
  CNP_802P_PRIO=6

# 3) 复核 Next Boot 值
mlxconfig -d $DEV query | grep -E 'ROCE_CC|CNP_'

# 4) 重启（官方要求）
reboot
""", size=8.0)
    BULLETS(doc, [
        "`ROCE_CC_PRIO_MASK=255` 表示 8 个 priority 全开，是 Network Operator 的 RoCE 优化默认；只承载一个 RoCE priority 时，按 8 位掩码理解可用 8（bit3），但写入前务必用 `mlxconfig query` 确认参数名和描述。[S15]",
        "`CNP_DSCP=48`、`CNP_802P_PRIO=6` 是 NVIDIA 默认；如果你的 fabric 把 CNP 映射到别的 SP/TC，必须同步改，不能只改一半。[S6]",
        "固件参数是持久化的；这正是它与 `mlnx_qos`/sysfs 的区别。[S14][S15]",
        "如果只是改 CNP 的 DSCP/PCP，不需要动 `LINK_TYPE`；不要为了“重置”而改链路类型。",
    ])

    H2(doc, "Step 2：交换机侧", "8.3")
    P(doc, "交换机侧要同时配置：trust、PFC、ECN、CNP 的 strict 队列、lossless buffer。NVIDIA Onyx 和 Cumulus Linux 都有 RoCE 一键 profile；先用 profile 建立基线，再做局部调优。")
    H3(doc, "Onyx 示例")
    CODE(doc, r"""
# 进入 config 模式
configure terminal

# 一键 lossless RoCE：PFC priority 3 + ECN + buffer + CNP strict
roce lossless

# 核对默认值（不同版本输出可能不同）
show roce
show interfaces ethernet 1/1 counters roce
show interfaces ethernet 1/1 counters pfc prio 3
""", size=8.0)
    P(doc, "如果不用一键 profile，至少显式配置 PFC：")
    CODE(doc, r"""
dcb priority-flow-control enable force
dcb priority-flow-control priority 3 enable
interface ethernet 1/1 dcb priority-flow-control mode on force
""", size=8.0)
    P(doc, "Onyx 的 `roce` 命令可能引起接口 toggle 和瞬时流量损失；变更前确认维护窗口。[S11]")
    H3(doc, "Cumulus Linux 示例")
    CODE(doc, r"""
# lossless RoCE（默认模式）
nv set qos roce mode lossless
nv set qos pfc default-global switch-priority 3
nv set qos pfc default-global cable-length 100
nv config apply

# 核对
nv show qos roce
nv show interface swp1 qos roce counters
""", size=8.0)
    P(doc, "如果只想用 ECN、不用 PFC：")
    CODE(doc, r"""
nv set qos roce mode lossy
nv config apply
""", size=8.0)
    CALLOUT(doc, "不要混用两套 NOS 命令", "Onyx 与 Cumulus 的语法、默认值、对象模型不同；本文把它们并列只是为了说明“同一机制在不同 NOS 上怎么落”。生产环境只选你实际使用的那一套，不要把 `dcb priority-flow-control` 和 `nv set qos` 混着敲。", "warn")

    H2(doc, "Step 3：主机侧（运行时）", "8.4")
    P(doc, "主机侧要配置 trust、PFC priority、cable length、ECN RP/NP。PFC 和 trust 是运行时配置，通常不会跨重启保留；需要纳入启动脚本。[S15]")
    CODE(doc, r"""
IF=ens1f0np0
P=3

# 1) DCBX 控制权：本地静态配置用 OS 控制；如果交换机用 DCBX 下发，改用 fw 并不要同时用 lldptool
mlnx_qos -i $IF --dcbx=os

# 2) trust：L3 用 dscp；L2 用 pcp
mlnx_qos -i $IF --trust=dscp

# 3) PFC：只开 priority 3
mlnx_qos -i $IF --pfc 0,0,0,1,0,0,0,0

# 4) cable length：按实际线缆填写（单位以工具帮助为准）
mlnx_qos -i $IF --cable_len=100

# 5) 可选：显式 DSCP→priority 映射，确保 26→3、48→6
mlnx_qos -i $IF --dscp2prio set,26,3
mlnx_qos -i $IF --dscp2prio set,48,6

# 6) ECN RP/NP：priority 3 启用
echo 1 > /sys/class/net/$IF/ecn/roce_np/enable/$P
echo 1 > /sys/class/net/$IF/ecn/roce_rp/enable/$P

# 7) 核对
mlnx_qos -i $IF
""", size=8.0)
    BULLETS(doc, [
        "`--pfc` 的 8 个值对应 priority 0–7；第 4 个值是 priority 3。不要照抄文档里 priority 4 的示例。",
        "`--cable_len` 影响主机侧 Xoff/Xon 阈值；填错会导致缓冲浪费或丢包。[S2]",
        "`--trust=dscp` 是 L3 方案的起点；如果 fabric 是纯 L2/PCP，用 `--trust=pcp`，并确保 VLAN 标签存在。",
        "如果 DCBX 是 `fw` 控制，`mlnx_qos` 的修改可能被固件覆盖；先确认 `mlnx_qos -i $IF` 的 DCBX mode。[S2]",
    ])

    H2(doc, "Step 4：应用侧标记", "8.5")
    P(doc, "如果应用不设置 ToS/DSCP，RoCE 流量可能落到 priority 0，PFC/ECN 都不会按预期工作。RoCE 应用通过 RDMA-CM 的 `RDMA_OPTION_ID_TOS` 设置 ToS；MLNX_OFED 文档特别提醒：RoCE 只有 4 个预定义 ToS 值可用于 QoS 映射。[S2]")
    BULLETS(doc, [
        "确认应用/中间件把 RoCE 流量标成 DSCP 26（或你的 fabric 规划值）。",
        "确认 CNP 由网卡生成，不经过应用；不要把 CNP 和业务流量混在一个 QP/priority。",
        "用 `tcpdump -v` 或交换机计数器验证标记；不要只信应用配置。",
        "如果使用 SR-IOV，先在 PF 上设置 trust，再启用 VF。[S2]",
    ])

    H2(doc, "Step 5：开机自动应用", "8.6")
    P(doc, "把运行时配置做成 systemd oneshot、Ansible playbook 或 Network Operator 的 NicConfigurationTemplate。不要依赖“上次手动敲过”。下面的 unit 只是模板；ExecStart 需要替换成你的接口和参数。")
    CODE(doc, r"""
# /etc/systemd/system/roce-qos.service
[Unit]
Description=Apply RoCE PFC/trust/ECN runtime settings
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/mlnx_qos -i ens1f0np0 --trust=dscp
ExecStart=/usr/sbin/mlnx_qos -i ens1f0np0 --pfc 0,0,0,1,0,0,0,0
ExecStart=/usr/sbin/mlnx_qos -i ens1f0np0 --cable_len=100
ExecStart=/bin/sh -c 'echo 1 > /sys/class/net/ens1f0np0/ecn/roce_np/enable/3'
ExecStart=/bin/sh -c 'echo 1 > /sys/class/net/ens1f0np0/ecn/roce_rp/enable/3'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
""", size=7.8)
    CALLOUT(doc, "Network Operator 已经做了这件事", "如果你用 NVIDIA Network Operator 的 `roceOptimized`，它会设置 `ROCE_CC_PRIO_MASK=255`、CNP DSCP/PCP，并在每个 PF 上配置 PFC priority 3、trust dscp、ToS 0；文档明确这些运行时配置是非持久的，需要在每次启动后应用。不要和手写 systemd 重复配置，选一个 authority。[S15]", "info")

    H2(doc, "Step 6：变更顺序与停机", "8.7")
    rows = [
        ("1", "固件参数", "mlxconfig + reboot", "需要重启；业务中断"),
        ("2", "交换机 RoCE profile", "roce lossless / nv set qos roce", "可能 toggle 接口；业务中断"),
        ("3", "交换机 buffer/ECN 微调", "按厂商命令", "可能瞬时丢包；维护窗口"),
        ("4", "主机 trust/PFC/cable_len", "mlnx_qos", "可能短暂断流；逐台滚动"),
        ("5", "主机 ECN sysfs", "echo enable/params", "可能短暂降速；逐台滚动"),
        ("6", "应用 ToS", "应用/中间件配置", "按应用灰度"),
    ]
    TABLE(doc, ["#", "阶段", "动作", "影响"], rows, [1.2, 4.0, 4.8, 6.0], font_size=8.4, first_col_bold=True)
    P(doc, "每一阶段结束后都做一次最小验证（PFC 配置、ECN enable、CNP 计数），不要等全部配完再排错。")


def add_section_9(doc):
    H1(doc, "验证、验收与性能测试", "9")
    P(doc, "验证的目标不是“命令敲成功了”，而是“拥塞时 PFC/ECN 按预期动作，业务指标达标”。至少要做单流、incast、故障/风暴、重启持久化四类测试。")

    H2(doc, "测试拓扑", "9.1")
    BULLETS(doc, [
        "两台主机 + 一台交换机，链路速率/MTU/线缆长度与生产一致；主机双口建议接同一 ToR 或双 ToR，按生产拓扑。",
        "RoCEv2 GID 用 `show_gids` 确认；`ib_write_bw -d mlx5_0 -x <gid>` 指定 RoCEv2 GID。",
        "至少 4 个客户端打 1 个服务端做 incast；如果生产有 8:1、16:1，实验室也要覆盖。",
        "交换机镜像/计数器和主机 `ethtool -S` 同时采集；否则无法判断 PFC 和 ECN 谁先动作。",
    ])

    H2(doc, "验收标准", "9.2")
    rows = [
        ("PFC 配置", "`mlnx_qos -i $IF` 显示 priority 3 = 1，其余 0；交换机 `show dcb priority-flow-control` oper=Enabled", "必选"),
        ("ECN 配置", "RP/NP priority 3 enable=1；交换机 `show roce` ECN 在 TC3", "必选"),
        ("CNP 路径", "CNP DSCP/PCP 与交换机映射一致；CNP 走 strict TC6", "必选"),
        ("单流吞吐", "达到线速的约定比例（按业务 SLO 定义）", "必选"),
        ("incast 吞吐", "无持续 PFC pause 风暴；吞吐随并发下降但可恢复", "必选"),
        ("丢包", "lossless priority 的 `no-buffer-discard` 为 0 或接近 0", "必选"),
        ("时延", "P99 在 SLO 内；无持续毫秒级尖峰", "必选"),
        ("风暴防护", "PFC watchdog 开启；`tx_pause_storm_error_events` 不增长", "必选"),
        ("重启持久化", "固件参数保留；运行时配置由启动项自动恢复", "必选"),
        ("回滚", "按第 11 章能在维护窗口内恢复", "必选"),
    ]
    TABLE(doc, ["项目", "通过标准（示例，按业务调整）", "级别"], rows, [3.4, 10.8, 1.8], font_size=8.3, first_col_bold=True)

    H2(doc, "主机侧核对", "9.3")
    CODE(doc, r"""
IF=ens1f0np0
P=3

# PFC / trust / cable length
mlnx_qos -i $IF

# PFC 计数器（只看 priority 3）
ethtool -S $IF | grep -E "prio${P}_(rx|tx)_pause|pause_storm"

# ECN enable
cat /sys/class/net/$IF/ecn/roce_rp/enable/$P
cat /sys/class/net/$IF/ecn/roce_np/enable/$P

# ECN 参数
for f in rpg_gd rpg_ai_rate rpg_hai_rate rpg_min_rate; do
  printf "%s=" "$f"; cat /sys/class/net/$IF/ecn/roce_rp/params/$f
done

# RoCE 计数器（sysfs；不同驱动/固件名称可能不同，先 ls）
ls /sys/class/infiniband/mlx5_0/ports/1/hw_counters/
""", size=8.0)
    P(doc, "`ethtool -S` 的 pause 计数器语义：`tx_pause` 是本端发出的 Pause（本端接收侧拥塞），`rx_pause` 是本端收到的 Pause（对端让本端减速）。不要把两者看反。[S3]")

    H2(doc, "交换机侧核对", "9.4")
    H3(doc, "Onyx")
    CODE(doc, r"""
show roce
show interfaces ethernet 1/1 counters roce
show interfaces ethernet 1/1 counters pfc prio 3
show dcb priority-flow-control interface ethernet 1/1
""", size=8.0)
    P(doc, "重点看：ECN marked packets、RoCE PFC pause packets/duration、no buffer discard、buffer max usage。`show roce` 还会给出 Min/Max、PFC priority、TC/ETS 映射。[S11]")
    H3(doc, "Cumulus Linux")
    CODE(doc, r"""
nv show qos roce
nv show interface swp1 qos roce status
nv show interface swp1 qos roce counters
nv show interface swp1 qos pfc-watchdog
""", size=8.0)
    P(doc, "重点看：pfc-priority、rx/tx enabled、congestion-control min/max、ECN marked、pause packets、no-buffer-discard、buffer max usage。[S13]")

    H2(doc, "流量测试", "9.5")
    NUMBERED(doc, [
        "**单流基线**：`ib_write_bw` 单 QP，确认 GID、MTU、速率、FEC 正常；记录吞吐/时延。",
        "**并发基线**：多 QP/多进程，但不过载；确认没有异常 PFC/ECN。",
        "**incast**：4:1、8:1 多打一，持续 10 分钟；观察 ECN 标记、CNP、PFC pause、buffer max usage、重传。",
        "**降速/恢复**：人为制造拥塞后停止，确认 RP 能恢复；不要只看“降下去”，要看“能回来且不振荡”。",
        "**PFC 负向测试（仅实验室）**：让接收端暂停 drain 或注入 pause，验证 watchdog/ stall prevention 能止损；绝不在生产做。",
        "**重启测试**：重启主机/交换机，确认固件参数保留、运行时配置由启动项恢复。",
    ])
    P(doc, "不要用 `ping` 验证 RoCE 拥塞控制；它不走 RDMA QP，也不产生 CNP。必须用 RDMA 流量（`ib_write_bw`/`ib_read_lat` 等）和交换机 RoCE 计数器。")

    H2(doc, "计数器解读", "9.6")
    rows = [
        ("`prio3_tx_pause` 增长", "本端接收侧入口拥塞，正在向对端发 Pause", "看本端 ingress buffer、cable length、Xoff/headroom", "[S3]"),
        ("`prio3_rx_pause` 增长", "对端让本端减速；本端是发送侧", "看对端/交换机缓冲，不要只调本端", "[S3]"),
        ("`tx_pause_storm_warning_events`", "Pause 持续时间超过预警水线", "检查接收端是否慢 drain、是否死锁", "[S3]"),
        ("`tx_pause_storm_error_events`", "超过超时，Pause 发送被禁用", "立即止损；可能已经丢包", "[S3]"),
        ("switch `ECN marked packets` 高", "交换机在标记，DCQCN 应降速", "看 CNP 是否回得去、RP 是否 enable", "[S11]"),
        ("switch `no-buffer-discard` > 0", "lossless 已破，缓冲不足或 PFC 未生效", "查 headroom/cable/Xoff/PFC 配置", "[S11]"),
        ("`buffer max usage` 接近分配值", "缓冲接近上限，随时可能丢包", "扩容/调 pool/降超配", "[S11]"),
        ("`out_of_sequence`/重传增长", "丢包或乱序；RoCE 在重传", "查链路、PFC、ECN、MTU", "[S16]"),
    ]
    TABLE(doc, ["现象", "含义", "下一步", "依据"], rows, [4.6, 5.0, 4.6, 1.6], font_size=8.0, first_col_bold=True)

    H2(doc, "验收记录模板", "9.7")
    rows = [
        ("环境", "网卡型号/PSID、固件、驱动、交换机 NOS、端口速率、MTU、线缆长度"),
        ("配置", "RoCE priority、PFC mask、ECN TC、CNP DSCP/PCP、buffer 参数"),
        ("基线", "单流/并发/incast 的吞吐、P99、PFC pause、ECN 标记、丢包"),
        ("变更", "改了什么、为什么、谁批准、何时回滚"),
        ("结论", "通过/有条件通过/不通过；遗留问题与责任人"),
    ]
    TABLE(doc, ["项", "内容"], rows, [3.0, 13.2], font_size=8.5, first_col_bold=True)
