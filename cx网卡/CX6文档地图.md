# CX6 文档地图与使用差异速查

> 配套课程《从自研网卡到 NVIDIA ConnectX-6：使用差异分析与文档地图》  
> 版本基线：ConnectX-6 VPI / Dx / Lx；MLNX_OFED 24.10 LTS；DOCA-OFED 3.x；MFT 4.3x  
> 核对时间：2026-10

---

## 0. 先看这里：三条最短路径

| 你的任务 | 先看这份 | 直接跳转 |
|---|---|---|
| 第一次上机 / 认卡 | ConnectX-6 Dx 用户手册 | [打开](https://networking-docs.nvidia.com/connectx6dxhw/) |
| 装驱动 / 配 RoCE / SR-IOV | MLNX_OFED 24.10 用户手册 | [打开](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/) |
| 改固件参数 / 刷固件 | MFT 手册 + mlxconfig | [打开](https://networking-docs.nvidia.com/mftswum/434118lts/) |

**一句话结论：CX6 不是一张卡，是一个家族；文档按“层”切，不按“卡”切。**

---

## 1. 为什么按“CX6 使用说明”搜不到

1. **CX6 是家族**：VPI / Dx / Lx 三套硅片、三套固件分支、三套文档。  
2. **文档按层切**：卡手册只讲硬件；RoCE/QoS/SR-IOV 在 OFED 手册；固件参数在 MFT 手册；DPDK/OVS 在生态文档。  
3. **平台在迁移**：`docs.mellanox.com` → `docs.nvidia.com/networking` → `networking-docs.nvidia.com`；旧链接经常 404。  
4. **命名在迁移**：MLNX_OFED → DOCA-OFED。2024-10 是最后一个独立版；2027-10 EOL。  
5. **版本强绑定**：卡型号 ↔ PSID ↔ 固件分支 ↔ 驱动栈 ↔ OS/kernel，任何一环错位都会“命令对、现象不对”。  
6. **大量“怎么做”在 KB**：`enterprise-support.nvidia.com` 的文章不在手册目录里，但往往是官方最佳实践。

### 检索词对照

| 不要搜 | 改搜 |
|---|---|
| CX6 使用说明 | `ConnectX-6 Dx Ethernet Adapter Cards User Manual` |
| CX6 驱动 | `NVIDIA MLNX_OFED Documentation 24.10 installation` |
| CX6 配置 | `NVIDIA Firmware Tools mlxconfig` |
| CX6 光模块 | `mlxlink utility` / `mlxcables` |
| CX6 RoCE 配置 | `MLNX_OFED RDMA over Converged Ethernet RoCE` |
| CX6 调优 | `Performance Tuning for NVIDIA Adapters` |
| CX6 丢包 | `Understanding mlx5 Linux counters` |

---

## 2. 六层文档地图

| 层 | 文档 | 链接 | 什么时候看 |
|---|---|---|---|
| L5 应用/生态 | DPDK mlx5 PMD / rdma-core / OVS / SPDK | [DPDK mlx5](https://doc.dpdk.org/guides/nics/mlx5.html) | 写代码、做卸载、跑存储 |
| L4 配置/工具 | ethtool / devlink / mlnx_qos / sysfs | [OFED Ethtool](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/ethtool.md) | 日常配置与排障 |
| L3 驱动/栈 | MLNX_OFED 24.10 / DOCA-OFED / Release Notes | [OFED 24.10](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/) | 安装、升级、兼容性 |
| L2 固件工具 | MFT / mlxconfig / mlxlink / mlxfwmanager | [MFT 4.34.1](https://networking-docs.nvidia.com/mftswum/434118lts/) | 改卡、刷机、看链路 |
| L1 硬件手册 | CX6 VPI UM / CX6 Dx UM | [CX6 VPI](https://networking-docs.nvidia.com/connectx6vpihw/) · [CX6 Dx](https://networking-docs.nvidia.com/connectx6dxhw/) | 上架、接线、规格 |
| L0 发布/兼容 | Firmware Release Notes / Compatibility Matrix | [DOCA 3.2.3 General Support](https://networking-docs.nvidia.com/doca/archive/3-2-3/general-support) | 选版本、查支持 |

---

## 3. 14 份核心文档

### 3.1 硬件手册

1. **ConnectX-6 VPI 用户手册**  
   <https://networking-docs.nvidia.com/connectx6vpihw/>  
   解决：接口、LED、供电、上架、规格、固件升级、排障。  
   重点：Interfaces / Hardware Installation / Updating Adapter Firmware / Troubleshooting。

2. **ConnectX-6 Dx 用户手册**  
   <https://networking-docs.nvidia.com/connectx6dxhw/>  
   解决：Dx 的 OPN、接口、规格、驱动安装、固件升级、监控。  
   重点：Introduction（OPN 表）/ Interfaces / Specifications / Monitoring。

### 3.2 驱动栈

3. **MLNX_OFED 24.10 LTS 用户手册（当前主线）**  
   <https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/>  
   解决：安装、卸载、Secure Boot、性能调优入口，以及 Ethernet/RoCE/QoS/SR-IOV/OVS 的全部配置。  
   重点：Installation / Ethernet Network / Virtualization / Troubleshooting。

4. **MLNX_OFED 5.9 用户手册（旧版，但语义最完整）**  
   <https://networking-docs.nvidia.com/mlnxofedswum/590560125/>  
   解决：24.10 手册里被精简掉的细节（GID 示例、RoCE LAG、VF 策略、QoS 映射）。  
   重点：RDMA over Converged Ethernet / Quality of Service / Single Root IO Virtualization。

5. **MLNX_OFED → DOCA-OFED 迁移指南**  
   <https://networking-docs.nvidia.com/doca/archive/3-2-3/mlnx_ofed-to-doca-ofed-transition-guide>  
   解决：为什么改名、DOCA-Host 有哪些 profile、迁移步骤、时间线。  
   重点：What is DOCA-OFED / Transition Timeline / Installation Example。

6. **DOCA 3.2.3 General Support（兼容矩阵）**  
   <https://networking-docs.nvidia.com/doca/archive/3-2-3/general-support>  
   解决：哪些 OS/kernel 受支持、各卡捆绑的固件版本、DOCA 组件版本。  
   重点：Supported Platforms and NIC Firmware Versions / Supported Host OS。

### 3.3 固件工具

7. **NVIDIA Firmware Tools（MFT）用户手册**  
   <https://networking-docs.nvidia.com/mftswum/434118lts/>  
   解决：mst、mlxfwmanager、mlxconfig、flint、mlxfwreset、mlxlink、mlxcables 的完整用法。  
   重点：mst Service / mlxfwmanager / mlxconfig / mlxlink / Cable Utilities。

8. **mlxconfig：改固件配置**  
   <https://networking-docs.nvidia.com/mftswum/434118lts/using-mlxconfig>  
   解决：查询/设置固件参数、SR-IOV、端口类型、备份/恢复、raw TLV。  
   重点：Using mlxconfig / mlxconfig Commands / MFT Supported Configurations and Parameters。

9. **mlxlink：链路诊断**  
   <https://networking-docs.nvidia.com/mftswum/434118lts/mlxlink-utility>  
   解决：链路状态、FEC、BER、眼图、模块信息、PRBS、PCIe 链路。  
   重点：Queries / Commands / Tool Usage with NIC vs. Switch。

10. **mlxcables：光模块/线缆**  
    <https://networking-docs.nvidia.com/mftswum/434118lts/mlxcables-cables-tool>  
    解决：光模块 EEPROM、DDM、寄存器读取、线缆固件升级。  
    重点：Query / DDM / read_reg / dump。

11. **mlxfwmanager：固件升级/查询**  
    <https://networking-docs.nvidia.com/mftswum/434118lts/mlxfwmanager-firmware-update-and-query-tool>  
    解决：查询 PSID/FW、升级 .mfa、在线升级、下载固件包。  
    重点：Querying the Device / Updating the Device。

12. **mlxfwreset：不重启加载新固件**  
    <https://networking-docs.nvidia.com/mftswum/434118lts/mlxfwreset-loading-firmware-on-5th-generation-devices-tool>  
    解决：reset level/type/sync、热重启、多主机同步。  
    重点：Query Command / Reset Command / Reset Levels and Types。

### 3.4 数据面与性能

13. **DPDK MLX5 PMD**  
    <https://doc.dpdk.org/guides/nics/mlx5.html>  
    解决：DPDK 下 mlx5 的编译、配置、Rx/Tx 调优、flow steering、representor、多进程。  
    重点：Configuration / Rx/Tx Tuning / Features & Support / Usage。

14. **性能调优与计数器 KB**  
    <https://enterprise-support.nvidia.com/s/article/performance-tuning-for-mellanox-adapters>  
    解决：BIOS/内核/IRQ/队列/协议栈的调优顺序，以及 mlx5 计数器含义。  
    重点：Performance Tuning / Understanding mlx5 Linux Counters / ethtool Counters。

---

## 4. 按任务找文档

| 你要做的事 | 先看这份 | 关键章节 |
|---|---|---|
| 第一次上架、接线、确认规格 | [CX6 / Dx 用户手册](https://networking-docs.nvidia.com/connectx6dxhw/) | Interfaces / Specifications |
| 装驱动、选 OFED 版本 | [OFED 24.10 安装](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/installation.md) | Installation / Supported OS |
| 升级固件、改固件参数 | [MFT 手册](https://networking-docs.nvidia.com/mftswum/434118lts/) | mlxfwmanager / mlxconfig |
| RoCE 不通、丢包、重传 | [OFED RoCE](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/rdma-over-converged-ethernet-roce.md) | GID / PFC / ECN / counters |
| PFC、ETS、DSCP 信任 | [OFED QoS](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/quality-of-service-qos.md) | Trust / PFC / prio_tc |
| SR-IOV、VF、switchdev | [OFED SR-IOV](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/single-root-io-virtualization-sr-iov.md) | SR-IOV / VF 策略 / representor |
| OVS 硬件卸载 | [OFED OVS ASAP²](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/ovs-offload-using-asap2-direct.md) | SwitchDev / tc-policy / representor |
| DPDK 收发包 | [DPDK mlx5](https://doc.dpdk.org/guides/nics/mlx5.html) | Configuration / Rx-Tx Tuning |
| NVMe-oF / NFS-RDMA | [OFED Storage](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/storage-protocols.md) | NVMe-oF Target Offload |
| 性能上不去 | [性能调优 KB](https://enterprise-support.nvidia.com/s/article/performance-tuning-for-mellanox-adapters) | BIOS / IRQ / 队列 / sysctl |
| 排障、看计数器 | [OFED Troubleshooting](https://networking-docs.nvidia.com/mlnxofedswum/24101140lts/troubleshooting.md) | General / Ethernet / Performance |

---

## 5. 版本矩阵（截至 2026-10）

| 卡 | 固件分支 | DOCA 3.2.3 捆绑 | 主要文档 |
|---|---|---|---|
| ConnectX-6 VPI | 20.43.x | 20.43.8016 | [CX6 用户手册](https://networking-docs.nvidia.com/connectx6vpihw/) + [CX6 固件 RN](https://docs.nvidia.com/networking/display/connectx6firmwarev20434100lts/changes+and+new+features) |
| ConnectX-6 Dx | 22.4x | 22.47.3576 | [CX6 Dx 用户手册](https://networking-docs.nvidia.com/connectx6dxhw/) + [Dx 固件 RN](https://docs.nvidia.com/networking/display/connectx6dxfirmwarev22438002lts/changes+and+new+feature+history) |
| ConnectX-6 Lx | 26.4x | 26.47.3576 | CX6 Lx 用户手册 + Lx 固件 RN |

**版本选择建议：**

- 新部署、OS 在 DOCA 3.x 支持列表：优先 **DOCA-OFED 3.2.x**（`doca-ofed` profile）。
- 存量 CX6 VPI、追求稳定：**MLNX_OFED 24.10 LTS**（维护到 2027-10）。
- 只要以太网、包越小越好：**inbox `mlx5_core`** 或 **DOCA-RoCE**。
- 需要 IPsec/TLS/MACsec：**DOCA-OFED + CX6 Dx**（注意型号是否带 Crypto）。
- DPDK / OVS 卸载：**DOCA-OFED 或 inbox + DPDK**（不要绑 vfio-pci）。

**三个不要：** 不要混装 inbox/OFED；不要跨 PSID 刷固件；不要只看驱动不看固件。

---

## 6. 30 分钟上机检查单

| # | 步骤 | 命令 | 看什么 / 判读 |
|---|---|---|---|
| 1 | 认卡 | `lspci -nn \| grep -i mellanox` | 15b3:101b/101d/101f；确认 VPI/Dx/Lx |
| 2 | 认固件 | `mst start && mlxfwmanager --query` | Device Type、PSID、FW 分支是否匹配 |
| 3 | 认驱动 | `ethtool -i ens1f0np0`、`ofed_info -s` | driver=mlx5_core；OFED 版本是否存在 |
| 4 | 认接口 | `ip -br link`、`ibdev2netdev` | PF netdev、mlx5_x 的映射 |
| 5 | 看链路 | `ethtool ens1f0np0`、`mlxlink -d <mst> -m -c` | speed/width/FEC/BER；模块是否识别 |
| 6 | 配 IP | `ip addr add 192.0.2.1/24 dev ens1f0np0` | ping 对端；确认 MTU |
| 7 | 看计数 | `ethtool -S ens1f0np0 \| head -40` | rx/tx、drop、crc、link_down 是否增长 |
| 8 | 验 RDMA | `ibv_devices`、`ibv_devinfo`、`rdma link show` | PORT_ACTIVE；link_layer=Ethernet |
| 9 | 验 RoCE | `cma_roce_mode -d mlx5_0 -p 1 -m 2`、`ibv_rc_pingpong` | 能建连；GID 类型为 v2 |
| 10 | 看 QoS | `mlnx_qos -i ens1f0np0` | PFC/trust/prio_tc 是否符合设计 |
| 11 | 开 SR-IOV | `mlxconfig q`、`sriov_totalvfs`、`sriov_numvfs` | SRIOV_EN=1；VF 能创建 |
| 12 | 做基线 | `iperf3` / `perftest` / `mlxlink -c` | 记录吞吐/延迟/BER，作为后续对比 |

---

## 7. 12 个差异落点

| # | 落点 | 自研典型 | CX6 标准 | 关键命令 |
|---|---|---|---|---|
| 1 | 认卡与型号 | 一个型号一本手册 | PCI ID + Device Type + PSID | `mlxfwmanager --query` |
| 2 | 驱动安装 | 驱动+固件一个包 | inbox 或 DOCA-OFED | `ofed_info -s` |
| 3 | 固件升级 | 厂商刷机工具 | MFT + PSID 匹配 + reset | `mlxfwmanager -u` |
| 4 | 固件参数 | 私有配置文件 | `mlxconfig` 读写 NV 配置 | `mlxconfig q/set/backup` |
| 5 | 设备命名 | eth0/eth1 | netdev/ibdev/VF/representor/MST | `ibdev2netdev` |
| 6 | 链路与光模块 | 厂商 CLI | ethtool + mlxlink + mlxcables | `mlxlink -m -c` |
| 7 | 队列与中断 | 厂商 CLI | ethtool -L/-G/-C | `ethtool -L` |
| 8 | Offload | 私有开关 | ethtool -K / tc flower | `tc ... skip_sw` |
| 9 | RoCE 与 QoS | 私有 RDMA 配置 | verbs + PFC/ECN + mlnx_qos | `cma_roce_mode` |
| 10 | SR-IOV | 私有 VF 管理 | mlxconfig + sriov_numvfs + switchdev | `devlink port show` |
| 11 | DPDK / OVS | 自研 PMD | mlx5 PMD（bifurcated） | `testpmd -a <bdf>` |
| 12 | 调优与监控 | 私有 dashboard | 四个计数器来源 | `devlink health` |

---

## 8. 命令速查

### 8.1 识别与版本

```bash
lspci -nn | grep -i mellanox
mst start
mst status -v
mlxfwmanager --query
ethtool -i ens1f0np0
ofed_info -s
ibdev2netdev
rdma link show
```

### 8.2 固件与配置

```bash
mlxfwmanager -u -d /dev/mst/mt4123_pciconf0 -i fw.mfa
mlxfwreset -d /dev/mst/mt4123_pciconf0 query
mlxfwreset -d /dev/mst/mt4123_pciconf0 reset -y
mlxconfig -d /dev/mst/mt4123_pciconf0 q
mlxconfig -d /dev/mst/mt4123_pciconf0 show_confs
mlxconfig -d /dev/mst/mt4123_pciconf0 set SRIOV_EN=1 NUM_OF_VFS=8
mlxconfig -d /dev/mst/mt4123_pciconf0 -f backup.conf backup
```

### 8.3 链路与光模块

```bash
ethtool ens1f0np0
ethtool -m ens1f0np0
ethtool --show-fec ens1f0np0
mlxlink -d /dev/mst/mt4123_pciconf0 -m -c
mlxlink -d /dev/mst/mt4123_pciconf0 --show_fec
mlxcables -d /dev/mst/mt4123_pciconf0_cable_0 -q
mlxcables -d /dev/mst/mt4123_pciconf0_cable_0 --DDM
```

### 8.4 队列 / 中断 / offload

```bash
ethtool -l ens1f0np0
ethtool -L ens1f0np0 combined 8
ethtool -g ens1f0np0
ethtool -G ens1f0np0 rx 4096 tx 4096
ethtool -c ens1f0np0
ethtool -C ens1f0np0 adaptive-rx off rx-usecs 32
ethtool -k ens1f0np0
ethtool --show-priv-flags ens1f0np0
tc qdisc add dev ens1f0np0 ingress
tc filter show dev ens1f0np0 ingress
```

### 8.5 RoCE / QoS / SR-IOV

```bash
cma_roce_mode -d mlx5_0 -p 1 -m 2
cat /sys/class/infiniband/mlx5_0/ports/1/gid_attrs/types/*
mlnx_qos -i ens1f0np0
mlnx_qos -i ens1f0np0 --pfc 0,0,0,1,0,0,0,0
mlnx_qos -i ens1f0np0 --trust dscp
echo 4 > /sys/class/net/ens1f0np0/device/sriov_numvfs
ip link set ens1f0np0 vf 0 trust on
devlink dev eswitch set pci/0000:3b:00.0 mode switchdev
devlink port show
```

---

## 9. 本地离线文件

| 文件 | 说明 |
|---|---|
| `references/NVIDIA_ConnectX-6_IB_Ethernet_Adapter_Cards_User_Manual.pdf` | CX6 VPI 用户手册（离线） |
| `references/NVIDIA_ConnectX-6_Dx_Ethernet_Adapter_Cards_User_Manual.pdf` | CX6 Dx 用户手册（离线） |
| `CX6_vs_自研网卡_课程讲义.docx` | 完整课程讲义（34 页） |
| `CX6_vs_自研网卡_课程讲义.pdf` | 讲义 PDF（无需 Office） |
| `CX6_vs_自研网卡_讲座.pptx` | 讲座幻灯片（22 页） |
| `CX6_vs_自研网卡_讲座.pdf` | 幻灯片 PDF |
| `assets/` | 讲义/幻灯片使用的图表 |

---

## 10. 参考入口

- NVIDIA Networking 文档总入口：<https://docs.nvidia.com/networking/>
- 新文档平台：<https://networking-docs.nvidia.com/>
- Enterprise Support KB：<https://enterprise-support.nvidia.com/s/>
- 固件下载：<https://network.nvidia.com/support/firmware/firmware-downloads/>
- OFED 下载：<https://network.nvidia.com/products/infiniband-drivers/linux/mlnx_ofed/>
- MFT 下载：<https://network.nvidia.com/products/adapter-software/firmware-tools/>

> 注：NVIDIA 文档有版本选择器；如果链接失效，按标题搜索同名新版。DOCA 3.2+ 使用 DKMS 源码编译，NVIDIA 不再签驱动；Secure Boot 环境要提前规划 MOK/签名。
