# RoCE / RDMA 高频问题 60 问

本文件收录 RoCE 学习与面试中**最常被问到的 60 个问题**，按十个主题分组：入门与选型 / 环境与安装 / GID 与地址 / QP 与状态机 / 内存与 MR / 性能与测量 / PFC-ECN-拥塞 / 排障 / 安全 / 源码与进阶。

**回答约定**（遵循 [`00-conventions.md`](00-conventions.md)）：

- 每个回答 2–6 句或一张小表，**只给结论与判据**，展开讲解走章节链接；
- 每个回答末尾给出 `→ 详见 [第 N 章](…)` 的章节跳转，或给出 `kernel:` / `rdma-core:` / `perftest:` 级别的源码引用（答案本身是源码级问题时）；
- 术语以 [`glossary.md`](glossary.md) 为准，容易混淆的概念在 [`glossary.md`](glossary.md) 第 9 节有逐维对比表；
- 版本相关的问题，请先对照 [`versions-and-abi.md`](versions-and-abi.md)。

> 目录：[A 入门与选型](#a-入门与选型) · [B 环境与安装](#b-环境与安装) · [C-gid-与地址](#c-gid-与地址) · [D-qp-与状态机](#d-qp-与状态机) · [E-内存与-mr](#e-内存与-mr) · [F-性能与测量](#f-性能与测量) · [G-pfc-ecn-拥塞](#g-pfc-ecn-拥塞) · [H-排障](#h-排障) · [I-安全](#i-安全) · [J-源码与进阶](#j-源码与进阶)

---

## A 入门与选型

### Q1. RDMA 真的比 TCP 快在哪里？

快在三件事同时发生：**零拷贝**（应用缓冲区与网卡之间不再有一次内核缓冲区拷贝）、**内核旁路**（数据面直接是用户态写 UAR 门铃 + 轮询 CQ，没有系统调用与协议栈）、**CPU 卸载**（接收端不产生中断、不跑协议处理，收包由网卡 DMA 直接落到已注册内存）。所以 RDMA 的收益不只是「时延低」，更是「每 GB 数据消耗的 CPU 周期少一个数量级」——这才是大规模存储/AI 集群用它的真正原因。代价是：网络必须配成无损（PFC/ECN/DCQCN）、内存必须注册、失败模式比 TCP 复杂得多。

→ 详见 [第 1 章](../01-rdma-basics.md)

### Q2. RoCE、InfiniBand、iWARP 该选哪个？

一句话选型：**新建以太网数据中心选 RoCEv2，已有 IB 专网且预算充足选 IB，跨广域或必须走 TCP 的场景才考虑 iWARP**。三者都提供 verbs 接口，差别在链路层与生态：IB 有自己的链路层、SM/SA 管理与无损机制（天生无损，不用配 PFC），RoCEv2 复用了 IB 传输层但跑在以太网上（必须自己把以太网配成无损），iWARP 把 RDMA 实现在 TCP 上（天然可靠、可跨路由，但生态与性能上限较弱）。

→ 详见 [第 1 章](../01-rdma-basics.md)

### Q3. RC 和 UD 怎么选？

**要单边操作、要可靠性、要大消息 → RC；要组播、要「一个 QP 对多个对端」、要无连接 → UD。** 能力差异是硬约束：UD 只支持 SEND/RECV，最大消息 = 一个 Path MTU，不保证顺序与送达；UD 也是唯一支持组播的类型。UC 介于两者之间（支持 RDMA WRITE，但没有 READ/Atomic 且不可靠），RoCE 生产中很少用。

| 能力 | UD | UC | RC |
|---|---|---|---|
| SEND/RECV | ✅ | ✅ | ✅ |
| RDMA WRITE | ❌ | ✅ | ✅ |
| RDMA READ | ❌ | ❌ | ✅ |
| Atomic | ❌ | ❌ | ✅ |
| 组播 | ✅ **唯一** | ❌ | ❌ |
| 最大消息 | Path MTU | 1 GB | 1 GB |

→ 详见 [第 1 章](../01-rdma-basics.md)

### Q4. RDMA WRITE 和 SEND/RECV 怎么选？

**「我只想动对端内存、不需要对端程序知道」→ WRITE；「我要让对端程序处理这条消息」→ SEND/RECV。** WRITE 是单边的：对端不需要 post recv、不产生 CQE、CPU 完全不参与，所以最快（`ib_write_lat` 就是它）。SEND 是双边的：对端必须事先 post recv，会消耗一个 RR 并产生 CQE。有一个必须记住的例外：**`WRITE_WITH_IMM` 虽然叫 WRITE，却会消耗对端一个 RR 并产生带 `IBV_WC_WITH_IMM` 的 CQE**——这是新手最常见的「明明没人 post recv 却不报错/反而报错」的来源。

→ 详见 [第 4 章](../04-verbs-model.md)

### Q5. 没有 RDMA 网卡能学 RoCE 吗？

能，而且推荐这么做。用 **Soft-RoCE（`rdma_rxe`）** 在任意普通网卡上加载模块，就能得到一个 `rxe0` 设备，perftest 全部命令都能跑，而且它发的是**真正的 RoCEv2 报文**（UDP 4791）——你可以一边跑一边抓包。更好的地方在于：`kernel:drivers/infiniband/sw/rxe/` 是逐字节构造 RoCEv2 报头的软件实现，是理解报文格式的最佳读物。软件 iWARP（`siw`）可以用来横向对比另一种封装方式。

→ 详见 [第 3 章](../03-software-stack.md)（§3.6）

### Q6. 学 RoCE 应该按什么顺序推进？

建议四阶段：**① 会用**（跑通 perftest、看懂 `ibv_devinfo`/`show_gids`、理解 `-d/-i/-x`）→ **② 会写**（用 verbs 与 RDMA_CM 各写一个最小程序，理解 QP 状态机与 MR）→ **③ 会调**（PFC/ECN/DCQCN、NUMA/PCIe、多 QP 与 ECMP）→ **④ 会读代码**（`ibv_post_send` → `mlx5_post_send` → WQE → 门铃 → 固件命令）。把 [`repo-map.md`](repo-map.md) 的第 5 节「一页速查」当索引，遇到任何概念先定位到文件再读。

→ 详见 [第 1 章](../01-rdma-basics.md) 与 [第 16 章](../16-tools.md)（§16.7）

---

## B 环境与安装

### Q7. 怎么用三条命令确认这台机器真的能用 RoCE？

按这个顺序，每一步都有明确的期望输出：

| 步骤 | 命令 | 期望 |
|---|---|---|
| ① 设备与绑定 | `rdma link show` | 有 `mlx5_0/1 ... state ACTIVE physical_state LINK_UP netdev <你的网口>` |
| ② 端口与链路层 | `ibv_devinfo -d mlx5_0 -v \| grep -Ei 'state\|link_layer\|active_mtu'` | `link_layer: Ethernet`、`state: PORT_ACTIVE` |
| ③ GID 表 | `show_gids` | 存在 `VER = v2` 且 `IPv4` 列等于业务 IP 的一行，记下 INDEX |

三步都过，才说明「设备在、链路通、RoCEv2 地址就绪」。任何一步不过，先解决那一步再往下。

> `show_gids` 是 **MLNX_OFED** 附带的脚本，**不在 rdma-core 66.0 中**（本仓库全树无此文件，`debian/infiniband-diags.install` 里也没有）。纯 inbox 环境下用 `ibv_devinfo -d <dev> -v` 的 GID 表（每行形如 `GID[  3]:`）或 `rdma link show` 替代。

→ 详见 [实验 1](../labs/lab01-environment-and-first-test.md)

### Q8. `roceP1p1s0f0` 和 `mlx5_0` 是什么关系？

它们是**同一块网卡的两个名字**，来自两套命名规则：现代上游内核由驱动直接注册 `mlx5_0` / `mlx5_1`（`ib_register_device`），RoCE LAG 激活时注册为 `mlx5_bond_0`；部分发行版与 MLNX_OFED 用 udev 规则改名为带 PCI 槽位信息的形式 `roce<P>p<B>s<S>f<F>`（P=域、B=总线、S=槽位、F=功能）。**结论：不要靠名字猜对应关系**，用 `rdma link show` 的 `netdev` 列，或者读 `/sys/class/infiniband/<dev>/ports/N/gid_attrs/ndevs/`。

→ 详见 [第 3 章](../03-software-stack.md)（§3.3）

### Q9. `ibv_devinfo` 一个设备都没有（或只有设备没有端口），怎么办？

按「从下往上」排查：① `lsmod | grep -E 'mlx5_ib|mlx5_core|ib_uverbs|ib_core'` 看模块是否加载；② `dmesg | tail -50` 看 PCI 探测与 RoCE 使能是否报错；③ `lspci -nn | grep -i mellanox` 确认硬件可见；④ `rdma link show` 确认 netdev 侧是否看到端口；⑤ RoCE 是否被显式关掉（`devlink dev param show` 关注 `ENABLE_ROCE`）。如果设备在但端口状态是 `PORT_DOWN`，那是 netdev 没 up / 没配 IP / 线缆问题，不是 RDMA 问题。

→ 详见 [第 12 章](../12-troubleshooting.md)（§12.3）

### Q10. RoCE 的内核模块加载顺序与依赖是什么？

典型依赖链是 **`mlx5_core` → `mlx5_ib` → `ib_uverbs` → `ib_core`**，加上连接管理的 `rdma_cm` → `rdma_ucm`。理解两点：① `mlx5_core` 通过 **auxiliary bus** 向 `mlx5_ib` 暴露子设备，所以是 `mlx5_ib` 依赖 `mlx5_core`，不是反过来；② `ib_uverbs_support.ko` 承载 uobject 生命周期核心 `rdma_core.c`，被 `ib_uverbs` 依赖——**它不是 `ib_uverbs.ko` 的一部分**。查当前状态用 `lsmod | grep -E 'ib_|mlx5|rdma'`。

→ 详见 [第 3 章](../03-software-stack.md)（§3.4）与 [第 7 章](../07-kernel-rdma-core.md)（§7.1）

### Q11. 同时装了 MLNX_OFED 和 inbox 驱动，会冲突吗？

会，而且是最难查的一类。两者会提供**同名但不同版本**的 `libibverbs`/`libmlx5`/内核模块，混合安装时经常出现「用户态是新版、内核模块是老版」（或反之），症状就是 [`versions-and-abi.md`](versions-and-abi.md) 第 5 节列的 `ENOSPC`/`EINVAL`/设备列不出来。判定方法：`ofed_info -s` 有输出说明装了 MLNX_OFED；`dpkg -l | grep -E 'ibverbs|rdma-core'` 看发行版包；两者的版本必须来自同一套。**修法是整包卸载重装，不要手工替换单个 `.so`。**

→ 详见 [versions-and-abi.md](versions-and-abi.md)（§5.1）

### Q12. 只有一台机器，能自测 RoCE 吗？

能，有三种由弱到强的自测：① **loopback**（同一台机器跑 server/client，用同一块卡）——验证 verbs 路径与 GID 选择，`ib_write_bw -d mlx5_0 -x <idx>` 直接跑；② **两台机器直连**（DAC 线，不经过交换机）——验证链路、MTU、PFC 端到端，但没有 ECMP 与拥塞；③ **Soft-RoCE 单机双设备**——在没有硬件时学习。注意 ① 不会暴露网络问题（ECMP、PFC、拥塞），所以「单机测试通过」绝不能推出「生产一定没问题」。

→ 详见 [第 6 章](../06-perftest.md)（§6.5）

---

## C GID 与地址

### Q13. `show_gids` 里有好几行，选哪个？

**选「`VER = v2` 且 `IPv4` 列等于你业务 IP」的那一行，记下它的 `INDEX` 作为 `-x` 参数。** `show_gids` 的列语义是：`DEV`（ibdev，对应 `-d`）、`PORT`（对应 `-i`）、`INDEX`（GID 索引，对应 `-x`）、`GID`（128 位标识，IPv4 场景下最后 4 字节就是 IP）、`IPv4`（该 GID 对应的 IP）、`VER`（`v1` / `v2`）、末列 `DEV`（对应 netdev）。同一个 IP 通常会占两行（v1 一行、v2 一行），**选 v1 会连不上或行为异常**。不要硬编码索引——netdev 配置一变索引就重排。

→ 详见 [第 2 章](../02-rocev2-protocol.md)（§2.5）

### Q14. `-x` 选错了会怎样？

症状按严重程度分三档：① **建连失败**——`Failed to modify QP to RTR` 或 perftest 卡在握手，这是最常见的结果（选到了 v1 行或 `fe80::` link-local 行）；② **建连成功但不可达**——选到了另一张网卡/另一个 VLAN 的 IP，`ib_write_bw` 超时并最终报 `IBV_WC_RETRY_EXC_ERR`；③ **跑得起来但源 IP 不是业务 IP**——抓包能看到 `tos`/源地址不对，QoS 策略不生效导致性能异常。**判据**：抓包核对源 IP 与 DSCP，或用 `ibv_devinfo -d <dev> -v | grep -E 'GID\['`（devinfo 的 GID 表每行形如 `GID[  3]:`，**没有** "gid table" 这个字符串，按后者 grep 会静默无输出）与 `show_gids` 交叉验证。

→ 详见 [第 12 章](../12-troubleshooting.md)（§12.4）

### Q15. 为什么同一块网卡上同一个 IP 会有两张 GID？

因为**一个 IP 会同时生成 RoCEv1 与 RoCEv2 两个 GID**：v1 走二层（EtherType `0x8915`），v2 走 UDP/IP（目的端口 4791）。它们在 GID 表里是两行，sysfs 里的类型字符串分别是 `"IB/RoCE v1"` 与 `"RoCE v2"`。除业务 IP 外，端口通常还有基于 link-local（`fe80::`）的 GID，那些只用于链路本地场景。**所以「有几行」是正常的，「选哪行」才是关键。**

> `rdma-core:libibverbs/cmd_device.c:282`–`:283`（`V1_TYPE "IB/RoCE v1"` / `V2_TYPE "RoCE v2"`）；sysfs 路径模板 `ports/%d/gid_attrs/types/%d`（同文件 `:295`）。

### Q16. 怎么确认流量真的走了 RoCEv2？

三条互相独立的证据，最好同时拿到：

| 证据 | 命令 / 判据 |
|---|---|
| GID 类型 | `show_gids` 选中的行 `VER = v2`；或 `ibv_devinfo -d <dev> -v` 的 GID 表里该索引标为 RoCE v2 |
| 抓包 | `tcpdump -i <netdev> -nn 'udp port 4791'` 能看到包；**目的端口 4791 是 RoCEv2 的唯一标识**；再看源 IP 是否业务 IP、`tos` 是否符合 DSCP 规划 |
| QP 属性 | 用 `-x` 显式指定 v2 索引；会话中 `rdma res show qp` 能看到 RTS 状态与 lqpn |

如果抓不到 4791 的包但程序「跑通了」，说明它根本没走 RoCE（或走的是 loopback 短路路径）。

→ 详见 [第 2 章](../02-rocev2-protocol.md)（§2.9）

### Q17. 对端的目的 MAC 是谁在解析？为什么建连有时会卡住？

**内核的 `ib_core` 在解析**，不是用户态自己去 ARP。链路是：内核地址层（`kernel:drivers/infiniband/core/addr.c` 的 `rdma_addr_*` / `rdma_resolve_ip`）通过 netlink 向邻居子系统查 ARP/ND，结果填进 AH/QP 的 `roce.dmac`；`ib_resolve_eth_dmac()`（`kernel:drivers/infiniband/core/verbs.c:1798`）负责把 dmac 与 hop limit 解析出来，调用点在 **`rdma_create_user_ah()`**（`:670`，即 `ibv_create_ah` 走的那条路径）与 **`_ib_modify_qp()`**（`:1855`，带 udata 的 modify 路径）——内核侧的 `rdma_create_ah()`（`:619`）**不做** dmac 解析。用户态对应的辅助函数在 `rdma-core:libibverbs/neigh.c`。**卡住的常见原因**：对端未配 IP / ARP 未解析成功 / 邻居表过期 / netdev down——所以 RoCE 建连失败时，「先 ping 通」是最有效的第一步。

> `kernel:drivers/infiniband/core/verbs.c:1798`（`ib_resolve_eth_dmac()` 定义）、`:1794`（注释说明它同时解析 L3 hop limit）。

### Q18. 为什么删掉一个 VLAN 子接口就把 RDMA 连接搞挂了？

因为 **GID 表是依据 netdev 的 IP 与 VLAN 动态生成的**：`kernel:drivers/infiniband/core/roce_gid_mgmt.c` 的 `add_netdev_ips`（`:429`）与 `kernel:drivers/infiniband/core/cache.c` 的 `gid_table_setup_one`（`:911`）会在 IP/VLAN 变化时增删对应的 RoCEv1/v2 GID 条目，mlx5 再通过 `.add_gid`/`.del_gid` 回调把条目下发固件（`mlx5_core_roce_gid_set`，命令 `MLX5_CMD_OP_SET_ROCE_ADDRESS = 0x761`）。删 VLAN 会让**所有 GID 索引重排**，于是硬编码的 `-x 3` 指向了别的 GID，连接自然断。同时你会收到 `IBV_EVENT_GID_CHANGE`——**不处理异步事件的程序会在这里静默失效**。

→ 详见 [第 7 章](../07-kernel-rdma-core.md)（§7.8）

---

## D QP 与状态机

### Q19. QP 为什么必须走 INIT→RTR→RTS，不能一步到位？

因为这个状态机是**硬件逐步获取配置信息**的过程，每一步解锁一类能力，缺信息就无法进入下一状态：

| 迁移 | 硬件在这一步学到什么 | 解锁的能力 |
|---|---|---|
| `RESET → INIT` | 本端身份：端口、PKey、访问标志、QKey | 可以 post 到 SQ，但不会真正发出 |
| `INIT → RTR` | 对端身份与路径：AV（含 DGID）、Path MTU、`dest_qp_num`、`RQ_PSN`、`MAX_DEST_RD_ATOMIC`、`MIN_RNR_TIMER` | **RR 可以被 post 并处理（能收）** |
| `RTR → RTS` | 可靠性参数：`timeout`、`retry_cnt`、`rnr_retry`、`MAX_QP_RD_ATOMIC` | **SR 可以被 post 并处理（能发）** |

所以「必须先 RTR 再 RTS」不是协议洁癖，而是「接收侧要先准备好，发送侧才开始」的物理要求。注意 **Init→RTR 需要 `IBV_QP_DEST_QPN` 与 `IBV_QP_RQ_PSN`** 这类容易漏的字段——漏了就是 `-EINVAL`。

→ 详见 [第 4 章](../04-verbs-model.md)（§4.3.5）

### Q20. 进入 RTR / RTS 分别要设哪些属性？

两张表互补，建议一起记（`IBV_QP_*` 是 `ibv_modify_qp` 的 mask）：

| 迁移 | Required | Optional |
|---|---|---|
| `RESET → INIT` | `IBV_QP_PKEY_INDEX`、`IBV_QP_PORT`、`IBV_QP_DC_KEY` | — |
| `INIT → INIT` | `IBV_QP_PKEY_INDEX`、`IBV_QP_PORT`、`IBV_QP_ACCESS_FLAGS` | — |
| `INIT → RTR` | `IBV_QP_AV`、`IBV_QP_PATH_MTU` | `IBV_QP_PKEY_INDEX`、`IBV_QP_DC_KEY` |
| `RTR → RTS` | `IBV_QP_TIMEOUT`、`IBV_QP_RETRY_CNT`、`IBV_QP_RNR_RETRY`、`IBV_QP_MAX_QP_RD_ATOMIC` | `IBV_QP_ALT_PATH`、`IBV_QP_MIN_RNR_TIMER`、`IBV_QP_PATH_MIG_STATE` |

另一张「按目标状态看」的表（进入某状态需要的最小 mask）见 [`glossary-quickref.md`](glossary-quickref.md) 第 2.3 节。**实践提醒**：进入 RTR 时通常还要显式给 `IBV_QP_DEST_QPN` 与 `IBV_QP_RQ_PSN`，进入 RTS 常带 `IBV_QP_SQ_PSN`——这两项在不同实现/文档里的归类不一致，但**不给就会失败**。

→ 详见 [第 4 章](../04-verbs-model.md)（§4.3.5）

### Q21. 为什么 `ibv_modify_qp` 会返回 `EINVAL`？

因为 QP 迁移有**两层校验**，两层都过才成功：

1. **内核通用层**：`ib_modify_qp_is_ok()` 用状态表 `qp_state_table[][]` 判断这条迁移边是否合法（`kernel:drivers/infiniband/core/verbs.c:1462` 定义表，`:1763` 是判定函数）；
2. **驱动层**：`mlx5_ib_modify_qp` 用 `opt_mask[][][]` 按「迁移边 + QP 类型」裁剪该状态允许的 optpar（`kernel:drivers/infiniband/hw/mlx5/qp.c:3668`）。

所以 `EINVAL` 有两个完全不同的成因：**mask 与字段不一致**（例如传了 `IBV_QP_PATH_MTU` 却把 `path_mtu` 留 0），或**该 QP 类型在这个状态下不允许这个 optpar**（例如给 UD QP 设 RC 才有的属性）。排查时先把 mask 打印出来逐位核对。

> `kernel:drivers/infiniband/core/verbs.c:1462`、`:1763`；`kernel:drivers/infiniband/hw/mlx5/qp.c:3668`。

### Q22. 为什么 `ib_write_lat` 不需要对端 post recv，`ib_send_lat` 却需要？

因为 `ib_write_lat` 用的是 **RDMA WRITE（单边操作）**：发起方直接把数据写进对端已注册内存，对端既不消耗 RR 也不产生 CQE，所以对端只要把 MR 注册好、把 `addr + rkey` 通过带外通道告诉发起方即可。`ib_send_lat` 用的是 **SEND（双边操作）**：必须有一条 RR 作为落脚点，否则对端硬件找不到「数据往哪写」，会回 RNR NAK，重试耗尽后报 `IBV_WC_RNR_RETRY_EXC_ERR`。反过来说：**WRITE 类测试不需要对端 CPU 配合，因此它测出的时延更接近纯硬件路径**——这正是它成为标准时延 benchmark 的原因。

→ 详见 [第 6 章](../06-perftest.md)（§6.1）

### Q23. QP 进了 ERROR 状态，能救回来吗？

不能「原地修」，只能**回到 RESET 重新迁移**。进入 ERROR 后 QP 上所有在途 WR 会被冲刷，你会在 CQ 里收到一连串 `IBV_WC_WR_FLUSH_ERR`（这**不是**根因，只是连带结果——真正的错误往往在最前面那条带其他状态码的 WC 上）。正确做法：① 先 `ibv_poll_cq` 把 CQ 排空，找到**第一个非 flush 的错误状态码**作为根因；② 用它定位问题（`RNR_RETRY_EXC_ERR` → 对端没 post recv；`RETRY_EXC_ERR` → 网络不通/对端 QP 不在；`REM_ACCESS_ERR` → rkey 权限不足）；③ `ibv_modify_qp` 回 `IBV_QPS_RESET`，清理在途 WR，再按 `INIT→RTR→RTS` 重建。

→ 详见 [第 4 章](../04-verbs-model.md)（§4.4）与 [第 12 章](../12-troubleshooting.md)（§12.5）

### Q24. `sq_sig_all` 与 `IBV_SEND_SIGNALED` 应该怎么配？

两者是「全局默认」与「单条覆盖」的关系，但**先要分清结构体**：`sq_sig_all` 是 **`struct ibv_qp_init_attr`** 的成员（`rdma-core:libibverbs/verbs.h:957`），也就是 **`ibv_create_qp` 时声明的属性**，它**不在 `struct ibv_qp_attr` 里**（`:1099`–`:1126` 的末字段是 `rate_limit`）——所以建 QP 之后想改它只能重建 QP。`ibv_qp_init_attr.sq_sig_all = 1` 时**每条** WR 都产生 CQE；为 0 时**只有带 `IBV_SEND_SIGNALED` 的 WR** 产生 CQE（`rdma-core:libibverbs/verbs.h:1156`）。高吞吐的正确姿势是 `sq_sig_all = 0`，然后每 N 条打一个 `IBV_SEND_SIGNALED`：CQ 压力降为 1/N，代价是错误发现延迟变大（失败的那条可能在你察觉前已经污染了后续数据）。**RTS 阶段必须保证至少有一个信号位**——一条都不打信号，程序就永远等不到完成。

> `rdma-core:libibverbs/verbs.h:1154`–`:1160`（`enum ibv_send_flags`）、`:950`–`:958`（`struct ibv_qp_init_attr`，`sq_sig_all` 在 `:957`）、`:1099`–`:1126`（`struct ibv_qp_attr`，**不含** `sq_sig_all`）。

---

## E 内存与 MR

### Q25. 为什么 `ibv_reg_mr` 会 `ENOMEM`？

`ibv_reg_mr` 返回 `NULL` 并把 `errno` 设为 `ENOMEM` 的原因有四种，按出现频率排序：

| 原因 | 判据 / 位置 |
|---|---|
| **`RLIMIT_MEMLOCK` 不够** | 内核把 `npages` 加进 `mm->pinned_vm`，超过 `rlimit(RLIMIT_MEMLOCK) >> PAGE_SHIFT` 且没有 `CAP_IPC_LOCK` 就返回 `-ENOMEM`：`kernel:drivers/infiniband/core/umem.c:224`–`:231` |
| **页 pin 不住 / 内存不足** | `pin_user_pages_fast()` 或 `sg_alloc_append_table_from_pages()` 失败：`umem.c:240`–`:248`、`:252`–`:259` |
| **DMA 映射失败** | `ib_dma_map_sgtable_attrs()` 返回非 0：`umem.c:262`–`:265` |
| **网卡侧表项耗尽** | MTT/mkey 表满，mlx5 的注册路径返回 `-ENOMEM`（`kernel:drivers/infiniband/hw/mlx5/mr.c` 多处，创建 mkey 走 `mlx5_core_create_mkey`，`mr.c:106`） |

另外两个容易误判成 `ENOMEM` 的 errno：**`EPERM`**（`!can_do_mlock()`，`umem.c:187`–`:188`）与 **`EOPNOTSUPP`**（在普通 VA 路径上传了 `IB_ACCESS_ON_DEMAND`，`umem.c:190`–`:191`）。修法：抬高 `ulimit -l` 或给 `CAP_IPC_LOCK`、检查是否泄漏 MR 未 dereg、算一下注册总量是否超过设备 `max_mr`。

→ 详见 [第 7 章](../07-kernel-rdma-core.md)（§7.6）与 [第 15 章](../15-virtualization.md)（§15.5）

### Q26. `lkey` 和 `rkey` 到底有什么区别？

一句话：**`lkey` 只在本端用（本地校验收数据/取数据），`rkey` 交给对端用（远端校验收到的 RDMA 请求）**。两者同源于一次 `ibv_reg_mr`，但出现在完全不同的地方：`lkey` 写在每条 SGE 里（`struct ibv_sge.lkey`），`rkey` 出现在 RETH/ATMETH 扩展头（`ibv_send_wr.wr.rdma.rkey`）。**安全含义天差地别**：`lkey` 泄露基本只能影响本端进程，`rkey` 泄露等价于把内存的读写权交给别人。

| 维度 | `lkey` | `rkey` |
|---|---|---|
| 使用者 | 本端硬件 | 对端硬件 |
| 出现位置 | 每条 SGE | RETH / ATMETH 头 |
| 校验对象 | 本地地址范围与权限 | 远端 RW/READ/ATOMIC 权限 |
| 泄露后果 | 本端进程内 | **等效内存泄露** |

→ 详见 [第 14 章](../14-security.md)（§14.2）

### Q27. `imm_data` 为什么要 `htonl`？

因为 **`imm_data` 在软件接口与线路上都是网络字节序**：`struct ibv_send_wr` 里它声明为 `__be32`（`rdma-core:libibverbs/verbs.h:1198`–`:1201`），`struct ibv_wc` 里的 `imm_data` 同样是网络字节序（同文件 `struct ibv_wc` 的注释明确写着 "Immediate data in network byte order"），而在线上它承载于 IMMDT 扩展头。所以小端主机必须 `htonl()` 后发出、`ntohl()` 后使用；忘了转换的典型症状是「`imm_data` 收到了，但值是个奇怪的巨大数字」——而且它**不会报错**，只会静默错值，这是最难查的一类 bug。

> `rdma-core:libibverbs/verbs.h:1195`–`:1201`（`ibv_send_wr` 的 `imm_data` / `invalidate_rkey` 联合体）。

### Q28. MR 权限应该怎么给？

按**最小权限原则**给：远端只需要读就只给 `IBV_ACCESS_REMOTE_READ`，不要习惯性给 `IBV_ACCESS_REMOTE_WRITE`。本地要往这块内存收数据才需要 `IBV_ACCESS_LOCAL_WRITE`（这个位忘给会导致 `IBV_WC_LOC_ACCESS_ERR`，是新手最常见的 bug 之一）。要跑原子操作才需要 `IBV_ACCESS_REMOTE_ATOMIC`。此外推荐加 `IBV_ACCESS_ZERO_BASED`——它让对端看到的地址从 0 开始算，**不泄露本端虚拟地址**。

| 权限位 | 何时需要 |
|---|---|
| `IBV_ACCESS_LOCAL_WRITE` | 本地要收数据（SEND/RECV 的接收缓冲区） |
| `IBV_ACCESS_REMOTE_WRITE` | 对端要 RDMA WRITE 到这块内存 |
| `IBV_ACCESS_REMOTE_READ` | 对端要 RDMA READ |
| `IBV_ACCESS_REMOTE_ATOMIC` | 对端要跑 Atomic |
| `IBV_ACCESS_ZERO_BASED` | 建议总是加（隐藏本端地址） |

> `rdma-core:libibverbs/verbs.h:615`–`:626`（`enum ibv_access_flags`）。

### Q29. ODP、dma-buf、GPUDirect RDMA 分别在解决什么问题？

三者解决的痛点不同：**ODP** 解决「注册时不想立刻 pin 住全部页」——适合几百 GB 的大内存与稀疏访问，代价是首次访问触发缺页的延迟（`IBV_ACCESS_ON_DEMAND`；内核 `umem_odp.c` / `hw/mlx5/odp.c`）。**dma-buf** 解决「这块内存不在 CPU 侧」——用于注册 GPU/加速器显存（`ibv_reg_dmabuf_mr`，uAPI 载荷 `IB_UVERBS_BUFFER_TYPE_DMABUF`，内核 `umem_dmabuf.c`）。**GPUDirect RDMA** 是前者的**业务目标**：让网卡与显存直接交换数据、绕过主机内存拷贝（perftest 的 `cuda_memory.c`/`rocm_memory.c` 就是它的实验后端）。三者可以叠用，但都要先确认设备能力。

→ 详见 [第 7 章](../07-kernel-rdma-core.md)（§7.6.3）与 [第 10 章](../10-ecosystem.md)（§10.3）

### Q30. 该用很多个小 MR，还是少量大 MR？

**默认用少量大 MR**：每个 MR 都消耗 MTT/MPT 表项与 pin 住的内存，MR 数量过多会撞上设备 `max_mr` 上限，也让硬件查表更慢。但有两种情况必须拆开：① 每块 MR 的**权限不同**（把只读数据与可写数据分开，符合最小权限）；② 需要独立失效/回收（配合 `IBV_WR_LOCAL_INV` 或 `SEND_WITH_INV`）。另一个维度是「大页」：用 2 MB/1 GB 大页能显著减少 MTT 条目数与 TLB miss，所以「少量大 MR + 大页」通常是吞吐与延迟同时最优的组合。

→ 详见 [第 13 章](../13-performance.md)（§13.4）

---

## F 性能与测量

### Q31. 单 QP 为什么跑不满带宽？

因为 **RoCEv2 的 ECMP 哈希输入通常是「源/目的 IP + 源/目的 UDP 端口」——前提是交换机侧的 ECMP 哈希包含了 L4 端口（部分老设备/配置不含，见第 2.7 节）**，而同一个 QP 的源 UDP 端口是固定的——于是这个 QP 的全部流量被哈希到同一条路径上，无论拓扑里有多少条等价路径，你都只能用其中一条的带宽。派生逻辑在 `kernel:include/rdma/ib_verbs.h`：`rdma_flow_label_to_udp_sport()`（`:5077`）把 20 位 flow label 折叠成 14 位源端口，并或上 `IB_ROCE_UDP_ENCAP_VALID_PORT_MIN = 0xC000`（`:5064`）；flow label 为 0 时由 `rdma_calc_flow_label(lqpn, rqpn)`（`:5100`，`v = lqpn * rqpn` 再折叠成 20 位）自动推导。**所以立即见效的办法是 `-q 4`（多 QP）**——每增加一个 QP 就多一个 sport、多一条哈希路径。

> `kernel:include/rdma/ib_verbs.h:5064`–`:5083`、`:5100`–`:5108`；驱动侧组装在 `kernel:drivers/infiniband/hw/mlx5/qp.c:3573`（`mlx5_set_path_udp_sport`）与 `ah.c:35`（`mlx5_ah_get_udp_sport`，static、内核侧）。

### Q32. CQ 深度怎么定？

原则：**CQ 的条目数（`max_cqe`）必须 ≥ 所有共享这个 CQ 的 QP 的「最大在途 WR 总数」**，否则会出现 CQ overrun，触发 `IBV_EVENT_CQ_ERR`，并且**共享该 CQ 的所有 QP 会一起失效**。计算方式：`CQ 深度 ≥ Σ(每个 QP 的 max_send_wr + max_recv_wr)`，再留 10%–20% 余量；如果用 `sq_sig_all = 0` 或 `IBV_SEND_SIGNALED` 抽样，可以按「实际会产生的 CQE 数」算而不是按 WR 数算。另一个反直觉的点：**CQ 太大不一定好**——它占内存、也拉低 cache 命中率，够用即可。

→ 详见 [第 4 章](../04-verbs-model.md)（§4.3.4）

### Q33. `inline` 和 `post_list` 该怎么配？

`inline` 与 `post_list` 优化的是**不同**的东西，不要混为一谈：**`IBV_SEND_INLINE` 省的是 PCIe 读**——把数据直接拷进 WQE，硬件不用再去 DMA 读一遍，所以对**小消息**（几十~几百字节）的时延改善最明显；副作用是数据在 `ibv_post_send()` 返回时已被拷贝，**发送缓冲区可以立即复用**。**`post_list`（perftest `-l/--post_list`）省的是门铃次数**——一次 `ibv_post_send` 连成链投递多条 WR，用一次门铃驱动多条 WQE，对**吞吐**改善明显。经验值：小消息时延场景开 `inline`（上限用 `-I/--inline_size`），大吞吐场景加大 `post_list` 并配合 `sq_sig_all = 0`。

→ 详见 [第 13 章](../13-performance.md)（§13.4）与 [第 6 章](../06-perftest.md)（§6.2）

### Q34. 时延测试为什么必须关变频、绑 NUMA？

因为 perftest 的时间基准是 **TSC 周期数**（`cycles_t`，换算需要知道 CPU 频率）：CPU 频率一变，周期→微秒的换算就失准，而且变频本身会引入唤醒延迟，把尾延迟（P99/P999）抬得很高。所以标准动作是三步：① `cpupower frequency-set -g performance`（关变频）；② 关深 C-state（避免唤醒延迟）；③ `numactl --cpunodebind=N --membind=N` 或直接用 perftest 的自动绑定，让**进程、内存、网卡在同一个 NUMA 节点**。漏掉第 ③ 步是最常见的「时延测出来比论文大 3 倍」的原因。

→ 详见 [第 13 章](../13-performance.md)（§13.5）

### Q35. 怎么判断瓶颈在网络还是主机？

用**分段对照**而不是猜。核心方法是「换一个维度看同一个指标是否等比例变化」：

| 现象 | 指向 |
|---|---|
| `-q 1` 是 `-q 4` 的 1/4 | **网络侧 ECMP 单路径**（加 QP 就能救） |
| 加 QP 不变、加消息尺寸才涨 | **主机侧**：PCIe 宽度/速率不足、NUMA 跨节点、内存带宽瓶颈、CPU 打满 |
| `LnkSta` 的 Speed/Width 低于 `LnkCap` | **PCIe 插槽问题**（插在 x8 槽上） |
| 网卡所在 NUMA 与进程/内存不同 | **NUMA 错配**（`numactl` 验证） |
| 内存带宽 < 网卡带宽 × 2（读+写） | 内存本身是瓶颈 |

先跑 `ib_write_bw -a -F --report_gbits` 做尺寸扫描，再跑 `-q 4` 和 `numactl` 两组对照，三张表一比结论就出来了。

→ 详见 [第 12 章](../12-troubleshooting.md)（§12.7、§12.9）

### Q36. perftest 报出来的 BW/LAT 数字怎么读才不被骗？

四个陷阱：① **单位**——`--report_gbits` 才是 Gb/s（线速单位），默认是 MiB/s；perftest 自己的帮助里明确写了 `MiB = 2^20 byte` 而 `Gb = 10^9 bit`，并给出 `Factor=10^9/(2^20*8)=119.2`，即**两个单位相差 119.2 倍**（注意别写成「差 8%」——8% 只是 GiB(2^30) 与 GB(10^9) 之间的差，与这里的 MiB/Gb 换算无关；`perftest:src/perftest_parameters.c:714`–`:715`）。② **LAT 报的是半程**——SEND/WRITE 系工具把测得的 RTT 折半输出，所以看到的是 one-way 时延；**READ/ATOMIC 类测试 `rtt_factor = 1`，不折半**（`perftest:src/perftest_parameters.c:5108`）。③ **`-s` 与 `-n` 的默认值不同**——BW 默认 `65536` 字节；迭代次数默认 `1000`，其中 **WRITE/WRITE_IMM 的 BW 测试是 `5000`**（`DEF_ITERS_WB`，`perftest:src/perftest_parameters.h:106` + `perftest_parameters.c:1024`–`:1025`）；LAT 默认 `2` 字节，不显式给参数时两者的「典型值」不可比（默认值定义在 `perftest:src/perftest_parameters.h:103`–`:113`）。④ **`-a` 扫描时每个尺寸使用「相同」的迭代次数**（就是默认或 `-n` 给的那个值，perftest 不会按尺寸缩放；`perftest:src/write_bw.c:348`–`:352` 的 RUN_ALL 循环里 `iters` 不变），所以曲线抖动不代表性能抖动。做对比实验时永远**只改一个变量**。

> `perftest:src/perftest_parameters.h:100`–`:114`（默认值定义）、`:87`（`VERSION_EXIT`）以及 `perftest_parameters.c` 的 usage 文本（`:714` 附近解释单位换算）。

---

## G PFC-ECN-拥塞

### Q37. PFC 和 ECN 都必须开吗？

**是的，两个都要开，但它们职责不同、不能互相替代。** PFC 是**保底机制**：队列快满时发 PAUSE，用「停发」换「不丢包」——它是无损的最后一道闸，但它会造成队头阻塞甚至死锁。ECN + DCQCN 是**主动机制**：队列还没满就标记 CE，让发送端提前降速，**尽量避免 PFC 被触发**。只开 PFC 不开 ECN，会出现「PFC 频繁触发 → 反压扩散 → 一旦成环就全网死锁」的最坏情形；只开 ECN 不开 PFC，遇到微突发（microburst）时来不及降速就直接丢包，RC 重传导致长尾延迟飙升。

→ 详见 [第 11 章](../11-lossless-tuning.md)（§11.1）

### Q38. `--tclass` 该填多少？

填**完整的 IP TOS 字节**，也就是 **DSCP << 2**。perftest 的帮助原文是 "Set the Traffic Class in GRH (if GRH is in use)"，它被写进 `ah_attr.grh.traffic_class`（`perftest:src/perftest_resources.c:3552`），驱动再原样搬进 AV：`ah->av.tclass = grh->traffic_class`（`kernel:drivers/infiniband/hw/mlx5/ah.c:68`）。所以：规划里说「RoCE 走 DSCP 26」，就填 `26 << 2 = 104`（即 `0x68`），抓包应看到 `tos 0x68`。**注意低 2 位是 ECN 字段，由驱动自己设置**——RoCEv2 时驱动会 `ah->av.tclass |= MLX5_ECN_ENABLED`（`BIT(1)`，即 IP 的 ECT(0)，`ah.c:88`–`:89`），所以不要自己往低 2 位塞值，否则会破坏 ECN 语义。

> `kernel:drivers/infiniband/hw/mlx5/ah.c:68`、`:88`–`:89`；`perftest:src/perftest_resources.c:3552`。

### Q39. Kmin / Kmax / Pmax 该怎么定？

它们定义的是**交换芯片队列的 ECN 标记曲线**：队列长度 < `Kmin` 不标记；`Kmin`–`Kmax` 之间按概率线性标记，到 `Kmax` 时概率达 `Pmax`；超过 `Kmax` 全标记（或开始丢弃）。定值的三条经验：① **`Kmin` 要大于「一条链路的 BDP + 微突发」**，太小会让 ECN 过度触发、把速率长期压在低位；② **`Kmax` 与 `Pmax` 决定降速的陡峭程度**，`Pmax` 太低则反馈太弱（DCQCN 反应不过来）、太高则速率震荡；③ **全网交换机必须一致**，否则流量在不同跳上受到不同策略，表现为「路径相关的性能差异」。**必须结合交换芯片的实际 buffer 大小来算**，照搬别人的数字几乎一定会出问题。

→ 详见 [第 11 章](../11-lossless-tuning.md)（§11.4）

### Q40. DCQCN 参数在哪里改？为什么只有 debugfs？

**在 mlx5 上，驱动侧唯一的 DCQCN 配置入口就是 debugfs**——本驱动**没有 verbs 级的 DCQCN 配置接口**。目录由 `mlx5_ib_init_cong_debugfs()` 创建在设备 debugfs 根下的 `cc_params/`（`kernel:drivers/infiniband/hw/mlx5/cong.c:432`，目录名在 `:456`），**且只有固件能力 `cc_query_allowed` 与 `cc_modify_allowed` 同时为真才存在**（`:446`）。参数共 **22 个**（`cong.c:44`–`:67`），分三组：`rp_*`（发送端 Reaction Point，16 个）、`np_*`（接收端 Notification Point，4 个）、`rtt_resp_dscp*`（2 个）。**注意 22 是上限**：`rtt_resp_dscp_valid` / `rtt_resp_dscp` 这两个文件要求固件同时具备 `roce` 与 `roce_cc_general` 能力（`cong.c:459`–`:463`），不满足时会被 `continue` 跳过——所以部分固件下 `cc_params/` 里只有 20 个文件。修改经 `MLX5_CMD_OP_MODIFY_CONG_PARAMS` 下发固件（`cong.c:351`–`:352`）。

> `kernel:drivers/infiniband/hw/mlx5/cong.c:44`–`:67`（参数名表）、`:432`–`:473`（debugfs 建立）、`:351`（固件命令）。

### Q41. 怎么证明 PFC / ECN 配置真的生效了？

看**计数器**而不是看配置回显。四组关键指标：

| 指标 | 在哪里读 | 健康值 / 判读 |
|---|---|---|
| `tx_prio3_pause` / `rx_prio3_pause` | `ethtool -S <netdev>` 或 `mlnx_qos -i` | 非 0 说明 PFC 在工作：`tx` 是「本端发 PAUSE（对端发太快）」，`rx` 是「收到 PAUSE（本端发太快）」。计数器名格式是 `rx_prioN_pause`/`tx_prioN_pause`（`kernel:drivers/net/ethernet/mellanox/mlx5/core/en_stats.c:1992`–`:1995`） |
| `np_ecn_marked_roce_packets` | `ethtool -S` / 硬件计数器 | 非 0 说明 ECN 在标记；**持续增长说明链路长期拥塞** |
| `roce_slow_restart_cnps` | 同上 | 与 CNP 联动，判断是偶发还是持续过载 |
| `roce_adp_retrans` / `roce_adp_retrans_to` | 同上 | **必须为 0**；非 0 说明网络在丢包，无损没配好 |

再加一条端到端证据：`tcpdump -i <netdev> -nn 'udp port 4791' -v` 逐包看 `tos` 是否等于你规划的 DSCP（如 `tos 0x68`）。

→ 详见 [第 11 章](../11-lossless-tuning.md)（§11.6）

### Q42. PFC 死锁是怎么发生的？

死锁的本质是**反压形成环路 + 网卡无限等待**。典型剧本：交换机 A 的出口队列满 → 向 B 发 PAUSE → B 因为不能发而内部 buffer 也满 → B 向 C 发 PAUSE → …… 一旦拓扑里有环路（或某种流量模式等价于环），PAUSE 就会互相等待，形成「我等你、你等我」，**整条链路甚至全网停摆**。两层防护缺一不可：① **交换机侧 `pfcwd`（PFC Watchdog）**：检测到某队列长时间 PAUSE 就自动 bypass（丢弃/转发）该队列，牺牲一个优先级保全网；② **网卡侧 `device_stall_watermark`**：`mlx5_set_port_stall_watermark()`（`kernel:drivers/net/ethernet/mellanox/mlx5/core/port.c:537`）设一个水位，超过后网卡**主动丢包**而不是无限等待——这是「宁可丢包也不能全网死锁」的工程折中。**它用的是 `MLX5_REG_PFCC` 寄存器**（`:541` 准备 `pfcc_reg`，`:550`/`:552` 填 `device_stall_critical_watermark` / `device_stall_minor_watermark`，`:555` 下发）；`MLX5_REG_PPTB` 与停顿水位无关，它只用于「优先级 → 端口缓冲」的映射（`kernel:drivers/net/ethernet/mellanox/mlx5/core/en/port.c:249` 的 `mlx5e_port_set_priority2buffer`）。

→ 详见 [第 11 章](../11-lossless-tuning.md)（§11.8）与 [第 8 章](../08-mlx5-provider.md)（§8.10）

---

## H 排障

### Q43. `Failed to modify QP to RTR` 该怎么查？

这是 RoCE 最高频的报错，按「信息是否给全」的顺序查：

| 检查项 | 命令 / 判据 |
|---|---|
| GID 选对了吗 | `show_gids`：必须是 `VER = v2` + 业务 IP 那一行的 INDEX（对应 perftest `-x`） |
| 对端 QPN / PSN 拿到了吗 | 带外握手是否成功交换了 `qp_num`；`IBV_QP_DEST_QPN`、`IBV_QP_RQ_PSN` 是否随 mask 一起给了 |
| MTU 一致吗 | 两端 `ibv_devinfo ... active_mtu` 与 `-m` 参数；netdev MTU 是否够（按内核 `iboe_get_mtu()` 的 **96 字节**折算，要得到 4096 的 RoCE MTU 需要 netdev MTU ≥ **4192**；设成 4154 只会得到 2048） |
| 邻居解析成功了吗 | 先 `ping` 通；`ib_resolve_eth_dmac()` 解析 DMAC 失败会直接失败（`kernel:drivers/infiniband/core/verbs.c:1798`） |
| 端口状态 | `ibv_devinfo -d <dev> -v \| grep -E 'state\|phys_state'`：必须 `PORT_ACTIVE` / `LINK_UP` |

顺序上先排除前三项（占 90%），再查邻居与端口。

→ 详见 [第 12 章](../12-troubleshooting.md)（§12.4、§12.5）

### Q44. 带宽只有预期的一半，怎么分段定位？

用「比例法」三步定位，每步都做 A/B 对照：

1. **先算比例**：如果 `-q 4` 的带宽 ≈ 4 × `-q 1`，那就确诊是**网络侧 ECMP 单路径**（一个 QP 只用一条路径），不是主机问题。
2. **排除主机**：`lspci -vv -s <BDF> | grep -E 'LnkCap\|LnkSta'` 对比 Speed/Width 是否一致（插在 x8 槽上会让 200 Gb/s 卡只能跑一半）；`numactl --hardware` + `cat /sys/class/infiniband/<dev>/device/numa_node` 确认网卡 NUMA 节点与进程/内存一致。
3. **再看网络深度**：`-q 4` 能到 96% 线速而 `-q 1` 只有 1/4，说明「主机没问题、路径数不够」，根因要么是交换机 ECMP 哈希没包含 L4 源端口，要么是应用把 `flow_label` 写死导致源端口熵为 0。

最后一步是长期方案：让网络团队把 ECMP 哈希改成包含 L4 源端口（`kernel:include/rdma/ib_verbs.h:5077` 表明 sport 由 `flow_label` 派生，所以哈希必须含 UDP sport 才能获益）。

→ 详见 [第 12 章](../12-troubleshooting.md)（§12.9）与 [第 13 章](../13-performance.md)（§13.2）

### Q45. `roce_adp_retrans` 不是 0，说明什么？

说明**网络正在丢包、RC 层在超时重传**——这直接证伪了「网络是无损的」。可能原因按概率：① PFC 没在正确的优先级上生效（DSCP→prio 映射或 trust mode 配错，导致 RoCE 流量落在了没开 PFC 的队列）；② ECN 阈值配得太激进，或根本没开 ECN，微突发直接触发丢包；③ 链路误码（`ethtool -S` 看 CRC/err 计数）；④ 交换机 buffer 太小、incast 场景下必然溢出。**处置顺序**：先用 `tcpdump` 确认 DSCP 是否落在规划的优先级上，再看 `prio*_pause_*` 计数是否与 `roce_adp_retrans` 同步增长，最后才去调 Kmin/Kmax。

→ 详见 [第 11 章](../11-lossless-tuning.md)（§11.8）

### Q46. 怎么知道是哪个进程在用 RDMA 资源？

用内核的 **restrack**（资源追踪）机制，它记录「哪个 QP/MR/CQ 属于哪个进程」：`kernel:drivers/infiniband/core/restrack.c` 是数据源，驱动侧命名在 `kernel:drivers/infiniband/hw/mlx5/restrack.c`。用户态通过 RDMA netlink 读取（`nldev.c` 提供底座），命令形如 `rdma res show qp` / `rdma res show mr` / `rdma res show ctx`，输出行带 `pid` 与 `comm` 字段。**这在三种场合特别有用**：① 排查「谁把 `max_mr` 用光了」；② 安全审计（哪个进程注册了多少内存）；③ 容器多租户场景下确认配额是否被执行。

> `kernel:drivers/infiniband/core/restrack.c`；`kernel:drivers/infiniband/core/nldev.c`；第 16 章 §16.2。

### Q47. 抓包该在哪抓、看什么字段？

**在 netdev 上抓，不在 ibdev 上抓**——RoCE 流量走的是以太网口，所以 `tcpdump -i <netdev> ...`（用 `rdma link show` 确认绑定关系）。过滤条件是 **`udp port 4791`**（RoCEv2 的唯一标识）。要看的字段按排查目的分：

| 目的 | 字段 |
|---|---|
| 确认是 RoCEv2 | 目的端口 4791；`-X` 看 BTH 的 opcode |
| 确认 QoS 生效 | IP `tos`（DSCP 左移 2 位后的值，如 DSCP 26 → `0x68`） |
| 确认源地址正确 | 源 IP 是否业务 IP（即 `sgid_index` 指向的 GID） |
| 确认 ECMP 熵 | **UDP 源端口**是否落在 `0xC000`–`0xFFFF`（`kernel:include/rdma/ib_verbs.h:5064`）且随 QP 变化 |
| 确认 MTU | 帧长是否接近 netdev MTU；出现分片即说明 MTU 不够 |

导出 pcap 后用 Wireshark 打开会自带 RoCEv2 解析器，比纯文本直观得多。

→ 详见 [第 2 章](../02-rocev2-protocol.md)（§2.9）

### Q48. 网络看起来一切正常，但性能抖动很大，看什么？

抖动（而非均值低）的排查重点与「带宽不够」完全不同，看四类指标：① **ECN/PFC 计数的时间序列**——`np_ecn_marked_roce_packets` 与 `prio*_pause_*` 是否在抖动期间同步飙升（说明拥塞在发生）；② **重传计数**——`roce_adp_retrans` 非 0 就直接定位到丢包；③ **主机侧干扰**——CPU 频率是否被别的负载拉走、中断是否集中在少数核上、是否有其他进程在抢 PCIe/内存带宽（`perf`、`mpstat -P ALL`）；④ **交换机侧**——同一时刻其他端口的 PFC 计数（判断是不是「别人拥塞、你被 PAUSE」）。**方法论要点**：抖动必须用「同时段采样」而不是「事后看累计值」，累计计数器看不出抖动。

→ 详见 [第 11 章](../11-lossless-tuning.md)（§11.6）与 [第 13 章](../13-performance.md)（§13.6）

---

## I 安全

### Q49. `rkey` 泄露有多严重？

**等价于内存泄露**：任何拿到 `remote_addr + rkey` 的人，只要网络可达，就能用 RDMA READ 把这块内存完整读走、或用 RDMA WRITE 覆盖它——**远端 CPU 完全不参与，也不会产生任何内核日志**。更糟的是它对权限位的依赖：如果那块 MR 同时给了 `IBV_ACCESS_REMOTE_WRITE`，攻击者不只能读还能改（比如改配置文件、改数据库页）。所以纪律是硬的：`rkey` 按敏感信息对待——不写日志、不进错误信息、抓包文件按机密管理、示例代码里用占位符。

→ 详见 [第 14 章](../14-security.md)（§14.1、§14.2）

### Q50. RDMA 流量怎么加密？

主流有三条路：① **MACsec**（802.1AE，链路层加密）——mlx5 有卸载支持（`kernel:drivers/infiniband/hw/mlx5/macsec.c`），粒度是「每一跳链路」，能保住 RDMA 性能，但**每个中间设备都要解密**；② **IPsec** ——粒度是端到端，但卸载能力与吞吐取决于网卡，且大量小包场景下开销明显；③ **应用层自加密**——数据在进 MR 之前就加好密（NVMe-oF 的 in-band 加密、TLS 之上的 RDMA 传输都属于这类），最灵活但要求应用配合。注意「RDMA 本身就是零拷贝直通内存」，所以任何加密都必须解决「密钥与卸载引擎在哪」的问题，不能指望中间的软件层去做。

→ 详见 [第 14 章](../14-security.md)（§14.3）

### Q51. 容器/多租户怎么隔离 RoCE？

四层都要做，缺一层就漏：① **设备隔离**——只把分配给该租户的 uverbs 节点（或 VF 对应的节点）给容器，**绝不要把全部 `/dev/infiniband/uverbs*` 一起给**；② **资源配额**——用 **RDMA cgroup**（`kernel:drivers/infiniband/core/cgroup.c`）限制 `rdma` 子系统的资源类型与数量，否则一个 Pod 能把全机 QP/MR 用光；③ **内存限额**——容器默认的 `RLIMIT_MEMLOCK` 很小，`ibv_reg_mr` 会直接 `ENOMEM`（`kernel:drivers/infiniband/core/umem.c:224`–`:231`），要显式抬高或给 `CAP_IPC_LOCK`；④ **身份绑定**——用 SR-IOV VF 让每个租户有独立的设备与独立的 `rkey` 空间，配合 network namespace 把 GID 也隔离掉。

→ 详见 [第 15 章](../15-virtualization.md)（§15.5）与 [第 14 章](../14-security.md)（§14.4）

### Q52. 怎么审计「谁注册了多少 MR」？

后台数据来自 **restrack**（`kernel:drivers/infiniband/core/restrack.c`），用户态读法就是 `rdma res show mr`（每个 MR 一行，带归属进程）与 `rdma res show ctx`（每个 ucontext）。做运维审计的实践是：① 定期采集并**存 JSON**（便于自动解析）而不是只看文本；② 按进程聚合统计 MR 数量与总注册内存，做趋势监控——**MR 数量单调上升通常意味着泄漏（忘了 `ibv_dereg_mr`）**；③ 出现异常时结合 `pid`/`comm` 直接定位到进程。合规场景下这套数据就是「谁在什么时候注册了哪块内存」的证据链。

> `kernel:drivers/infiniband/core/restrack.c`；第 14 章 §14.6、第 16 章 §16.5。

### Q53. PFC 风暴也算安全问题吗？

算，而且是**最严重的一类**——因为它能把故障从「一个端口」放大到「全网瘫痪」。机制是：恶意或异常流量持续触发某个优先级的 PFC，PAUSE 沿着链路传播并与正常流量互相反压，一旦形成环路就是全网死锁。防护手段是交换机侧的 **`pfcwd`（PFC Watchdog）**：检测到某队列长时间处于 PAUSE 状态就自动 bypass 该队列（丢弃或转发），**牺牲一个优先级以保全网**。所以「PFC 只对 RoCE 优先级开启」+「pfcwd 已启用」是 RoCE 部署的强制清单项，不是可选项。

→ 详见 [第 14 章](../14-security.md)（§14.3）与 [第 11 章](../11-lossless-tuning.md)（§11.8）

### Q54. 为什么不能只靠 PKey / QKey 做鉴权？

因为它们的定位是**「分区/粗粒度匹配」而不是「认证」**：`PKey` 类比 VLAN ID，只要 BTH 里的 `pkey` 与接收端的分区表匹配就放行；`QKey` 是 UD QP 上的 32 位字段，发送端 `ibv_send_wr.wr.ud.remote_qkey` 与接收 QP 的 `qkey` 匹配即通过。两者都是**明文、可枚举、可伪造**的——网络里任何人只要能发 UD 包，就可以试出 `QKey` 然后把伪造的 SEND 投进你的 RQ。真正的安全边界是：**MR 的 `rkey` + 访问权限位 + PD 隔离 + VF/namespace 隔离**，`PKey`/`QKey` 只应被当作「防误投递」的健壮性手段。

> `kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:463`（`struct rxe_deth` 承载 `qkey` 与 `sqp`）；`rdma-core:libibverbs/verbs.h:1213`–`:1217`（`wr.ud.remote_qkey`）。

---

## J 源码与进阶

### Q55. `ibv_post_send` 到底有没有进内核？

**没有。** 在 rdma-core 里它就是一个 `static inline`：`static inline int ibv_post_send(struct ibv_qp *qp, struct ibv_send_wr *wr, struct ibv_send_wr **bad_wr) { return qp->context->ops.post_send(qp, wr, bad_wr); }`（`rdma-core:libibverbs/verbs.h:3630`–`:3634`）——**不存在 `__ibv_post_send` 这类弱符号**，它纯粹是一次虚函数跳转。对 mlx5 来说，`ops.post_send` 指向 `mlx5_post_send`（`rdma-core:providers/mlx5/qp.c:1158`），后者在用户态把 `ibv_send_wr` 组装成 WQE 写进 QP 缓冲、再敲 UAR 门铃。所以**整个数据面是「用户态构造 + 一次 MMIO 写」**，内核只是在创建 QP/CQ/MR 时参与。

> `rdma-core:libibverbs/verbs.h:3630`；`rdma-core:providers/mlx5/qp.c:1158`；第 9 章 §9.3。

### Q56. 从 `ibv_post_send` 到固件命令，完整链路是什么？

要把「数据面」和「控制面」分开看：

| 阶段 | 链路 |
|---|---|
| **控制面（走内核一次）** | `ibv_create_qp` → `ibv_cmd_create_qp`（`rdma-core:libibverbs/cmd_qp.c`）→ ioctl/`UVERBS_METHOD_QP_CREATE`（新）或 write/`IB_USER_VERBS_CMD_CREATE_QP`（旧，`ib_uverbs.ko`）→ `mlx5_ib_create_qp`（`kernel:drivers/infiniband/hw/mlx5/qp.c`）→ `mlx5_qpc_create_qp`（`qpc.c:246`，发 `MLX5_CMD_OP_CREATE_QP`）→ `mlx5_core` 命令队列（`cmd.c`）→ 固件 |
| **数据面（不进内核）** | `ibv_post_send` → `mlx5_post_send` / `_mlx5_post_send`（`providers/mlx5/qp.c:804`）→ 按 `wqe.h` 布局写 WQE（单位是 64 字节的 WQEBB）→ 敲门铃（UAR / BlueFlame）→ 硬件 DMA 读 WQE 并组包发出 |

对照读第 7 章（内核 uverbs 分发）与第 8 章（mlx5 数据路径）就能把两条链完整串起来。

> `kernel:drivers/infiniband/hw/mlx5/qpc.c:246`；`rdma-core:providers/mlx5/qp.c:804`、`:1158`。

### Q57. mlx5 的 QP 固件命令在哪个文件？（常见错误纠正）

在 **`kernel:drivers/infiniband/hw/mlx5/qpc.c`**，不在 `drivers/net/ethernet/mellanox/mlx5/core/`。创建走 `mlx5_qpc_create_qp()`（`qpc.c:246`，发 `MLX5_CMD_OP_CREATE_QP`），销毁走 `mlx5_core_destroy_qp()`。**本内核树中不存在 `drivers/net/ethernet/mellanox/mlx5/core/qp.c`，也不存在 `mlx5_core_create_qp()`**——这类说法来自二手资料的混淆。`mlx5_core` 只提供命令通道（`cmd.c`）与 CQ/PD/MR/UAR/EQ 等共享资源；QP 语义与固件命令归 `mlx5_ib`。

> `kernel:drivers/infiniband/hw/mlx5/qpc.c:246`；另见 [`repo-map.md`](repo-map.md) §2.6 的「一个容易搞错的事实」。

### Q58. 用户态是怎么直接敲门铃的？

三步：① **建 context 时拿到 BF 寄存器信息**——`alloc_ucontext` 分配 BF 池（`kernel:drivers/infiniband/hw/mlx5/main.c`），并通过 `struct mlx5_ib_alloc_ucontext_resp` 的 `bf_reg_size`、`tot_bfregs`、`num_uars_per_page`（`kernel:include/uapi/rdma/mlx5-abi.h:137`/`:138`/`:155`）告诉用户态。**注意别写成 `bf_regs_per_page`——那是 mlx4 的字段**（`rdma-core:kernel-headers/rdma/mlx4-abi.h:59`）；mlx5 的 ucontext 响应里没有它，mlx5 用户态只在 provider 内部结构里有同名私有成员（`rdma-core:providers/mlx5/mlx5.h:326`）。② **mmap 把 UAR 映射进用户态**——`struct mlx5_ib_alloc_ucontext_resp` 与 mmap 命令枚举配合，偏移编码常量是 `MLX5_IB_MMAP_CMD_SHIFT = 8` / `MLX5_IB_MMAP_CMD_MASK = 0xff`（`kernel:drivers/infiniband/hw/mlx5/mlx5_ib.h:113`–`:114`）；③ **发 WQE 时写 UAR**——普通门铃是写一个小记录，**BlueFlame（BF）则把最多 256 字节的 WQE 直接写进寄存器区**，硬件从这次写里就把 WQE 收走了，省掉一次 PCIe DMA 读。用户态侧的对象指针由 DV 暴露：`mlx5dv_init_obj()` 会填出 `mlx5dv_qp` 的 `bf`、`.dbrec`、`.sq`、`.rq`（`rdma-core:providers/mlx5/mlx5dv.h:876`–`:899`）——**`struct mlx5dv_qp` 里没有 `.cq`**，CQ 相关的 `buf`/`dbrec`/`cqe_cnt`/`cqn` 等字段在另一个结构体 `struct mlx5dv_cq`（`:901`–`:909`）里。

> `rdma-core:providers/mlx5/mlx5dv.h`（`mlx5dv_qp`）；`kernel:drivers/infiniband/hw/mlx5/main.c`（`alloc_ucontext`）；第 8 章 §8.6、第 9 章 §9.4。

### Q59. DV 和 DR 分别解决什么问题？

两者都属于「绕过 libibverbs 通用层的加速接口」，但**加速的位置完全不同**：

| 接口 | 全称 | 加速什么 | 典型用途 |
|---|---|---|---|
| **DV** | Direct Verbs | **数据面每次 post 的软件开销**：直接拿到 `bf`/`dbrec`/`sq`/`rq`/`cq` 裸指针，自己组 WQE | 极致低时延的自研 verbs 程序 |
| **DR** | Direct Rules | **控制面的流表编程**：用户态直接把 flow steering 规则下发硬件流表（Steiner 表项编码、ICM 池） | OVS/DPDK 卸载、用户态防火墙、多租户流策略 |

**一个重要的性能澄清**：DV **不改变硬件路径**，它省的是 CPU 周期（少一层函数调用与状态检查），不是「让包走得更快」。所以「用了 DV 带宽就能翻倍」是误解——翻倍通常来自多 QP 与 ECMP。

> `rdma-core:providers/mlx5/mlx5dv.h`、`mlx5dv_dr.h` 与 `dr_*.c`；第 9 章 §9.4、§9.5。

### Q60. 想读代码，从哪里开始？

按「一条链路走到底」的方式读，比按目录漫游有效得多。推荐顺序：

1. **数据面**：`rdma-core:libibverbs/verbs.h` 的 `ibv_post_send`（`:3630`）→ `rdma-core:providers/mlx5/qp.c` 的 `mlx5_post_send`（`:1158`）→ `_mlx5_post_send`（`:804`）→ `rdma-core:providers/mlx5/wqe.h` 与 `mlx5_ifc.h`（WQE 位域）。
2. **控制面**：`rdma-core:libibverbs/cmd_qp.c` → `kernel:drivers/infiniband/core/uverbs_std_types_qp.c`（`UVERBS_METHOD_QP_CREATE`）→ `kernel:drivers/infiniband/hw/mlx5/qp.c` 的 `mlx5_ib_create_qp` → `qpc.c` 的 `mlx5_qpc_create_qp`。
3. **报文格式**：`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h`——所有扩展头（BTH/RETH/DETH/AETH/IMMDT/IETH/ATMETH/ATMACK/RDETH/FETH）的字段布局都在这里，逐字节可信。
4. **GID 与地址**：`kernel:drivers/infiniband/core/roce_gid_mgmt.c` + `cache.c` + `verbs.c` 的 `ib_resolve_eth_dmac()`（`:1798`）。
5. **应用层范例**：`rdma-core:tests/`（C 语言 API 范例）与 `rdma-core:pyverbs/tests/`（几十行 Python 就能建 QP、注册 MR、跑一次 send/recv）。

每读一个 `ibv_*` 调用，就沿着「应用 → libibverbs → `cmd_*.c` → `uverbs_*.c` → `mlx5_ib` → `mlx5_core`」写到纸上——做 5 次就有架构直觉了。

> [`repo-map.md`](repo-map.md) §5「一页速查」与 §6「使用本图的两个练习」；第 9 章 §9.7。

---

## 相关文件

- 核心术语与四组对比小表：[`glossary.md`](glossary.md)
- 版本、ABI 边界与兼容性矩阵：[`versions-and-abi.md`](versions-and-abi.md)
- 代码导航总图（所有 `kernel:` / `rdma-core:` / `perftest:` 路径的地图）：[`repo-map.md`](repo-map.md)
- 写作与引用约定：[`00-conventions.md`](00-conventions.md)
- 按主题速查取值（QP 状态迁移表、传输类型能力表、异步事件总表、opcode、AETH syndrome、MTU 算式）：[`glossary-quickref.md`](glossary-quickref.md)
- 实验环境搭建与第一次测试：[实验 1](../labs/lab01-environment-and-first-test.md)
