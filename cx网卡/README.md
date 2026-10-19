# 自研网卡 vs NVIDIA ConnectX-6：课程资料包

> 主题：自研网卡与 CX6 的使用差异、配置落点、文档地图  
> 版本基线：ConnectX-6 VPI / Dx / Lx；MLNX_OFED 24.10 LTS；DOCA-OFED 3.x；MFT 4.3x  
> 整理时间：2026-10

## 先看哪个？

| 目的 | 打开 |
|---|---|
| 系统学习 / 打印讲义 | `CX6_vs_自研网卡_课程讲义.docx`（34 页） |
| 直接看 / 发给别人（无需 Office） | `CX6_vs_自研网卡_课程讲义.pdf` |
| 上台讲课 | `CX6_vs_自研网卡_讲座.pptx`（22 页） |
| 讲稿 PDF | `CX6_vs_自研网卡_讲座.pdf` |
| 快速查文档 / 发给学员 | `CX6文档地图.md`（可直接点击链接） |
| 离线看官方硬件手册 | `references/` 下的两份 PDF |

## 一页结论

1. **CX6 不是一张卡，是一个家族**：VPI / Dx / Lx，三套硅片、三套固件分支、三套文档。先认卡。
2. **文档按层切，不按卡切**：卡手册讲硬件；RoCE/QoS/SR-IOV 在 OFED 手册；固件参数在 MFT 手册；DPDK/OVS 在生态文档；大量“怎么做”在支持 KB。
3. **配置不在一处**：固件（`mlxconfig`）、驱动（`modprobe`/`devlink`）、接口（`ethtool`/`sysfs`）、系统（`/etc`）各管一层。
4. **版本强绑定**：卡型号 ↔ PSID ↔ 固件分支 ↔ 驱动栈 ↔ OS/kernel。任何一环错位，都会“命令对、现象不对”。
5. **MLNX_OFED 已进入维护期**：2024-10 是最后一个独立版，2027-10 EOL；新部署优先 DOCA-OFED。

## 课程主线

```text
先认卡（VPI/Dx/Lx）
  → 再认栈（inbox / MLNX_OFED / DOCA-OFED）
    → 再认层（固件 / 驱动 / 接口 / 系统 / 数据面）
      → 最后才调优
```

## 资料包结构

```text
.
├── CX6_vs_自研网卡_课程讲义.docx      # 完整讲义：10 章 + 附录（34 页）
├── CX6_vs_自研网卡_课程讲义.pdf       # 讲义 PDF
├── CX6_vs_自研网卡_讲座.pptx          # 22 页幻灯片
├── CX6_vs_自研网卡_讲座.pdf           # 幻灯片 PDF
├── CX6文档地图.md                     # 可点击的文档索引
├── README.md                          # 本文件
├── references/
│   ├── NVIDIA_ConnectX-6_IB_Ethernet_Adapter_Cards_User_Manual.pdf
│   └── NVIDIA_ConnectX-6_Dx_Ethernet_Adapter_Cards_User_Manual.pdf
├── assets/                            # 讲义/幻灯片图表
├── build_handout.py                   # 讲义生成脚本
├── build_deck.py                      # 幻灯片生成脚本
└── make_figures.py                    # 图表生成脚本
```

## 三个快速入口

- NVIDIA Networking 文档总入口：<https://docs.nvidia.com/networking/>
- 新文档平台：<https://networking-docs.nvidia.com/>
- 支持 KB：<https://enterprise-support.nvidia.com/s/>

## 说明

- 讲义中的接口名以 `ens1f0np0` 为例，MST 设备名以 `mt4123_pciconf0` 为例；实际请替换为 `ibdev2netdev` / `mst status -v` 的输出。
- 固件版本、DOCA 捆绑版本会随 LTS 更新；正式操作前请以 `mlxfwmanager --query` 和 NVIDIA 官方兼容矩阵为准。
- 官方文档链接在 2026-10 核对；如果失效，按文档标题搜索同名新版。
