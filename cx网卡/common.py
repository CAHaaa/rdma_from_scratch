# -*- coding: utf-8 -*-
"""Shared constants and source metadata."""

DOC_TITLE = "ConnectX-6 网卡 RoCEv2 拥塞控制与 PFC 流控实施指南"
DOC_SUBTITLE = "基于 NVIDIA 官方文档的 DCQCN / ECN / PFC 设计、配置、验证与运维"
DOC_VERSION = "v1.1"
DOC_DATE = "2026-10-25"
OUT_DOCX = "ConnectX-6_RoCEv2_拥塞控制与PFC实施指南_v1.1.docx"

SOURCES = [
    {
        "id": "S1",
        "title": "NVIDIA ConnectX-6 Ethernet Adapter Cards User Manual — Introduction / Features and Benefits",
        "version": "Last updated 2022-08-31",
        "url": "https://networking-docs.nvidia.com/connectx6enhw/introduction",
        "use": "CX6 的 PFC、QCN、ETS、RoCE、QoS 能力与型号边界",
    },
    {
        "id": "S2",
        "title": "NVIDIA MLNX_OFED Documentation — Quality of Service (QoS)",
        "version": "v24.10-2.1.8.0 LTS (2024 LTS U2)",
        "url": "https://networking-docs.nvidia.com/mlnxofedswum/24102180lts/quality-of-service-qos",
        "use": "ToS→sk_prio→UP→TC 映射、trust、mlnx_qos、DCBX、cable_len",
    },
    {
        "id": "S3",
        "title": "NVIDIA MLNX_OFED Documentation — Flow Control",
        "version": "v24.10-2.1.8.0 LTS (2024 LTS U2)",
        "url": "https://networking-docs.nvidia.com/mlnxofedswum/24102180lts/flow-control",
        "use": "PFC 配置、逐优先级计数器、PFC stall prevention、Dropless RQ",
    },
    {
        "id": "S4",
        "title": "NVIDIA MLNX_OFED Documentation — Explicit Congestion Notification (ECN)",
        "version": "v24.10-2.1.8.0 LTS (2024 LTS U2)",
        "url": "https://networking-docs.nvidia.com/mlnxofedswum/24102180lts/explicit-congestion-notification-ecn",
        "use": "RoCEv2 ECN 的 sysfs 启用方式、RP/NP 算法与参数路径",
    },
    {
        "id": "S5",
        "title": "NVIDIA DOCA Documentation — DCQCN CC Algorithm",
        "version": "DOCA 3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/dcqcn-cc-algorithm",
        "use": "CP/NP/RP 三角色、ECN 标记、CNP、alpha 与速率恢复阶段",
    },
    {
        "id": "S6",
        "title": "NVIDIA DOCA Documentation — DCQCN CC Parameters",
        "version": "DOCA 3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/dcqcn-cc-parameters",
        "use": "DCQCN 参数、默认值、单位、CNP DSCP/PCP 与最小 CNP 间隔",
    },
    {
        "id": "S7",
        "title": "NVIDIA DOCA Documentation — Congestion Control Infrastructure",
        "version": "DOCA 3.5.0",
        "url": "https://networking-docs.nvidia.com/doca/archive/3-5-0/congestion-control-infrastructure",
        "use": "DCQCN 的定位、原生 CC 与可编程 CC 的边界",
    },
    {
        "id": "S8",
        "title": "NVIDIA Onyx User Manual — Priority Flow Control (PFC)",
        "version": "Onyx 3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/priority-flow-control-pfc",
        "use": "PFC 八个虚拟链路、默认关闭、物理口限制、Xoff/Xon、PFC watchdog",
    },
    {
        "id": "S9",
        "title": "NVIDIA Onyx User Manual — Shared Buffers",
        "version": "Onyx 3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/shared-buffers",
        "use": "lossless traffic pool、PG/TC、reserved/shared、headroom、Xoff/Xon",
    },
    {
        "id": "S10",
        "title": "NVIDIA Onyx User Manual — RDMA over Converged Ethernet (RoCE)",
        "version": "Onyx 3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/rdma-over-converged-ethernet-roce",
        "use": "RoCE lossless/semi-lossless/lossy 模式、默认优先级与 ECN 配置",
    },
    {
        "id": "S11",
        "title": "NVIDIA Onyx User Manual — RoCE Commands",
        "version": "Onyx 3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/roce-commands",
        "use": "show roce 默认值、RoCE 计数器、模式切换的流量影响",
    },
    {
        "id": "S12",
        "title": "NVIDIA Cumulus Linux 5.15 — Quality of Service",
        "version": "Cumulus Linux 5.15",
        "url": "https://docs.nvidia.com/networking-ethernet-software/cumulus-linux-515/Layer-1-and-Switch-Ports/Quality-of-Service/",
        "use": "PFC 缓冲计算、cable length、PFC watchdog、ECN 默认阈值",
    },
    {
        "id": "S13",
        "title": "NVIDIA Cumulus Linux 5.15 — RDMA over Converged Ethernet (RoCE)",
        "version": "Cumulus Linux 5.15",
        "url": "https://docs.nvidia.com/networking-ethernet-software/cumulus-linux-515/Layer-1-and-Switch-Ports/Quality-of-Service/RDMA-over-Converged-Ethernet-RoCE/",
        "use": "RoCE 默认配置、PFC+ECN 组合、DSCP 26/48 与优先级映射",
    },
    {
        "id": "S14",
        "title": "NVIDIA Firmware Tools (MFT) — mlxconfig: Changing Device Configuration Tool / Examples",
        "version": "MFT 4.36.0",
        "url": "https://networking-docs.nvidia.com/mftswum/4.36.0/examples-of-mlxconfig-usage",
        "use": "mlxconfig 查询/设置、配置持久化、重启生效",
    },
    {
        "id": "S15",
        "title": "NVIDIA Network Operator — Configuration Details (RoCE optimized)",
        "version": "v26.10.0",
        "url": "https://mellanox.github.io/network-operator-docs/nic-conf-operator/configuration-details.html",
        "use": "ROCE_CC_PRIO_MASK=255、CNP DSCP/PCP、PFC priority 3、运行时配置非持久",
    },
    {
        "id": "S16",
        "title": "NVIDIA DOCA Documentation — Ethernet Interface: RoCE Counters",
        "version": "DOCA 2.9.2 LTS",
        "url": "https://networking-docs.nvidia.com/doca/archive/2-9-2-lts-ovs-update/ethernet-interface",
        "use": "RoCE 计数器所在的 sysfs 路径",
    },
    {
        "id": "S17",
        "title": "NVIDIA Onyx User Manual — QoS Commands",
        "version": "Onyx 3.10.4800",
        "url": "https://networking-docs.nvidia.com/onyxum/3.10.4800/qos-commands",
        "use": "trust 默认值、DSCP/PCP 映射、ECN absolute threshold 的 KB 单位",
    },
]
