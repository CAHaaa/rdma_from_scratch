# -*- coding: utf-8 -*-
"""Constants and sources for the congestion-algorithm/tuning companion."""

TOPIC_TITLE = "ConnectX-6 RoCEv2 拥塞算法与调优专题"
TOPIC_SUBTITLE = "DCQCN / ECN / PFC 的算法原理、参数敏感性、实验设计与分场景调优"
TOPIC_VERSION = "v1.0"
TOPIC_DATE = "2026-10-25"
TOPIC_DOCX = "ConnectX-6_RoCEv2_拥塞算法与调优专题_v1.0.docx"

TOPIC_SOURCES = [
    {
        "id": "C1",
        "title": "NVIDIA ConnectX-6 Ethernet Adapter Cards User Manual — Introduction",
        "version": "2022-08-31",
        "url": "https://networking-docs.nvidia.com/connectx6enhw/introduction",
        "use": "CX6 的 PFC/ECN/QCN/RoCE 能力边界",
    },
    {
        "id": "C2",
        "title": "NVIDIA MLNX_OFED — Explicit Congestion Notification (ECN)",
        "version": "24.10-2.1.8 LTS",
        "url": "https://networking-docs.nvidia.com/mlnxofedswum/24102180lts/explicit-congestion-notification-ecn",
        "use": "ECN RP/NP sysfs 启用与参数路径",
    },
    {
        "id": "C3",
        "title": "NVIDIA MLNX_OFED — Flow Control",
        "version": "24.10-2.1.8 LTS",
        "url": "https://networking-docs.nvidia.com/mlnxofedswum/24102180lts/flow-control",
        "use": "PFC 配置、计数器、stall prevention",
    },
    {
        "id": "C4",
        "title": "NVIDIA DOCA — DCQCN CC Algorithm",
        "version": "3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/dcqcn-cc-algorithm",
        "use": "CP/NP/RP、ECN 标记、CNP、α、降速与恢复",
    },
    {
        "id": "C5",
        "title": "NVIDIA DOCA — DCQCN CC Parameters",
        "version": "3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/dcqcn-cc-parameters",
        "use": "DCQCN 默认值、单位、CNP DSCP/PCP",
    },
    {
        "id": "C6",
        "title": "NVIDIA DOCA — Congestion Control Infrastructure",
        "version": "3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/congestion-control-infrastructure",
        "use": "DCQCN 与 ZTR-RTT 的定位、原生 CC 与可编程 CC 边界",
    },
    {
        "id": "C7",
        "title": "NVIDIA DOCA — ZTR-RTT CC Algorithm",
        "version": "3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/ztr-rtt-cc-algorithm",
        "use": "ZTR-RTT 的 RTT+CNP、AIMD、时间戳与 HOL 说明",
    },
    {
        "id": "C8",
        "title": "NVIDIA DOCA — ZTR-RTT Parameter and Counter Configuration",
        "version": "3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/ztr-rtt-cc-parameter-and-counter-configuration",
        "use": "ZTR-RTT 参数（ALPHA/MAX_DEC/MAX_INC/AI）与调优范围",
    },
    {
        "id": "C9",
        "title": "NVIDIA DOCA — DOCA PCC",
        "version": "3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/doca-pcc",
        "use": "可编程 CC 的平台要求、RP/NP、DPACC、BlueField-3 限制",
    },
    {
        "id": "C10",
        "title": "NVIDIA Onyx — RDMA over Converged Ethernet (RoCE)",
        "version": "3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/rdma-over-converged-ethernet-roce",
        "use": "Onyx RoCE 模式、默认优先级、ECN/PFC/CNP 配置",
    },
    {
        "id": "C11",
        "title": "NVIDIA Onyx — Priority Flow Control (PFC)",
        "version": "3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/priority-flow-control-pfc",
        "use": "PFC 语义、Xoff/Xon、watchdog",
    },
    {
        "id": "C12",
        "title": "NVIDIA Onyx — Shared Buffers",
        "version": "3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/shared-buffers",
        "use": "PG/TC、headroom、reserved/shared、lossless pool",
    },
    {
        "id": "C13",
        "title": "NVIDIA Onyx — QoS Commands（含 RED/ECN）",
        "version": "3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/qos-commands",
        "use": "ECN absolute threshold 的 KB 单位、RED/ECN 命令、trust/DSCP 映射",
    },
    {
        "id": "C14",
        "title": "NVIDIA Cumulus Linux 5.15 — Quality of Service",
        "version": "5.15",
        "url": "https://docs.nvidia.com/networking-ethernet-software/cumulus-linux-515/Layer-1-and-Switch-Ports/Quality-of-Service/",
        "use": "PFC 缓冲/watchdog、ECN 默认阈值、cable length",
    },
    {
        "id": "C15",
        "title": "NVIDIA Cumulus Linux 5.15 — RDMA over Converged Ethernet (RoCE)",
        "version": "5.15",
        "url": "https://docs.nvidia.com/networking-ethernet-software/cumulus-linux-515/Layer-1-and-Switch-Ports/Quality-of-Service/RDMA-over-Converged-Ethernet-RoCE/",
        "use": "RoCE 默认配置、PFC+ECN、DSCP 26/48",
    },
    {
        "id": "C16",
        "title": "NVIDIA MFT — mlxconfig",
        "version": "4.36.0",
        "url": "https://networking-docs.nvidia.com/mftswum/4.36.0/examples-of-mlxconfig-usage",
        "use": "固件配置持久化与重启生效",
    },
    {
        "id": "C17",
        "title": "NVIDIA Network Operator — Configuration Details",
        "version": "v26.10.0",
        "url": "https://mellanox.github.io/network-operator-docs/nic-conf-operator/configuration-details.html",
        "use": "RoCE 优化默认、运行时配置非持久",
    },
    {
        "id": "C18",
        "title": "Zhu et al., Congestion Control for Large-Scale RDMA Deployments",
        "version": "ACM SIGCOMM 2015, DOI 10.1145/2829988.2787484",
        "url": "https://dl.acm.org/doi/10.1145/2829988.2787484",
        "use": "DCQCN 的算法来源、设计目标与背景",
    },
    {
        "id": "C19",
        "title": "RFC 3168 — The Addition of Explicit Congestion Notification (ECN) to IP",
        "version": "IETF, 2001",
        "url": "https://www.rfc-editor.org/rfc/rfc3168",
        "use": "ECN 的协议定义、ECT/CE 语义",
    },
    {
        "id": "C20",
        "title": "Mittal et al., TIMELY: RTT-based Congestion Control for the Datacenter",
        "version": "ACM SIGCOMM 2015, DOI 10.1145/2829988.2787510",
        "url": "https://dl.acm.org/doi/10.1145/2829988.2787510",
        "use": "延迟型 CC 的代表与 RTT 信号",
    },
    {
        "id": "C21",
        "title": "RFC 5681 — TCP Congestion Control",
        "version": "IETF, 2009",
        "url": "https://www.rfc-editor.org/rfc/rfc5681",
        "use": "丢包型 CC 的基线（AIMD/慢启动）",
    },
]
