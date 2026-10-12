# RoCE / RDMA 核心术语表

本文件是这套教程的**精选（curated）术语表**，与 [`glossary-quickref.md`](glossary-quickref.md) 的分工是：

- **本文件（`glossary.md`）** 是**按术语组织的解释版**：只收录能在本教程锁定的三个源码快照（[`repo-map.md`](repo-map.md)）与第 1–16 章正文中找到依据的术语；定义按「RoCE 学员视角」重写，措辞与正文统一；每条术语都给出 `→ 见第 N 章` 的章节交叉引用，方便你从词跳到讲解。
- **[`glossary-quickref.md`](glossary-quickref.md)** 是**按主题组织的取值版**：面向「写代码 / 排障 / 对抓包时快速查一个确定取值」——QP 状态迁移掩码、异步事件类型、WC 状态码、opcode、AETH syndrome、CM 事件、MTU 与开销算式，全部以表格 / 位域图 / 短算式呈现。
- 两份文件**不冲突**：本文件解释「这个词是什么意思」，速查表回答「这个常量到底等于多少」。两者都以同一套源码快照为依据，取值以速查表为准。
- 版本与 ABI 号一律以 [`00-conventions.md`](00-conventions.md) 第 1 节为准：**Linux 7.2.8 / rdma-core 66.0（`IBVERBS_PABI_VERSION 65`）/ perftest 6.30**。

**使用方式**：先按主题分区找词（第 1–8 节），遇到容易混淆的成对概念直接看第 9 节的四张**对比小表**，最后用第 10 节的**字母序索引**反查。正文里的代码位置一律写成 `kernel:` / `rdma-core:` / `perftest:` + 相对路径 + 行号（约定见 [`00-conventions.md`](00-conventions.md) 第 2 节）。

---

## 1. 传输与协议

### 1.1 技术族与总体概念

**RDMA（Remote Direct Memory Access，远程直接内存访问）**
在不涉及远端 CPU 的前提下直接读写远端内存的技术族。它同时做到三件事：**零拷贝**（数据不进内核缓冲区）、**内核旁路**（数据面不经过内核）、**CPU 卸载**（远端不产生接收中断与协议处理）。
→ 见第 1 章

**RoCE（RDMA over Converged Ethernet，融合以太网上的 RDMA）**
把 InfiniBand 的传输层（IB Transport）跑在以太网上的 RDMA 实现，因此它保留 IB 的 QP/WQE/CQE 语义与全部扩展头，只替换二层/三层封装。RoCE 有两代：v1 走二层、v2 走 UDP/IP。
→ 见第 1、2 章

**RoCEv1**
把 IB 传输头直接封装在以太网帧里，以太网类型（EtherType）为 `0x8915` 的**二层协议**。因为不带 IP 头，**不可路由、不能跨三层**，现代数据中心几乎不再部署。
→ 见第 1、2 章

**RoCEv2**
把 IB 传输头封装进 **UDP/IP**（IPv4 或 IPv6），目的 UDP 端口固定 **4791**，因此**可路由、可跨三层、可被 ECMP 哈希**。生产环境说的「RoCE」默认指 RoCEv2。
→ 见第 1、2 章

**iWARP（Internet Wide Area RDMA Protocol）**
另一种以太网 RDMA：把 RDMA 语义实现在 **TCP（或 SCTP）之上**（由 IETF 标准化），因此天然可靠、可跨广域，但需要支持 DDP/MPA 的网卡，且与 IB verbs 的对象语义有差异（例如没有 UD、没有 GRH）。本教程的 `siw` 是它的软件实现。
→ 见第 1、3 章

**InfiniBand（IB，无限带宽）**
定义 verbs 抽象、QP 状态机、传输服务类型与扩展头格式的**原生互连架构标准**（由 IBTA 维护）。RoCE 复用了它的传输层，只是把链路层换成以太网；`IB_QPT_*`、`IBV_QP_*` 这些前缀就是这段历史的痕迹。
→ 见第 1、2 章

**Verbs（verbs 接口 / 动词接口）**
对网络适配器能力的**抽象描述**：应用通过 verbs 创建与管理使用 RDMA 所需的全部对象（context、PD、MR、CQ、QP、AH…）。术语本身是名词（这套接口），单数小写形式 **verb** 指其中一个具体操作（如 `ibv_post_send` 就是一个 verb）。
→ 见第 4 章

**verb（单个动词操作）**
Verbs 接口中的**一个具体函数**。注意 `verbs` 是接口整体、`verb` 是单个操作、`Verbs API` 是与 `RDMA_CM API` 相对的那一层「QP 级原语」——三者在中文里都常被译成「动词」，但指的不是一回事。
→ 见第 4 章

**IB Transport（IB 传输层）**
IB 体系里负责可靠传输、序号、确认、重传与拥塞标记的那一层。RoCE 不重新定义它，只把它的报文封装到以太网/UDP 里，所以 **BTH/AETH 的字段语义在 IB 与 RoCE 中完全一致**。
→ 见第 2 章

### 1.2 报文头（Base / Extended Transport Header）

**BTH（Base Transport Header，基本传输头）**
**每一个** IB/RoCE 报文都有的 12 字节头，是本层唯一的「必备头」。字段（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:61`，掩码定义同文件 `:69`–`:82`）：

| 字段 | 宽度 | 说明 |
|---|---|---|
| `opcode` | 1 B | 操作码，决定这个包是 SEND / WRITE / READ 请求还是响应 |
| `flags` | 1 B | 位域：`SE`（Solicited Event，bit7）、`MIG`（迁移，bit6）、`Pad`（bit5–4）、`TVer`（传输头版本，bit3–0，当前为 0） |
| `pkey` | 2 B | 分区键（默认 `0xffff`，即默认分区） |
| `qpn` | 4 B | 目的 QPN（低 24 位）；**高 2 位是 `FECN`/`BECN` 拥塞标记位** |
| `apsn` | 4 B | 高 1 位是 `A`（ACK 请求位）；低 24 位是 `PSN`（包序号） |

→ 见第 2 章

**RETH（RDMA Extended Transport Header，RDMA 扩展头）**
用于 **RDMA WRITE / RDMA READ 请求**，把「远端虚拟地址 + rkey + 长度」告诉对端。布局为 `va`(8 B) + `rkey`(4 B) + `len`(4 B)，共 16 字节（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:526`）。
→ 见第 2、4 章

**DETH（Datagram Extended Transport Header，数据报扩展头）**
**UD QP 专用**，携带 `qkey` 与源 QPN（`sqp`，低 24 位有效）（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:463`）。UD 没有连接，所以每个包都必须自带「我是谁、我属于哪个 QKey」。
→ 见第 2、5 章

**RDETH（Reliable Datagram Extended Transport Header）**
**可靠数据报（RD）/XRC 类**服务使用的扩展头，携带 EEC 号（`een`）（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:428`）。注意 **DC 报文不带 RDETH**（DC 属动态连接，RDETH 是 RD/XRC 类的语义）——**「RD/XRC 类」这个归属是 IBTA 规范级结论，三个源码仓库不能最终裁定**：本树中 rxe 只定义该结构体、自述不支持 RD 传输（`rxe_hdr.h:42`–`:44`）。RoCE 日常几乎用不到，但读 mlx5 代码时会遇到 XRC/DC 分支。
→ 见第 2、8 章

**AETH（ACK Extended Transport Header，确认扩展头）**
所有 **ACK/NAK** 报文携带，4 字节，高 8 位是 **syndrome（SYN）**、低 24 位是 **MSN**（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:773`、`:780`）。SYN 取值决定这是 ACK 还是 NAK 以及 NAK 的原因（`:782`–`:790`）：`AETH_ACK = 0x00`、`AETH_RNR_NAK = 0x20`、`AETH_NAK = 0x60`、`AETH_ACK_UNLIMITED = 0x1f`、`AETH_NAK_PSN_SEQ_ERROR = 0x60`、`AETH_NAK_INVALID_REQ = 0x61`、`AETH_NAK_REM_ACC_ERR = 0x62`、`AETH_NAK_REM_OP_ERR = 0x63`。
→ 见第 2 章

**IMMDT（Immediate Extended Transport Header，立即数扩展头）**
4 字节立即数（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:885`）。只有 `*_WITH_IMM` 类操作码才有；它**不占用接收缓冲区**，而是作为「带内通知」把 32 位数据送给对端。
→ 见第 2、4 章

**IETH（Invalidate Extended Transport Header，失效扩展头）**
携带一个待失效的 `rkey`（4 字节），用于 `SEND_WITH_INV` / `WRITE_WITH_INV` 类操作（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:918`）。典型用途是「把远端那块 MR 的钥匙收回来」。
→ 见第 2、14 章

**FETH（FLUSH Extended Transport Header，冲刷扩展头）**
4 字节，用于持久内存的 flush 类操作，携带 PLT（placement type，bit3–0）与 SEL（selectivity level，bit5–4）（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:618`、`:619`）。**注意**：FETH 不是流控头（流控靠 PFC/ECN/CNP），它的 F 是 FLUSH。
→ 见第 2 章

**ATMETH（Atomic Extended Transport Header，原子操作扩展头）**
原子操作请求头，含 `va`(8 B) + `rkey`(4 B) + `swap_add`(8 B) + `comp`(8 B)（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:662`）。`FETCH_AND_ADD` 只用 `swap_add`，`CMP_AND_SWP` 同时用 `comp` 与 `swap_add`。
→ 见第 2、4 章

**ATMACK（Atomic ACK，原子确认扩展头）**
原子操作响应携带，8 字节，内容是操作前内存里的**原值**（`orig`）（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:852`）。这就是 `FETCH_AND_ADD` / `CMP_AND_SWP` 能「返回旧值」的物理来源。
→ 见第 2、4 章

**GRH（Global Routing Header，全局路由头）**
基于 IPv6 格式的 40 字节全局头，用于**跨子网**投递与**组播**投递。RoCEv2 里外层已有真实 IP 头，GRH 主要承载 SGID/DGID 与流标签等 IB 语义字段。
→ 见第 2、7 章

**LRH（Local Routing Header，本地路由头）**
IB 原生链路层的 8 字节本地路由头，含 `dlid`/`slid` 等。**RoCE 上不存在 LRH**——这也正是 RoCE 里 `lid` 字段没有意义、必须靠 `dgid` 定位对端的原因。
→ 见第 2、7 章

**ICRC（Invariant CRC，不变式校验）**
报文尾部的 4 字节校验（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:55`，`RXE_ICRC_SIZE = 4`）。它与以太网 FCS 不是一回事：ICRC 覆盖的是**端到端不变字段**（传输层头 + 净荷中不随路由改变的部分），因此能在报文穿过交换机后仍校验端到端完整性；RoCEv2 中可变字段（IPv4 TTL、Traffic Class、UDP checksum 等）不参与计算。
→ 见第 2 章

### 1.3 序号、确认与拥塞标记

**PSN（Packet Sequence Number，包序号）**
**每个包**的 24 位序号，位于 BTH 的 `apsn` 低 24 位（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:82`、`:264`）。发送端每发一个包 PSN 加一，接收端据此检测丢包、乱序与重复；ACK/NAK 里回带的也是 PSN。
→ 见第 2、5 章

**MSN（Message Sequence Number，消息序号）**
**每条消息**的 24 位序号，位于 AETH 的低 24 位（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:778`、`:809`）。它按「消息」递增而不是按「包」递增，所以一条跨多包的大消息只消耗一个 MSN。
→ 见第 2 章

**MSN 与 PSN 的区别（必须分清）**
**PSN 是包级、MSN 是消息级**：1 条 8 KB 消息在 1 KB MTU 下会产生 8 个 PSN，但只占 1 个 MSN。PSN 用于丢包检测与重传定位（BTH），MSN 用于让接收端知道「哪些消息已经完整收到、可以产生 CQE」（AETH）。
→ 见第 2 章

**ACK / NAK（确认 / 否认）**
RC 连接上接收端的反馈：ACK 表示包已按序收到（`AETH_ACK = 0x00`，或 `AETH_ACK_UNLIMITED = 0x1f` 表示「暂时无上限」）；NAK 表示需要重传，带具体原因（PSN 序列错误 / 非法请求 / 远端访问错误 / 远端操作错误，`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:786`–`:790`）。
→ 见第 2、12 章

**RNR NAK（Receiver Not Ready NAK，接收方未就绪否认）**
一种**特殊的 NAK**（`AETH_RNR_NAK = 0x20`）：连接正常、但接收侧 **RQ 里没有可用的 RR**。它不是错误而是流控信号——发送端按 `min_rnr_timer` 退避后重试，重试次数上限由 `rnr_retry` 决定；超过上限就报 `IBV_WC_RNR_RETRY_EXC_ERR`。
→ 见第 2、4、12 章

**CNP（Congestion Notification Packet，拥塞通知包）**
由接收端网卡的 **NP（Notification Point）** 回发给发送端的**独立小包**，用于告诉发送端「你的流量在路上被 ECN 标记过，请降速」。它是 RoCEv2 拥塞控制闭环的反馈通道，与 ACK/NAK 走同一条 RC 连接但语义完全不同。
→ 见第 2、11 章

### 1.4 传输服务类型（Transport Type）

**RC（Reliable Connection，可靠连接）**
面向连接的可靠服务：一个 QP 只与另一个 QP 配对，硬件保证**不丢、不重、保序**，并支持**全部操作**（SEND/RECV、RDMA WRITE、RDMA READ、原子）。RoCE 生产环境的主力（NVMe-oF、NCCL 等默认RC）。
→ 见第 1、4 章

**UC（Unreliable Connection，不可靠连接）**
同样面向连接（一个 QP 对一个 QP），但**不执行可靠协议**，消息可能丢失。能力上比 RC 少了 RDMA READ 与原子操作。
→ 见第 1、4 章

**UD（Unreliable Datagram，不可靠数据报）**
无连接、一条消息一个包（受 Path MTU 限制）、不保证送达与顺序。它是**唯一支持组播**的服务类型，用 `AH` 指定目的地址、用 `QKey` 做轻量校验。常用于发现、心跳、MAD/GSI 管理面。
→ 见第 1、4、5 章

**XRC（eXtended Reliable Connection，扩展可靠连接）**
让**一个发送 QP（XRC_SEND）可以向多个远端 XRC_SRQ（XRC_RECV）发送**的扩展服务类型，用 SRQ + XRC domain 把「接收侧 QP 数量」从 O(N²) 降到 O(N)。代价是 API 更复杂，且两侧都要显式使用 XRC 类型。
→ 见第 1、4 章

**DC / DCT（Dynamic Connection / Dynamic Connection Target，动态连接）**
IB 的「动态连接」服务类型：发送侧用 **DCI**、接收侧用**共享的 DCT**，让一个节点无需为每个对端建一条 QP 即可与大量对端通信（类似 XRC 的进一步演进）。`DCT` 是接收端的共享目标对象，RoCE 上支持情况取决于驱动与固件。
→ 见第 1、8 章

**RAW_PACKET（原始包 QP）**
一种特殊 QP 类型（`IBV_QPT_RAW_PACKET = 8`，`rdma-core:libibverbs/verbs.h:936`）：verbs 层不做任何封装，**由应用自己构造以太网/IP/UDP/VXLAN 等头部**，网卡只负责收发。它是理解 RoCEv2 报文格式的最佳实验台，也是 DPDK/OVS 卸载这类场景的基础（perftest 的 `raw_ethernet_*` 系列、`mlx5dv_create_qp` 都用它）。
→ 见第 4、6、8 章

**RD（Reliable Datagram，可靠数据报）**
IB 标准中定义的可靠数据报服务类型，能力上支持全部 RDMA 操作、最大消息 1 GB。它出现在传输类型能力对比表中，但 RoCE 上几乎不用；看到 `RD` 列时知道它是 IB 原生服务即可。
→ 见第 1 章

### 1.5 操作（Operations）

**RDMA WRITE（单边写）**
**单边操作**：发起方直接把数据写入远端已注册内存，**远端不消耗 RR、不产生 CQE、其 CPU 完全不参与**。请求带 RETH（远端地址 + rkey + 长度），响应只是一个 ACK。
→ 见第 1、4 章

**RDMA READ（单边读）**
**单边操作**：发起方从远端已注册内存读数据到本地。它同样不消耗远端 RR，但**需要响应包携带数据**，因此往返次数与响应包数量都比 WRITE 多，时延通常更高。
→ 见第 1、4 章

**SEND / RECV（双边消息）**
**双边操作**：发送方 `ibv_post_send(IBV_WR_SEND)`，接收方**必须事先** `ibv_post_recv` 一条 RR，硬件把数据写进 RR 描述的缓冲区并在接收侧产生一个 CQE。消息边界由硬件保持（不是字节流）。
→ 见第 1、4 章

**WRITE_WITH_IMM（带立即数的 RDMA WRITE）**
`IBV_WR_RDMA_WRITE_WITH_IMM`：写数据的同时携带 4 字节 `imm_data`。**关键坑**：它会**消耗对端一个 RR**（因此对端必须 post recv），并在对端产生带 `IBV_WC_WITH_IMM` 的 CQE；这与普通 RDMA WRITE 完全不同。
→ 见第 4 章

**Atomic（原子操作：`CMP_AND_SWP` / `FETCH_AND_ADD`）**
由网卡在远端内存上**原子完成**的 64 位读改写：`IBV_WR_ATOMIC_CMP_AND_SWP` 比较相等才替换，`IBV_WR_ATOMIC_FETCH_AND_ADD` 返回旧值并累加。两者都返回操作前的原值（ATMACK 扩展头），且要求远端 MR 具备 `IBV_ACCESS_REMOTE_ATOMIC` 权限。仅 RC/RD 支持。
→ 见第 4 章

**OpCode（操作码）**
BTH 的第一个字节，唯一决定「这个包是什么」。它区分请求/响应、SEND/WRITE/READ/ATOMIC、以及有无 IMM/INV 后缀。抓包排查时第一眼看的就是它。
→ 见第 2 章

**MAD / GSI / SMI（管理数据报 / 通用服务接口 / 子网管理接口）**
IB 的管理面：`MAD` 是管理数据报格式，`SMI`（QP0）与 `GSI`（QP1）是承载它的特殊 QP。RoCE 中管理面主要被 `ibstat`/`saquery`/`ibacm` 一类工具使用，普通数据面程序不会碰它。
→ 见第 7、16 章

---

## 2. 对象与资源

**QP（Queue Pair，队列对）**
把**发送队列（SQ）**与**接收队列（RQ）**打包在一起的对象，是 RDMA 传输的发起与终结单元。每个 QP 有唯一的 `QPN`、自己的状态机、自己的 PSN 空间；RC/UC 还绑定一个对端 QP。
→ 见第 4、8 章

**SQ（Send Queue，发送队列）**
QP 中存放用户所 post 的 **SR（Send Request）**的工作队列。`ibv_post_send` 往这里投递。
→ 见第 4 章

**RQ（Receive Queue，接收队列）**
QP 中存放用户所 post 的 **RR（Receive Request）**的工作队列。`ibv_post_recv` 往这里投递；RTR 状态后才能被处理。
→ 见第 4 章

**SRQ（Shared Receive Queue，共享接收队列）**
一个可以被**多个 RC/UC/UD QP 共享**的接收队列：任一关联 QP 收到消息都从同一个 SRQ 取 RR。它在「接收缓冲区需求极不均衡」的场景（如大量空闲连接）下能省下大量内存，代价是必须处理 `IBV_EVENT_QP_LAST_WQE_REACHED` 与 SRQ limit 事件。
→ 见第 4 章

**WQ（Work Queue，工作队列）**
SQ 或 RQ 的统称，是「WR 排队等待硬件处理」的地方。
→ 见第 4 章

**WQE（Work Queue Element，工作队列元素）**
工作队列中的一个**硬件可见元素**（读作 "wookie"），是 WR 在硬件里的具体编码形式。用户态 verbs 把 `ibv_send_wr` 翻译成 WQE 写进 QP 的发送缓冲，再敲 doorbell 通知硬件。
→ 见第 4、8、9 章

**WQEBB（WQE Basic Block，WQE 基本块）**
mlx5 硬件把发送 WQE 空间按 **64 字节**为单位切分，一个 WQEBB 就是这 64 字节（`rdma-core:providers/mlx5/mlx5dv.h:1277`，`MLX5_SEND_WQE_BB = 64`；配套的移位常量 `MLX5_SEND_WQE_SHIFT = 6` 在同文件 `:1278`）。一条 WQE 由若干 WQEBB 组成，`ctrl` 段里的 `ds`（数据段数）字段就是按 16 字节为单位统计的长度。
→ 见第 8、9 章

**WR（Work Request，工作请求）**
用户 post 到工作队列上的**请求**（软件视角），由 `struct ibv_send_wr` / `struct ibv_recv_wr` 描述。它进入队列后就变成硬件侧的 WQE。
→ 见第 4 章

**SR（Send Request，发送请求）**
post 到 **SQ** 上的 WR，描述要传多少数据、方向、以及用哪个 opcode 传。
→ 见第 4 章

**RR（Receive Request，接收请求）**
post 到 **RQ** 上的 WR，描述「用 send opcode 的入向数据要写到哪里」。**注意**：带立即数的 RDMA WRITE（`WRITE_WITH_IMM`）也会消耗一个 RR。
→ 见第 4 章

**Outstanding Work Request（未完成工作请求，在途 WR）**
已投递到工作队列、但其完成事件**尚未被 poll 到**的 WR。在途 WR 的数量直接受 `max_send_wr`/`max_recv_wr`（创建 QP 时声明）与 CQ 深度约束，是「SQ 溢出」与「CQ 溢出」两类故障的根源。
→ 见第 4、12 章

**CQ（Completion Queue，完成队列）**
存放 **CQE** 的 FIFO 队列。多个 QP 可以共享一个 CQ；CQ 是数据面唯一的「结果出口」，用户态直接轮询它（`ibv_poll_cq`）。
→ 见第 4、8 章

**CQE（Completion Queue Entry，完成队列条目）**
CQ 中的一个条目，描述某个已完成 WR 的信息：状态、`wr_id`、`opcode`、`byte_len`、`qp_num`、`src_qp`、`wc_flags`、`imm_data`/`invalidated_rkey` 等。用户态看到的是它的软件视图 `struct ibv_wc`。
→ 见第 4、8 章

**WC（Work Completion，工作完成）**
用户态对 CQE 的软件视图：`struct ibv_wc`（`rdma-core:libibverbs/verbs.h:593` 起）。`ibv_poll_cq()` 返回的每一条就是一个 WC。
→ 见第 4 章

**WC status code（完成状态码）**
`enum ibv_wc_status`（`rdma-core:libibverbs/verbs.h:489`）。`IBV_WC_SUCCESS` 之外，最常遇到的几个与它们的含义：

| 状态码 | 含义 / 典型原因 |
|---|---|
| `IBV_WC_SUCCESS` | 成功 |
| `IBV_WC_LOC_ACCESS_ERR` | 本地访问违例（MR 权限不足，例如没开 `IBV_ACCESS_LOCAL_WRITE` 却收数据） |
| `IBV_WC_LOC_LEN_ERR` | 收到的消息超过 RR 缓冲区长度 |
| `IBV_WC_LOC_PROT_ERR` | 本地保护错误（常见于 lkey 用错/失效） |
| `IBV_WC_REM_ACCESS_ERR` | 远端访问违例（rkey 权限不足或地址越界） |
| `IBV_WC_REM_INV_REQ_ERR` | 远端认为请求非法（RQ 未就绪、opcode 与 QP 类型不匹配等） |
| `IBV_WC_REM_OP_ERR` | 远端操作错误 |
| `IBV_WC_RNR_RETRY_EXC_ERR` | RNR 重试次数耗尽（对端 RQ 一直没有 RR） |
| `IBV_WC_RETRY_EXC_ERR` | 重传次数耗尽（对端无响应/网络不通） |
| `IBV_WC_WR_FLUSH_ERR` | QP 进入 ERROR 后被冲刷掉的 WR（不是真错误，是连带结果） |
| `IBV_WC_RESP_TIMEOUT_ERR` | 响应超时 |
| `IBV_WC_BAD_RESP_ERR` | 收到不符合预期的响应包 |
| `IBV_WC_MW_BIND_ERR` | Memory Window 绑定失败 |
| `IBV_WC_GENERAL_ERR` | 其他未分类错误 |

完整枚举共 24 个值（同文件 `:489`–`:513`）。排障口诀：**先看 `status`，再按 `LOC_*` / `REM_*` 分成「我这边的问题」和「对端的问题」**。
→ 见第 4、12 章

**EQ（Event Queue，事件队列）**
硬件/驱动把**中断事件**排入的队列。CQ 以 `cqn` 为键挂在 EQ 上，`mlx5_eq_comp_int()` 在中断里取出事件再调度 tasklet。理解 EQ 才能理解「中断 → tasklet → 唤醒用户态」这条通知链，也才能理解为什么低延迟程序干脆不用中断、直接轮询。
→ 见第 8 章

**PD（Protection Domain，保护域）**
一种**隔离域**：只有同一 PD 内的组件才能互相作用——AH 与 QP 交互、MR 与 WQ 交互都受 PD 约束。创建 QP 时指定的 PD 决定了它「能看见」哪些 MR，这是 verbs 层最基础的访问控制。
→ 见第 4、14 章

**MR（Memory Region，内存区域）**
**已注册并带访问权限**的一段内存。注册时内核把它 pin 住并映射成 DMA 地址，同时生成 `lkey`（本地用）与 `rkey`（远端用）。网卡只能访问已注册内存——这是 RDMA 安全模型的基石。
→ 见第 4、14 章

**MW（Memory Window，内存窗口）**
绑定到**既有 MR 内部某段区域**后才能提供远端访问的资源，每个 MW 有自己的 Window Handle、权限集合与**当前 rkey**。它的价值在于「不改动原 MR 的前提下，动态发放/回收一小段远端可访问权限」。
→ 见第 4、14 章

**AH（Address Handle，地址句柄）**
描述「通往远端的路径」的对象，**UD QP 每次发送都要显式提供**（因为 UD 无连接）。RoCE 场景下，AH 的实质就是把 `GID` 解析出的**目的 MAC / VLAN / GRH 字段**打包交给硬件；内核在 `ib_resolve_eth_dmac()`（`kernel:drivers/infiniband/core/verbs.c:1798`）里完成这步解析。
→ 见第 4、9 章

**AV（Address Vector，地址向量）**
驱动内部对 AH 的编码形式。在 mlx5 里就是 `struct mlx5_av`——RoCE 报头的「模板」，由 `create_ib_ah()` 填充（`kernel:drivers/infiniband/hw/mlx5/ah.c`）。UD QP 的每个 WQE 都带一个 AV 索引；RC 的路径信息则写进 QP context。
→ 见第 8、9 章

**ucontext / `ibv_context`（用户态设备上下文）**
`ibv_open_device()` 的产物，代表「这个进程对这个设备的会话」：持有 `cmd_fd`（打开 `/dev/infiniband/uverbsN` 得到的 fd）、`async_fd`（异步事件 fd）、`num_comp_vectors`、以及 provider 私有数据。
→ 见第 4、9 章

**QPN（QP Number，QP 号）**
QP 的唯一编号（24 位有效）。RC/UC 建连时必须把**自己的 QPN 告诉对端**（写进对端的 `dest_qp_num`），对端才能把包投递到正确的 QP。
→ 见第 4、5 章

**CQN（CQ Number，CQ 号）**
CQ 的唯一编号，用于把 CQE 归属到正确的 CQ，也是 CQ 挂到 EQ 上的键。
→ 见第 8 章

**DCT（Dynamic Connection Target，动态连接目标）**
DC 服务类型的接收端共享对象，一个 DCT 可以被大量 DCI 连接。参见第 1 节的 `DC / DCT`。
→ 见第 1 章

**XRCD（XRC Domain，XRC 域）**
XRC 的隔离单位：一个 XRC domain 内可以有多个 XRC_SEND QP 与一个 XRC_RECV（基于 SRQ）。创建时要显式指定 `xrcd`。
→ 见第 4 章

**uobject（内核用户对象）**
内核 uverbs 框架里「用户态对象」的抽象：PD/MR/CQ/QP 在内核侧都是一个 `ib_uobject`，有创建 → 提交 → 销毁的生命周期。生命周期核心在 `kernel:drivers/infiniband/core/rdma_core.c`（属于 **`ib_uverbs_support.ko`**）。
→ 见第 7 章

**mmap entry（mmap 条目）**
uverbs 允许把内核页（CQ 缓冲区、UAR/BF 寄存器页、doorbell record 页…）映射给用户态的机制。描述它的结构体 `struct rdma_user_mmap_entry` 见 `kernel:include/rdma/ib_verbs.h:2455`（**这是内核内部头，不是 uapi 头**——`include/uapi/rdma/rdma_user_mmap.h` 在内核与 rdma-core 中**都不存在**）；管理代码在 `kernel:drivers/infiniband/core/ib_core_uverbs.c`（属于 **`ib_core.ko`**）。
→ 见第 7、8 章

**comp_channel（完成事件通道）**
`ibv_create_comp_channel()` 创建的 fd，用于「不想轮询」的程序：`ibv_req_notify_cq()` 把 CQ 挂上通知，程序在 fd 上 `poll()`/`read()` 被唤醒后再去 `ibv_poll_cq()` 并 `ibv_ack_cq_events()`。注意它**只通知「有新 CQE」，不携带内容**。
→ 见第 4、9 章

**async fd（异步事件 fd）**
`ibv_context.async_fd`：异步事件（`IBV_EVENT_*`）的出口。用 `ibv_get_async_event()` 阻塞读取、`ibv_ack_async_event()` 确认。**每个 verbs 程序都必须处理它**，否则端口 down / QP fatal / GID change 这些事件会堆积。
→ 见第 4、7 章

**SRQ limit（SRQ 低水位）**
SRQ 上的一个阈值：可用 RR 数降到该值时触发 `IBV_EVENT_SRQ_LIMIT_REACHED`，提醒你补 post recv。
→ 见第 4 章

**ibv_poll_cq（轮询 CQ）**
`static inline int ibv_poll_cq(struct ibv_cq *cq, int num_entries, struct ibv_wc *wc)`（`rdma-core:libibverbs/verbs.h:3038`）：一次最多取 `num_entries` 条 WC，返回实际取到的条数。它**纯用户态轮询、不进内核**，是低延迟的关键；返回 0 表示当前没有新完成。
→ 见第 4、9、13 章

**ibv_req_notify_cq（请求完成通知）**
`static inline int ibv_req_notify_cq(struct ibv_cq *cq, int solicited_only)`（`rdma-core:libibverbs/verbs.h:3052`）：请硬件在**下一个**新 CQE 到来时发一次通知；`solicited_only != 0` 时只对带 Solicited 标记的完成通知（见 `IBV_SEND_SOLICITED`）。它是一次性武器，每次被通知后要重新 arm。
→ 见第 4、9 章

---

## 3. 内存与权限

**lkey（Local Key，本地密钥）**
MR 注册时返回、**只在本端 WQE 中使用**的编号，写在每条 SGE 里（`struct ibv_sge.lkey`）。硬件用它校验「这块内存在本地是否有权限访问、地址是否越界」。它**从不发给对端**。
→ 见第 4、14 章

**rkey（Remote Key，远端密钥）**
同一次 MR 注册返回的**另一个**编号，专门交给对端用于远端访问校验，出现在 RETH / ATMETH 里。**rkey 泄露等价于内存泄露**：拿到 `addr + rkey` 的任何人都能直接读写你的内存。
→ 见第 4、14 章

**QKey（Queue Key，队列键）**
UD QP 的轻量校验字段，位于 DETH（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:463`）。发送端 `ibv_send_wr.wr.ud.remote_qkey` 必须与接收 QP 的 `qkey`（或 SRQ 的 `qkey`）匹配，否则被丢弃。它是「共享 UD 通道上的粗粒度鉴权」，不是安全边界。
→ 见第 4、14 章

**PKey（Partition Key，分区键）**
标识端口所属**分区**的 16 位值，作用大致类比以太网的 VLAN ID；每个端口至少有一个由 SM 分配的 pkey。RoCE 场景下通常就是默认分区（`0xffff`），BTH 里的 `pkey` 字段即它。
→ 见第 2、5 章

**SGE（Scatter/Gather Element，分散聚集元素）**
指向本地已注册内存块**全部或一部分**的条目：起始地址 + 长度 + `lkey`（`struct ibv_sge`，`rdma-core:libibverbs/verbs.h:1177`）。一条 WR 可以带多个 SGE，硬件按顺序拼成一条数据流。
→ 见第 4 章

**S/G Array（分散聚集数组）**
WR 中的 SGE 数组。按 opcode 决定方向：发送时把多个缓冲区**收集（gather）**成一条流；接收时把一条流**分散（scatter）**写入多个缓冲区。
→ 见第 4 章

**MTT（Memory Translation Table，内存转换表）**
网卡用来把「虚拟地址 → 物理页」的映射关系存起来的表。注册大 MR 时 `mlx5_ib_populate_pas()`（`kernel:drivers/infiniband/hw/mlx5/mem.c`）把 umem 的页列表填成 PAS 数组再下给硬件。MTT 条目数（`max_mr`/`max_mtt` 相关能力）是 `ibv_reg_mr` 失败的一个常见原因。
→ 见第 7、8 章

**MPT / mkey（Memory Protection Table / 内存保护表与密钥）**
硬件侧的「MR 描述表」：每个 MR 一行，记录基址、长度、权限与 keys。创建/销毁走固件命令 `mlx5_core_create_mkey`（`kernel:drivers/infiniband/hw/mlx5/mr.c:106`）。
→ 见第 8 章

**FRWR（Fast Registration Work Request，快速注册 WR）**
用一条 WR 把**已经预留好的** MR 重新指向新内存并换取新 rkey 的机制（配合 `IBV_WR_LOCAL_INV` 回收），避免频繁走内核注册。内核通过 `mr_pool.c`/`frmr_pools.c` 池化支持它。
→ 见第 4、7 章

**UMR（User-Mode Memory Registration，用户态内存注册）**
允许在**用户态**完成内存键重映射的能力（源自截图转录的 Rev 1.7 修订记录）。mlx5 内核侧实现在 `kernel:drivers/infiniband/hw/mlx5/umr.c`。
→ 见第 7、8 章

**ODP（On-Demand Paging，按需缺页）**
让 MR 注册时**不必立刻 pin 住全部物理页**，而是等硬件真正访问到某一页时才触发缺页、由驱动补齐映射。它解决了大内存（几百 GB）注册时页表过大与 pin 住不放的问题，代价是首次访问的延迟与 `IBV_ACCESS_ON_DEMAND` 的额外要求。内核实现：`kernel:drivers/infiniband/core/umem_odp.c`、`kernel:drivers/infiniband/hw/mlx5/odp.c`。
→ 见第 7、8、13 章

**dma-buf**
Linux 的跨设备缓冲区共享框架。RDMA 用它注册**非 CPU 内存**（GPU 显存、加速器内存）：用户态走 `ibv_reg_dmabuf_mr()`，内核走 `kernel:drivers/infiniband/core/umem_dmabuf.c`，uAPI 里的载荷类型是 `IB_UVERBS_BUFFER_TYPE_DMABUF`（`kernel:include/uapi/rdma/ib_user_ioctl_verbs.h`）。
→ 见第 7、10 章

**GPUDirect RDMA**
让网卡与 GPU 显存**直接**交换数据、绕过主机内存与 CPU 拷贝的能力。对 verbs 程序来说就是「把显存当作一块 MR 注册」（走 dma-buf 或 `nvidia-peermem` 之类路径），perftest 的 `cuda_memory.c`/`rocm_memory.c` 等后端就是干这件事的。
→ 见第 7、10 章

**Device Memory（DM，设备内存）**
把**网卡上的内存**当作一块可注册、可 RDMA 访问的内存使用（`ibv_alloc_dm`、`kernel:drivers/infiniband/hw/mlx5/dm.c`）。用途是让「常驻的小数据结构」（如计数器、标志位）离网卡更近。
→ 见第 4、8 章

**`IBV_ACCESS_*`（MR 访问权限位）**
注册 MR 时声明的权限集合（`rdma-core:libibverbs/verbs.h:615`–`:626`）：`IBV_ACCESS_LOCAL_WRITE = 1`、`IBV_ACCESS_REMOTE_WRITE = 1<<1`、`IBV_ACCESS_REMOTE_READ = 1<<2`、`IBV_ACCESS_REMOTE_ATOMIC = 1<<3`、`IBV_ACCESS_MW_BIND = 1<<4`、`IBV_ACCESS_ZERO_BASED = 1<<5`、`IBV_ACCESS_ON_DEMAND = 1<<6`、`IBV_ACCESS_HUGETLB = 1<<7`、`IBV_ACCESS_FLUSH_GLOBAL = 1<<8`、`IBV_ACCESS_FLUSH_PERSISTENT = 1<<9`、`IBV_ACCESS_RELAXED_ORDERING = IBV_ACCESS_OPTIONAL_FIRST`。**最小权限原则**：远端只需要读就不要给 `REMOTE_WRITE`。
→ 见第 4、14 章

**`IBV_ACCESS_ZERO_BASED`（零基址）**
让 `rkey` 的相对地址从 **0** 开始计算，而不是从 MR 的绝对虚拟地址开始。作用是**不把本端虚拟地址泄露给对端**——对端只知道「偏移」。安全加固的常用手段。
→ 见第 4、14 章

**`IBV_ACCESS_RELAXED_ORDERING`（宽松排序）**
允许 PCIe 上的 Relaxed Ordering，通常能提升吞吐。但它是**可选**权限位（在 `IBV_ACCESS_OPTIONAL_RANGE` 范围内），老设备可能不支持，需要按「先试后降级」的方式使用。
→ 见第 4、13 章

**`IBV_ACCESS_HUGETLB`（大页）**
声明「这块 MR 覆盖的是大页」。使用大页能显著减少 MTT 条目数、提升 TLB 命中率，是延迟优化的常见手段。
→ 见第 13 章

**`RLIMIT_MEMLOCK`（可锁定内存限额）**
每个进程能 pin 住的内存上限。`ibv_reg_mr` 底层做 `pin_user_pages_fast` 时若超出 `RLIMIT_MEMLOCK >> PAGE_SHIFT` 就直接返回 `-ENOMEM`（`kernel:drivers/infiniband/core/umem.c:224`–`:231`）；容器场景要显式抬高它或给 `CAP_IPC_LOCK`。**这是「`ibv_reg_mr` 返回 ENOMEM」的第一大原因**。
→ 见第 7、15 章

**MSG_ZEROCOPY / 零拷贝（概念澄清）**
RDMA 的「零拷贝」指**应用缓冲区与网卡之间没有额外内存拷贝、且不经过内核协议栈**，而不是说「完全不碰内存」。数据仍然要被网卡 DMA 读/写，仍然要经过 PCIe。
→ 见第 1、13 章

---

## 4. 地址与路由

**GID（Global IDentifier，全局标识符）**
128 位标识符，用于标识网络适配器上的端口、路由器端口或**组播组**；它是一个合法的 128 位 IPv6 地址（RFC 2373），IBA 在其上追加了属性与限制。RoCEv2 中 GID 就承载着 IPv4/IPv6 地址。
→ 见第 2、4 章

**GID index（GID 索引）**
同一端口拥有**一张 GID 表**（多行），每行有索引。同一个 IP 通常会占两行（RoCEv1 一行、RoCEv2 一行），所以「选哪一行」是 RoCE 新手第一大坑。perftest 用 `-x/--gid-index=<index>` 指定（`rdma-core`/verbs 侧是 `ibv_qp_attr.ah_attr.grh.sgid_index`）。
→ 见第 2、6、12 章

**GID type（GID 类型）**
GID 表每行的类型，sysfs 里的字符串是 `"IB/RoCE v1"` 与 `"RoCE v2"`（`rdma-core:libibverbs/cmd_device.c:282`–`:283`，映射为 `IBV_GID_TYPE_SYSFS_IB_ROCE_V1` / `IBV_GID_TYPE_SYSFS_ROCE_V2`）。**RoCEv2 必须选 "RoCE v2" 的那一行**。
→ 见第 2、7 章

**SGID（Source GID，源 GID）**
本端使用的 GID（= `ah_attr.grh.sgid_index` 指向的那一行）。它同时决定了**源 IP**，抓包时核对「源 IP 是不是业务 IP」看的就是它。
→ 见第 2、9、12 章

**DGID（Destination GID，目的 GID）**
对端的 GID。**RoCE 场景必须给 DGID**（`dgid` 是 RoCE 的必备属性，而 `dlid` 只在 IB 链路层有意义）。
→ 见第 4、9 章

**MGID（Multicast Group ID，组播组 ID）**
IB 组播组由 MGID 标识，由 **SM** 管理：SM 为每个 MGID 关联一个 MLID，并显式配置 fabric 中的交换机，确保加入该组的所有端口都能收到报文。
→ 见第 2、7 章

**MLID（Multicast LID，组播 LID）**
SM 为每个 MGID 分配的组播 LID。**RoCE 上没有 LID 体系**，所以组播主要靠 GID 与 `rdma_cm` 的 `RDMA_CM_EVENT_MULTICAST_JOIN` 流程。
→ 见第 2、7 章

**LID（Local IDentifier，本地标识符）**
由子网管理器分配给端节点的 **16 位**地址，在子网内唯一。**RoCE 上不可用**——这正是 RoCE 必须靠 GID 定位对端的原因，也是「从 IB 迁移到 RoCE 的代码改动点」之一。
→ 见第 2、7 章

**GUID（Globally Unique IDentifier，全局唯一标识符）**
64 位、在子网内唯一标识一个设备或部件的编号。`ibv_device_attr.node_guid` / `sys_image_guid` 就是它。
→ 见第 3 章

**GID table（GID 表）**
端口上 GID 的有序列表，由 `ib_core` 的 `cache.c` 持有，内容由 `roce_gid_mgmt.c` 依据 netdev 的 **IP 与 VLAN** 增删（`add_netdev_ips`，`roce_gid_mgmt.c:429`；GID 表的建立与初始化则是 `cache.c:911` 的 `gid_table_setup_one`——本树中**没有** `gid_table_setup` 这个函数）。mlx5 只提供 `.add_gid`/`.del_gid` 回调把条目下发固件（`mlx5_core_roce_gid_set`，发 `MLX5_CMD_OP_SET_ROCE_ADDRESS = 0x761`，`kernel:drivers/net/ethernet/mellanox/mlx5/core/lib/gid.c`）。
→ 见第 3、7、8 章

**RoCEv2 UDP 目的端口 4791**
RoCEv2 的封装端口（IANA 分配）。抓包过滤条件就是它：`udp port 4791`。
→ 见第 2、12 章

**UDP source port entropy（UDP 源端口熵）**
RoCEv2 报文的**源** UDP 端口不是固定值，而是由发送方按 QPN 等参数派生（mlx5 内核侧 `mlx5_set_path_udp_sport()`；**用户态侧**是 `mlx5_ah_set_udp_sport()`（`rdma-core:providers/mlx5/verbs.c:3473`）与 `mlx5dv_modify_qp_udp_sport()`——`mlx5_ah_get_udp_sport()` 是**内核侧**函数（`kernel:drivers/infiniband/hw/mlx5/ah.c:35`），rdma-core 全树没有这个符号；能力协商看 `handle_hca_cap_roce` 的 `sw_r_roce_src_udp_port`）。**目的**：让交换机的 ECMP 哈希能把不同 QP 的流量散到不同路径上。
→ 见第 2、8、12、13 章

**flow label（流标签）**
GRH/IPv6 里的 20 位字段，也可参与 ECMP 哈希。perftest 的 `--flow_label` 可显式设置；应用侧若把它**写死成同一个值**，多 QP 的流量就会被哈希到同一条路径上，白白浪费多路径。
→ 见第 2、8、12、13 章

**hop limit（跳数上限）**
RoCEv2 报文的 IP TTL/Hop Limit 字段。它的取值必须足够大到能跨过整条路径——**太小**会导致大流量下随机丢包且难以定位（内核邻居解析会把它填进 GRH，`kernel:drivers/infiniband/core/verbs.c:834`）。**perftest 的 `--hop_limit` 仅 RawEth 可用**（普通 verbs 测试给了会直接 `exit(1)`）；verbs 路径上 perftest 把它**固定成 `0xFF`**（`perftest:src/perftest_resources.c:3551`）。
→ 见第 2、9、12 章

**traffic class（流量类别）**
RoCEv2 报文里的 IP TOS/DSCP 字段（RoCE 使用 GRH 的 Traffic Class 语义）。perftest 用 `--tclass=<value>` 设置，**必须与交换机上「DSCP → 优先级队列」的规划一致**，否则 PFC/ECN 都不会作用在你的流量上。**写 GRH `traffic_class` 的是 `--tclass`，不是 `--tos`**——`--tos`（`-T`）只在 `-R`（rdma_cm）或 RawEth QP 下合法，普通 verbs 测试给了它会打印 `TOS only valid for rdma_cm based QP and RawEth QP` 并 `exit(1)`（`perftest:src/perftest_parameters.c:1912`–`:1914`；`--hop_limit`/`-L` 同理，仅 RawEth 可用，`:1917`–`:1919`）。
→ 见第 2、11 章

**DSCP（Differentiated Services Code Point，差分服务代码点）**
IP 头 TOS 字节的高 6 位，是三层 QoS 的标记。RoCE 无损网络的标准做法是：**网卡信任 DSCP → 把某个 DSCP 映射到内部优先级（TC）→ 该优先级开 PFC + ECN**。
→ 见第 11 章

**PCP（Priority Code Point，优先级码点）**
VLAN 标签（802.1Q）里的 3 位优先级，是**二层** QoS 标记。网卡的 trust mode 可以设为信任 PCP 或信任 DSCP；RoCE 通常统一信任 DSCP，避免带不带 VLAN 时行为不一致。
→ 见第 11 章

**TC（internal traffic class，内部流量类别）**
网卡内部用来选择发送队列与 PAUSE 行为的优先级索引（0–7），由 DSCP/PCP 映射而来。`mlx5_set_port_pfc()` 就是按 TC 打开 PFC 的（`kernel:drivers/net/ethernet/mellanox/mlx5/core/port.c`，寄存器 `MLX5_REG_PFCC`）。
→ 见第 11 章

**VLAN**
以太网 802.1Q 标签。对 RoCE 的影响有两层：① 决定网卡是否用 PCP 做优先级；② **VLAN 子接口上的 IP 会生成对应的 GID**（`roce_gid_mgmt.c` 依据 netdev 的 IP/VLAN 增删 GID），所以「删掉一个 VLAN 子接口」会让某些 GID 消失、连接断开。
→ 见第 3、7、11 章

**MTU（Maximum Transfer Unit，最大传输单元）—— IB MTU**
IB/RoCE 语境下，MTU 指**一个端口能发送/接收的报文净荷（payload）最大长度，不含包头**。取值是固定的档位：`IBV_MTU_256/512/1024/2048/4096`（`rdma-core:libibverbs/verbs.h:368`–`:372`，对应 `enum ibv_mtu`）。它写进 QP 属性 `path_mtu`，两端必须一致。
→ 见第 2、5、13 章

**netdev MTU（网络设备 MTU）**
`ip link` 里看到的、以太网层面的**帧净荷**上限（含 RoCE 的 IB 头 + UDP/IP 头）。**两个数必须分清**：① **96 字节**是内核的换算预留（`iboe_get_mtu()` 减 `40+8+12+4+28+4`），它决定 `active_mtu`——要拿到 RoCE MTU 4096，IPv4 无 VLAN 需要 netdev MTU ≥ **4192**（实践建议直接设 4200；若按 58 字节算成 4154，4154−96=4058 仍只得到 `IB_MTU_2048`）。② **58 字节**是 RoCEv2/IPv4/无 VLAN 的真**线缆帧开销**（14 Eth + 20 IP + 8 UDP + 12 BTH + 4 ICRC），只用于**净荷效率**估算（带 VLAN 为 62，IPv6 为 78；单包 RDMA WRITE 还要多带 16 字节 RETH，故按 **74 字节**算，SEND 按 **58 字节**算）。**两者是不同的东西，必须同时核对**。
→ 见第 2、13 章

**jumbo frame（巨帧）**
把 netdev MTU 提到 1500 以上的以太网配置（常见 9000/9216）。RoCE 想用 4096 的 IB MTU 就必须依赖巨帧——**且要全网（含每一台交换机、每一条隧道）统一**，否则会出现「带宽上不去、包被分片」。
→ 见第 2、13 章

**ECMP（Equal-Cost Multi-Path，等价多路径）**
三层网络中把同一目的的多条等价路径利用起来的机制，靠对报文头字段做**哈希**选路。RoCEv2 的哈希输入通常包括**源/目的 IP + 源/目的 UDP 端口**；如果源端口不随 QP 变化（熵不足），**同一个 QP 的全部流量只会走一条路径**，这是「单 QP 跑不满带宽」的头号原因。
→ 见第 2、12、13 章

**Clos / Spine-Leaf（叶脊拓扑）**
现代数据中心的标准拓扑：每个 Leaf 上行到全部 Spine，任意两台主机之间有多条等价路径——这正是 ECMP 能与 RoCE 配合的前提，也是「多 QP 才能跑满带宽」的拓扑根源。
→ 见第 12、13 章

**incast（多打一）**
多个发送端同时向**同一个接收端**发送大量数据，导致接收端下行链路或网卡缓冲区瞬时拥塞。它是分布式存储/AI 训练中的典型流量模式，也是 PFC/ECN/DCQCN 要解决的核心问题。
→ 见第 11、13 章

**head-of-line blocking（队头阻塞）**
一个队列里的**头部**报文因为拥塞/PAUSE 停住时，后面的报文即使目的地不拥塞也必须等待。PFC 是按优先级队列做的，所以**只对 RoCE 优先级开 PFC** 可以把队头阻塞限制在这一个 TC 内，不至于影响同链路的其他业务。
→ 见第 11 章

**neighbor resolution（邻居解析：ARP / ND）**
RoCE 建 AH/QP 时需要的**目的 MAC 与 VLAN** 从哪来：由 `ib_core` 通过 netlink 向邻居子系统查询（用户态对应 `rdma-core:libibverbs/neigh.c`）。缓存过期/失败时会解析失败，表现为建连卡住或 `-ENODEV`。
→ 见第 9、12 章

**netdev ↔ ibdev 绑定**
`ibdev`（如 `mlx5_0`）是 verbs 设备名，`netdev`（如 `enp1s0f0`）是配 IP 的网口。两者不是靠名字对应的，**最可靠的查法是 `rdma link show` 输出的 `netdev` 列**，或者看 `/sys/class/infiniband/<dev>/ports/N/gid_attrs/ndevs/`。
→ 见第 3、16 章

**LAG（Link Aggregation，链路聚合）**
把多个物理口绑成一个逻辑口。对 RoCE 的意义在于 **RoCE LAG / bond**：绑定成功后驱动注册的 ibdev 名字会变成 `mlx5_bond_0` 这类（`kernel:drivers/infiniband/hw/mlx5/main.c` 的设备命名分支），且 LAG 事件会触发 GID 全量重建（`lag_event()` → `roce_del_all_netdev_gids()` + `rdma_roce_rescan_port()`）。约束：`mlx5_lag_is_roce_lag()` 要求**非 SR-IOV 且 legacy 模式**。
→ 见第 8、15 章

**RoCE LAG（RoCE 链路聚合 / bond）**
把多个物理口绑成一个逻辑 RDMA 设备，让 RoCE 流量在成员口之间分担与容错（内核 `kernel:drivers/net/ethernet/mellanox/mlx5/core/lag/lag.c`，IB 侧入口 `lag_event()`，`kernel:drivers/infiniband/hw/mlx5/main.c:3655`）。三个必须知道的约束：① **`mlx5_lag_is_roce_lag()` 要求非 SR-IOV 且 legacy 模式**；② LAG 状态变化会触发 **GID 全量重建**（`roce_del_all_netdev_gids()` + `rdma_roce_rescan_port()`）——这就是「绑了 bond 之后 `-x` 全变了」的原因；③ 绑定成功后设备名会变成 `mlx5_bond_0`。
→ 见第 8、15 章

**Multi-Plane（多平面）**
一块物理网卡向操作系统暴露**多个独立平面**（每个平面有独立的端口/资源），常见于 Multi-Host 形态。`mlx5_ib_get_plane_num()` 读取 `vport_ctx.num_plane`（`kernel:drivers/infiniband/hw/mlx5/main.c:3254`），多平面时设备名会带上子设备名。
→ 见第 15 章

---

## 5. 状态机与参数

**QP 状态机（`RESET → INIT → RTR → RTS`）**
QP 的硬件状态机，与 TCP 状态机**没有一一对应关系**。用户态枚举为 `enum ibv_qp_state`：`IBV_QPS_RESET`、`IBV_QPS_INIT`、`IBV_QPS_RTR`、`IBV_QPS_RTS`、`IBV_QPS_SQD`、`IBV_QPS_SQE`、`IBV_QPS_ERR`、`IBV_QPS_UNKNOWN`（`rdma-core:libibverbs/verbs.h:1083`）。
→ 见第 4、8 章

**RESET（复位）**
QP 刚创建时的状态，**不能收发任何东西**。要让它工作必须经 `ibv_modify_qp` 逐级迁移。
→ 见第 4、5 章

**INIT（已初始化）**
第一个可迁移到的状态：此时 QP 已经绑定端口/PKey/访问标志，可以 post 到 SQ，但**不会真正发出**（还没有对端信息）。必填属性：`IBV_QP_STATE`、`IBV_QP_PKEY_INDEX`、`IBV_QP_PORT`、`IBV_QP_ACCESS_FLAGS`。
→ 见第 4、5 章

**RTR（Ready To Receive，就绪接收）**
**RR 可以 post 并被处理**的状态。进入 RTR 必须提供路径信息：`IBV_QP_AV`、`IBV_QP_PATH_MTU`、`IBV_QP_DEST_QPN`、`IBV_QP_RQ_PSN`、`IBV_QP_MAX_DEST_RD_ATOMIC`、`IBV_QP_MIN_RNR_TIMER`。RoCE 下 `AV` 里的 `grh.dgid` 是必备的（`dlid` 无用）。
→ 见第 4、5 章

**RTS（Ready To Send，就绪发送）**
**SR 可以 post 并被处理**的状态，此时连接才真正可用。RTR→RTS 必填：`IBV_QP_TIMEOUT`、`IBV_QP_RETRY_CNT`、`IBV_QP_RNR_RETRY`、`IBV_QP_MAX_QP_RD_ATOMIC`。
→ 见第 4、5 章

**SQD（Send Queue Drain，发送队列排空）**
请求把 SQ 排空的状态：不再接受新的发送，等在途 WR 完成后产生 `IBV_EVENT_SQ_DRAINED`。它用于「有序停机」而不是错误处理。
→ 见第 4、8 章

**SQE（Send Queue Error，发送队列错误）**
SQ 进入错误子状态，通常伴随 QP 被置为 ERROR。实际排障时你更常看到的是 `IBV_QPS_ERR`。
→ 见第 8 章

**ERROR（`IBV_QPS_ERR`）**
出错状态：QP 上所有在途 WR 被冲刷（产生 `IBV_WC_WR_FLUSH_ERR`），不能再收发。**只能 modify 回 RESET 再重新迁移**才能复用（这就是为什么客户端要「重建 QP」而不是「修一下继续用」）。
→ 见第 4、12 章

**path migration（路径迁移）**
为 RC/UC 预置**备用路径**（`IBV_QP_ALT_PATH` + `IBV_QP_PATH_MIG_STATE`），主路径失效时硬件自动切到备用路径，产生 `IBV_EVENT_PATH_MIG` 或 `IBV_EVENT_PATH_MIG_ERR`。RoCE 上用得不多（因为路径选择交给 ECMP 了）。
→ 见第 2、4 章

**两层状态校验（two-layer validation）**
`ibv_modify_qp` 的合法性检查发生在**两处**：① 内核通用层 `ib_modify_qp_is_ok()` 用 `qp_state_table[][]` 判断（`kernel:drivers/infiniband/core/verbs.c:1462`、`:1763`）；② 驱动层 `mlx5_ib_modify_qp` 用 `opt_mask[][][]` 按「迁移边 + QP 类型」裁剪允许的 optpar（`kernel:drivers/infiniband/hw/mlx5/qp.c:3668`）。**「内核层过了、驱动层不过」是 `-EINVAL` 的经典来源。**
→ 见第 4、8 章

**`IBV_QP_*`（`ibv_qp_attr_mask` 位）**
`ibv_modify_qp` 的第三个参数，告诉内核「本次要改哪些字段」：`IBV_QP_STATE = 1<<0`、`IBV_QP_CUR_STATE = 1<<1`、`IBV_QP_EN_SQD_ASYNC_NOTIFY = 1<<2`、`IBV_QP_ACCESS_FLAGS = 1<<3`、`IBV_QP_PKEY_INDEX = 1<<4`、`IBV_QP_PORT = 1<<5`、`IBV_QP_QKEY = 1<<6`、`IBV_QP_AV = 1<<7`、`IBV_QP_PATH_MTU = 1<<8`、`IBV_QP_TIMEOUT = 1<<9`、`IBV_QP_RETRY_CNT = 1<<10`、`IBV_QP_RNR_RETRY = 1<<11`、`IBV_QP_RQ_PSN = 1<<12`、`IBV_QP_MAX_QP_RD_ATOMIC = 1<<13`、`IBV_QP_ALT_PATH = 1<<14`、`IBV_QP_MIN_RNR_TIMER = 1<<15`、`IBV_QP_SQ_PSN = 1<<16`、`IBV_QP_MAX_DEST_RD_ATOMIC = 1<<17`、`IBV_QP_PATH_MIG_STATE = 1<<18`、`IBV_QP_CAP = 1<<19`、`IBV_QP_DEST_QPN = 1<<20`、`IBV_QP_RATE_LIMIT = 1<<25`（`rdma-core:libibverbs/verbs.h:1041`–`:1069`；`1<<21`–`1<<24` 是历史上存在但从未由 libibverbs 暴露的位，见该处注释）。**mask 与实际字段不一致 = 状态迁移失败的头号原因。**
→ 见第 4、5 章

**`timeout`（本地 ACK 超时）**
RTS 时设置，决定「发出一个包后等多久没有 ACK 就触发重传」。取值是 4.096 µs × 2^timeout 的档位。**设得太小会造成大量无谓重传，设得太大则故障恢复慢**。
→ 见第 2、4、11 章

**`retry_cnt`（重传次数）**
同一条消息在收到 NAK/超时后重传的次数上限（0–7，7 表示无限）。耗尽后 QP 进入 ERROR 并报 `IBV_WC_RETRY_EXC_ERR`。
→ 见第 4、12 章

**`rnr_retry`（RNR 重试次数）**
收到 RNR NAK 后的重试次数上限（0–7，7 表示无限）。耗尽后报 `IBV_WC_RNR_RETRY_EXC_ERR`。**双边 SEND/RECV 程序必须把它设得足够大**，否则接收端稍有调度抖动就会把 QP 打挂。
→ 见第 4、12 章

**`min_rnr_timer`（RNR 最小退避定时器）**
收到 RNR NAK 后至少等待多久再重试。档位是 **0…31**，**取值本身对应一个 IB 定时器**（枚举名直接编码**毫秒**数）：`0 = 655.36 ms`、`12 = 0.64 ms`、`14 = 1.28 ms`、`31 = 491.52 ms`（`kernel:include/rdma/ib_verbs.h:1238`–`:1271` 的 `enum ib_rnr_timeout`）。rxe 以**微秒**存储同一组值再交给 `usecs_to_jiffies()`：`rnrnak_usec[IB_RNR_TIMER_000_64] = 640`（= 640 µs = 0.64 ms）、`[IB_RNR_TIMER_655_36] = 655360`，见 `kernel:drivers/infiniband/sw/rxe/rxe_comp.c:50`–`:88`。**perftest 默认给的是 12**（`MIN_RNR_TIMER`，`perftest:src/perftest_resources.h:96`）。它是「RNR 重试节流阀」。
→ 见第 4、12 章

**`max_rd_atomic`（本端在途 RDMA READ/Atomic 上限）**
本端作为**请求方**时，可以同时有多个 RDMA READ/Atomic 未完成的上限。它决定「读类操作的流水线深度」，直接影响 RDMA READ 的带宽。
→ 见第 4、13 章

**`max_dest_rd_atomic`（对端在途 RDMA READ/Atomic 上限）**
本端作为**响应方**时允许对端同时在途的 READ/Atomic 请求数。**建连时两侧必须匹配**：`A.max_rd_atomic ≤ B.max_dest_rd_atomic`，否则会出现 READ 报错或性能异常。
→ 见第 4、13 章

**`sq_sig_all`（全部发送都产生完成）**
**`struct ibv_qp_init_attr` 的成员**（`rdma-core:libibverbs/verbs.h:957`），也就是 **`ibv_create_qp` 时声明的属性**——它**不在 `struct ibv_qp_attr`**（`:1099`–`:1126`）里，因此**建 QP 之后不能再改，只能重建 QP**。为 1 时**每个** WR 都产生 CQE；为 0 时只有带 `IBV_SEND_SIGNALED` 的 WR 产生 CQE。批量发送场景把它设为 0、只对每 N 条打一个信号，能显著降低 CQ 压力（代价是错误发现变晚）。
→ 见第 4、13 章

**`inline`（内联发送）**
把数据**直接拷进 WQE**（而不是让网卡去 DMA 读），从而省掉一次 PCIe 读、降低小消息时延。上限由设备能力决定，用户态用 `IBV_SEND_INLINE`（逐 WR）或 QP 的 `cap.max_inline_data` 控制；perftest 用 `-I/--inline_size`。
→ 见第 4、9、13 章

**`post_list`（批量投递）**
一次 `ibv_post_send` 里连成链表投递的 WR 条数。perftest 用 `-l/--post_list` 设置，用少量 doorbell 换吞吐：**门铃次数减少 → 每包 CPU 开销降低**。
→ 见第 6、13 章

**`IBV_SEND_FENCE = 1 << 0`**
栅栏：保证这条 WR 之前的**所有** RDMA READ/Atomic 都已经完成，本条才开始执行。用于「先读回结果、再据此写」的依赖场景。注意它只作用于 READ/Atomic，对普通 SEND/WRITE 的排序无额外意义。
→ 见第 4 章

**`IBV_SEND_SIGNALED = 1 << 1`**
要求这条 WR 完成后**产生 CQE**。`ibv_qp_init_attr.sq_sig_all = 0` 时（`:957`；注意它不是 `ibv_qp_attr` 的成员，建 QP 后不能再改），只有带这个 flag 的 WR 才有完成事件——这是「批量发送、抽样确认」的核心开关。
→ 见第 4、13 章

**`IBV_SEND_SOLICITED = 1 << 2`**
置位后该消息的完成带 **Solicited** 标记：接收侧的 `ibv_req_notify_cq(cq, 1)` 只对这类消息通知；同时它对应 BTH 的 `SE` 位，会触发接收方一次事件。用于「请求-响应」模式里只关心响应的场景。
→ 见第 2、4 章

**`IBV_SEND_INLINE = 1 << 3`**
把这条 WR 的数据内联进 WQE（见上条 `inline`）。**重要副作用**：置位后 `ibv_post_send()` 返回时数据已被拷贝，**发送缓冲区可以立即复用**（`rdma-core:libibverbs/verbs.h:3627`）。
→ 见第 4、9 章

**`IBV_SEND_IP_CSUM = 1 << 4`**
要求硬件为 RAW_PACKET QP 的报文计算并填充 IP 校验和（`rdma-core:libibverbs/verbs.h:1159`）。只在自造报头的场景有意义。
→ 见第 4、6 章

---

## 6. 拥塞与无损

**PFC（Priority Flow Control，优先级流控）**
以太网 802.1Qbb 定义的**逐优先级 PAUSE**：接收方对某个优先级队列发 PAUSE 帧，发送方在该优先级上暂停发送，其他优先级不受影响。它把「丢包」换成「反压」，是 RoCE 无损的基础——**但 PFC 本身会造成队头阻塞与死锁风险**。
→ 见第 2、11、14 章

**PAUSE frame（PAUSE 帧）**
PFC 的实际报文。计数器名格式是 **`rx_prioN_pause` / `tx_prioN_pause`**（`kernel:drivers/net/ethernet/mellanox/mlx5/core/en_stats.c:1992`–`:1995` 的 `"rx_%s_pause"`/`"tx_%s_pause"`，`%s` 由 `:2058` 填成 `prioN`）。读法：`rx_prio3_pause` 表示「收到对端发来的 PAUSE（说明**本端发太快**）」，`tx_prio3_pause` 表示「本端发出 PAUSE（说明**对端发太快**）」。
→ 见第 11 章

**ECN（Explicit Congestion Notification，显式拥塞通知）**
IP 层拥塞标记：交换机（或网卡 NP）在队列超过阈值时把报文的 CE 位置 1，而不是丢包。对 **RoCEv2** 来说，CE 标记写在外层 **IP 头的 ECN 位**（`kernel:drivers/net/ethernet/mellanox/mlx5/core/en_rx.c:1265`–`:1279` 的 `IP_ECN_set_ce()` / `IP6_ECN_set_ce()`）。BTH 里的 `FECN`/`BECN`（`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h:76`–`:77`）是 IB 原生语义的遗留字段，**RoCEv2 不使用**。
→ 见第 2、11 章

**ECN marking（CE 标记）**
把报文标记为「遭遇拥塞」的动作。计数看 `np_ecn_marked_roce_packets`（本端作为 NP 标记的 CE 包数）。
→ 见第 11 章

**CNP（Congestion Notification Packet，拥塞通知包）**
接收端网卡作为 **NP** 回发给发送端（**RP**）的独立小包，用于通知「你的流量在路上被 ECN 标记过，请降速」。它是 RoCEv2 拥塞控制闭环的**反馈通道**：发送端收到 CNP 后按 DCQCN 规则降速。注意它与 ACK/NAK 走同一条 RC 连接，但语义完全不同——**CNP 不是确认，是流控反馈**。
→ 见第 2、11 章

**DCQCN（Data Center Quantized Congestion Notification，数据中心量化拥塞通知）**
RoCEv2 的标准拥塞控制算法：由 **NP（接收端）** 发 CNP，**RP（发送端）** 收到后按量化规则降速，然后按定时器/字节计数器逐步回升。它把「快降速、慢恢复」做成了硬件状态机。
→ 见第 2、11 章

**RP（Reaction Point，反应点）**
拥塞控制中**执行降速**的一方，通常是**发送端网卡**。对应 DCQCN 的 `rp_*` 参数组。
→ 见第 8、11 章

**NP（Notification Point，通知点）**
拥塞控制中**产生 CNP** 的一方，通常是**接收端网卡**。对应 `np_*` 参数组。
→ 见第 8、11 章

**Kmin / Kmax / Pmax（ECN 标记阈值与概率）**
交换机（或网卡 NP）队列的 ECN 标记曲线：队列长度 < `Kmin` 不标记；`Kmin`–`Kmax` 之间按概率标记（概率线性升到 `Pmax`）；> `Kmax` 全标记（或丢弃）。**这套阈值要按交换芯片的 buffer 大小设定**，全网一致性很关键。
→ 见第 11 章

**alpha（α，拥塞度量）**
DCQCN 内部维护的「当前拥塞程度」浮点估计值，每次收到 CNP 就抬升、之后按 `rp_dce_tcp_g` / `rp_dce_tcp_rtt` 衰减。降速幅度与它成正比。对应的调参项是 `rp_initial_alpha_value`、`rp_gd`。
→ 见第 8、11 章

**slow restart（慢启动重启）**
被 CNP 打到最低速率后，发送端按字节计数器（`rp_byte_reset`）或定时器（`rp_time_reset`）逐步把速率抬回来的过程。计数器 `roce_slow_restart_cnps` 记录了触发次数。
→ 见第 8、11 章

**ETS（Enhanced Transmission Selection，增强传输选择）**
802.1Qaz 定义的**按优先级分配带宽**机制。RoCE 调优里通常把 RoCE 优先级给足带宽、其他优先级给 0 或不保证，配合 PFC 使用。
→ 见第 11 章

**trust mode（信任模式）**
网卡决定「用哪个字段做优先级映射」的开关：信任 **DSCP**（三层）或 **PCP**（二层）。RoCE 部署统一信任 DSCP，避免有/无 VLAN 标签时优先级不一致。
→ 见第 11 章

**pfcwd（PFC Watchdog，PFC 看门狗）**
交换机上的保护机制：检测到某个优先级队列长时间处于 PAUSE 状态时自动采取动作（丢弃/转发该队列流量），**牺牲一个优先级以保全网**。它是防 PFC 死锁与 PFC 风暴的最后一道闸。
→ 见第 11、14 章

**stall watermark（停顿水位）**
网卡内部的水位：当自己的发送队列因为对端 PAUSE 无法前进、同时内部 buffer 也快满时，超过该水位网卡**主动丢包**而不是无限等待。`mlx5_set_port_stall_watermark()`（`kernel:drivers/net/ethernet/mellanox/mlx5/core/port.c:537`）设置 `device_stall_critical_watermark` / `device_stall_minor_watermark`，用的寄存器是 **`MLX5_REG_PFCC`**（`:541` 准备 `pfcc_reg`，`:550`/`:552` 填两个水位字段，`:555` 下发）——不是 `MLX5_REG_PPTB`（PPTB 只用于「优先级 → 端口缓冲」映射）。**它是「宁可丢包也不能全网死锁」的工程折中**。
→ 见第 8、11 章

**`roce_adp_retrans`（自适应重传计数）**
驱动计数器，统计因超时而重传的次数。**RoCE 无损网络的健康标准是它等于 0**（配套还有 `roce_adp_retrans_to`）。非 0 说明网络正在丢包。
→ 见第 8、11、12 章

**`np_ecn_marked_roce_packets`（被标记的 RoCE 包数）**
驱动计数器，本端作为 NP 标记的 CE 包数量。**它是判断「链路是否长期处于拥塞」最直接的指标。**
→ 见第 8、11 章

**`roce_slow_restart_cnps`（慢启动重启次数）**
驱动计数器，因 CNP 触发慢启动重启的次数。与 `np_ecn_marked_roce_packets` 联动看，可以区分「偶发拥塞」与「持续过载」。
→ 见第 8、11 章

**rate limit（QP 限速）**
对单个 QP 的发送速率做整形（`IBV_QP_RATE_LIMIT = 1<<25`，或用户态 `ibv_modify_qp_rate_limit`）。用于「不要让一条测试流量打爆生产网」以及多租户公平性。perftest 的 `--rate_limit` 默认单位是 Gbps，用 `--rate_units` 可改成 MiBps 或 pps。
→ 见第 6、11、13 章

**DCQCN 参数（22 个 debugfs 旋钮）**
mlx5 驱动侧**唯一**的 DCQCN 配置入口是 debugfs（`kernel:drivers/infiniband/hw/mlx5/cong.c`；本驱动**没有 verbs 级 DCQCN 配置接口**）。参数名逐字列出（`cong.c:44`–`:67`）：`rp_clamp_tgt_rate`、`rp_clamp_tgt_rate_ati`、`rp_time_reset`、`rp_byte_reset`、`rp_threshold`、`rp_ai_rate`、`rp_max_rate`、`rp_hai_rate`、`rp_min_dec_fac`、`rp_min_rate`、`rp_rate_to_set_on_first_cnp`、`rp_dce_tcp_g`、`rp_dce_tcp_rtt`、`rp_rate_reduce_monitor_period`、`rp_initial_alpha_value`、`rp_gd`、`np_min_time_between_cnps`、`np_cnp_dscp`、`np_cnp_prio_mode`、`np_cnp_prio`、`rtt_resp_dscp_valid`、`rtt_resp_dscp`。目录位置由 `mlx5_ib_init_cong_debugfs()` 建在设备的 debugfs 根下的 `cc_params/`（`cong.c:456`），且仅当固件能力 `cc_query_allowed` 与 `cc_modify_allowed` 都为真时才存在。
→ 见第 8、11 章

---

## 7. 驱动与工具链

### 7.1 内核模块

**`ib_core.ko`**
内核 RDMA 子系统的**核心模块**：对象模型（`device.c`）、verbs 分发（`verbs.c`）、sysfs（`sysfs.c`）、GID 缓存（`cache.c` 与 RoCE 专有的 `roce_gid_mgmt.c`）、netlink（`netlink.c`/`nldev.c`）、资源追踪（`restrack.c`）、计数器（`counters.c`）、cgroup（`cgroup.c`）、umem 三后端（`umem.c`/`umem_dmabuf.c`/`umem_odp.c`）、以及 **`ib_core_uverbs.c`**（mmap entry 管理、`uverbs_get_flags64/32`、`uverbs_copy_to`）。
→ 见第 7 章

**`ib_uverbs.ko`**
提供字符设备 **`/dev/infiniband/uverbsN`**，是用户态 verbs 的 ABI 入口：`open`/`close`/`write`/`ioctl`/`mmap`/`poll`（`kernel:drivers/infiniband/core/uverbs_main.c`）。传统命令实现在 `uverbs_cmd.c`，新式 ioctl 分发在 `uverbs_ioctl.c`，各对象方法表在 `uverbs_std_types*.c`。
→ 见第 7 章

**`ib_uverbs_support.ko`**
承载 **uobject 生命周期核心 `rdma_core.c`**（`rdma_lookup_get_uobject`、`uverbs_destroy_uobject` 等），通过符号命名空间 `"rdma_core"` 向 `ib_uverbs` 导出（`rdma_core.c:459` 的 `EXPORT_SYMBOL_NS_GPL(..., "rdma_core")`；`uverbs_main.c:64` 的 `MODULE_IMPORT_NS("rdma_core")`）。**很多人会把它误认为属于 `ib_uverbs.ko`。**
→ 见第 7 章

**`rdma_cm.ko`**
**只提供 CM 协议逻辑**，**不注册设备节点**（`cma.c`、`cma_trace.c`、`cma_configfs.c`）。RoCE 的路由解析 `cma_resolve_iboe_route()` 就在这里。
→ 见第 7、8 章

**`rdma_ucm.ko`**
RDMA CM 的用户态通道模块（`ucma.c`），**`/dev/infiniband/rdma_cm` 这个字符设备节点由它注册**——`ucma.c:1948`–`:1954` 的 `struct miscdevice ucma_misc`，`.nodename = "infiniband/rdma_cm"`（**不是 `rdma_cm.ko`**）。它把该节点的 `write/read` 命令分发到 `RDMA_USER_CM_CMD_*` 对应的处理函数（`ucma.c:1810` 的 `ucma_cmd_table[]`）。
→ 见第 7 章

**`ib_umad.ko` / `umadN`**
提供 **`/dev/infiniband/umadN`**，用户态收发 MAD 的通道（`kernel:drivers/infiniband/core/user_mad.c`）。RoCE 上主要用于管理面工具。
→ 见第 7、16 章

**`mlx5_ib.ko`**
Mellanox/NVIDIA 网卡的 **verbs 驱动**（`kernel:drivers/infiniband/hw/mlx5/`）：QP 生命周期与两层状态校验（`qp.c`）、QP 固件命令（`qpc.c`）、数据路径与门铃（`wr.c`）、CQ 与轮询（`cq.c`）、doorbell record（`doorbell.c`）、MR/MW/FRWR/UMR（`mr.c`/`mem.c`/`umr.c`）、AH/AV（`ah.c`）、拥塞控制 debugfs（`cong.c`）、DevX（`devx.c`）、flow steering（`fs.c`）、SR-IOV（`ib_virt.c`）、representor（`ib_rep.c`）。
→ 见第 8 章

**`mlx5_core.ko`**
网卡的**核心/以太网驱动**（`kernel:drivers/net/ethernet/mellanox/mlx5/core/`）：PCI 与固件命令通道（`main.c`/`cmd.c`）、CQ/EQ 与中断（`cq.c`/`eq.c`/`pci_irq.c`）、**UAR/BlueFlame 寄存器页**（`uar.c`）、PFC/PAUSE/停顿水位（`port.c`）、RoCE 使能（`rdma.c`/`vport.c`）、GID 下固件（`lib/gid.c`）、flow steering 底层（`fs_cmd.c`/`fs_core.c`）、netdev 与 DCB（`en_*.c`）、SR-IOV/representor（`eswitch*.c`/`esw/`）、LAG（`lag/lag.c`）、devlink（`devlink.c`）。
→ 见第 8 章

**auxiliary bus（辅助总线）**
内核机制：`mlx5_core` 通过它在同一 PCI 设备上**派生出独立的子设备**（"rdma"、"multiport" 等），让 `mlx5_ib` 与 `mlx5_core` 解耦加载（`kernel:drivers/net/ethernet/mellanox/mlx5/core/dev.c:276` 的 `mlx5_adev_init`）。**这解释了为什么 `mlx5_ib` 依赖 `mlx5_core` 而不是相反。**
→ 见第 8 章

### 7.2 用户态库与框架

**`libibverbs`**
verbs 核心库（`rdma-core:libibverbs/`）：对外头文件 `verbs.h`（安装为 `<infiniband/verbs.h>`）、通用实现 `verbs.c`、设备发现 `device.c`/`sysfs.c`/`init.c`、命令封装 `cmd.c` + `cmd_*.c`、provider 加载 `all_providers.c`/`dynamic_driver.c`、邻居解析 `neigh.c`。
→ 见第 9 章

**`libmlx5`**
mlx5 的用户态驱动（provider 插件，`rdma-core:providers/mlx5/`）：`verbs.c`（全部 `mlx5_*` verbs）、`qp.c`（`mlx5dv_create_qp`、`mlx5_post_send` 快速路径）、`cq.c`、`wqe.h`（WQE 布局）、`dbrec.c`（doorbell record）、`buf.c`（UAR 分配）、`mlx5dv.h`（DV 对外头文件）、`mlx5_ifc.h`（固件位域字典）。安装名带 PABI 后缀，如 `libmlx5-rdmav65.so`。
→ 见第 9 章

**`librdmacm`**
连接管理库（`rdma-core:librdmacm/`）：对外 `rdma_cma.h`、实现 `cma.c`、ACM 客户端 `acm.c`、RSocket `rsocket.c`（`librspreload.so`）、CM ID 索引 `indexer.c`。它把「地址解析 → 路由解析 → 建连」封装成事件驱动模型。
→ 见第 5、9 章

**`rdma-core`（仓库/发行包名）**
本教程锁定的用户态仓库，版本 **66.0**（`CMakeLists.txt:87` 的 `PACKAGE_VERSION "66.0"`），它**不编码 ABI 信息**——ABI 版本是独立的 `IBVERBS_PABI_VERSION`（同文件 `:91`，值为 `"65"`），provider `.so` 后缀 `-rdmav65.so` 就来自它（`:92`）。
→ 见第 3、9 章

**`perftest`（性能测试套件）**
rdma-core 生态里最常用的 RDMA 性能与正确性测试套件，本教程锁定 **6.30**（`configure.ac:32` 的 `AC_INIT([perftest],[6.30],...)`）。分 BW/LAT 两大类，覆盖 SEND/RECV、WRITE、READ、Atomic、RAW_PACKET。
→ 见第 6 章

**`rxe`（Soft-RoCE / `rdma_rxe`）**
**软件实现**的 RoCEv2（`kernel:drivers/infiniband/sw/rxe/`）：无需 RDMA 网卡即可学 verbs，而且它**逐字节构造 RoCEv2 报文**，是理解报文格式的最佳读物（本术语表里所有扩展头布局都可在 `rxe_hdr.h` 里逐字核对）。
→ 见第 2、3 章

**`siw`（Soft-iWARP）**
软件实现的 iWARP（`kernel:drivers/infiniband/sw/siw/`），用来**横向对比** RoCE 的另一种封装方式（TCP 之上而不是 UDP 之上）。
→ 见第 3、9 章

**`ibacm`（IB ACM 守护进程）**
用户态守护进程（`rdma-core:ibacm/`），缓存并加速地址/路由解析。librdmacm 通过 `acm.c` 与它通信，避免每次建连都做完整解析。
→ 见第 7、9 章

**`iwpmd`（iWARP Port Mapper Daemon）**
iWARP 的端口映射守护进程（`rdma-core:iwpmd/`），为 iWARP 连接做 TCP 端口与 RDMA 端点的映射。**RoCE 不需要它**，但看进程列表时要知道它为什么存在。
→ 见第 3、9 章

**`rdma-ndd`（Node Description Daemon）**
把主机名/节点描述写入驱动的守护进程，也就是 `ibstat` 里显示的 node description 的来源。
→ 见第 16 章

**`infiniband-diags`**
命令行诊断工具集（`rdma-core:infiniband-diags/`）：`ibstat`、`iblinkinfo`、`perfquery`、`saquery` 等。**RoCE 场景适用性不同**：`ibstat` 有用，`iblinkinfo`/`saquery` 依赖 IB 的 SM/SA，RoCE 上基本无用。
→ 见第 16 章

### 7.3 三层 API 与加速接口

**Verbs API vs RDMA_CM API（必分清）**
Verbs 是「QP 级」原语（你自己建 QP、自己交换 QPN/GID/rkey）；RDMA_CM 是「连接级」封装（`rdma_resolve_addr`/`rdma_connect` 帮你做地址与路由解析、GID 选择、建连）。生产程序两种都用，perftest 则是「默认裸 verbs + TCP 握手，`-R` 切到 RDMA_CM」。
→ 见第 4、5 章

**DV（Direct Verbs，直接动词）**
mlx5 提供的「绕过 libibverbs 通用层、直接拿到硬件对象指针」的 API（`rdma-core:providers/mlx5/mlx5dv.h`）：`mlx5dv_create_qp`、`mlx5dv_init_obj`（填出 `mlx5dv_qp` 的 `bf`、`dbrec`、`sq`、`rq`、`cq` 裸指针）。**注意**：DV 省的是「每次 post 的软件开销」，不改变硬件路径。
→ 见第 9 章

**DR（Direct Rules，直接规则）**
用户态直接把 **flow steering 规则下发到硬件流表**的 API（`rdma-core:providers/mlx5/mlx5dv_dr.h` + `dr_*.c`）。用于 OVS/DPDK/防火墙这类需要「用户态可编程流表」的场景（含 Steiner 表项编码、ICM 池、buddy 分配）。
→ 见第 9、10 章

**DevX**
把**固件对象**直接暴露给用户态的机制（`MLX5_IB_METHOD_DEVX_*`，内核 `kernel:drivers/infiniband/hw/mlx5/devx.c`）。DV/DR 之下还有一层「直接对固件下命令」，NVMe-oF/DPDK 等用它实现自定义卸载。
→ 见第 8、9 章

**flow steering（流表 / 转向）**
把「匹配某特征的流量」导向某个目标（QP、TIR、丢包…）的硬件能力。内核侧在 `kernel:drivers/infiniband/hw/mlx5/fs.c`（`mlx5_ib_create_flow`）与 `drivers/net/ethernet/mellanox/mlx5/core/fs_*.c`（**注意不在 mlx5_ib 目录**）；用户态用 `ibv_create_flow`/`ibv_create_qp` + DR。
→ 见第 8、9 章

**uverbs（用户态 verbs 内核框架）**
内核里支撑用户态 verbs 的那套框架：uAPI 描述（`uverbs_uapi.c`）、ioctl 分发引擎（`uverbs_ioctl.c` 的 `ib_uverbs_ioctl`/`ib_uverbs_cmd_verbs`/`ib_uverbs_run_method`）、方法表（`uverbs_std_types*.c`）、结构体搬运（`uverbs_marshall.c`）。**能力裁剪发生在「方法表注册时」而不是「调用时」**——不支持的方法根本不会出现在表里。
→ 见第 7 章

### 7.4 ABI

**ABI（Application Binary Interface，应用二进制接口）**
这里特指**内核与用户态之间**的二进制契约：结构体布局、命令号、标志位。RDMA 的 ABI 是**向后兼容演进**的——新库能跑老内核，但用了新特性的程序在老内核上会失败。
→ 见第 7 章

**`IB_USER_VERBS_ABI_VERSION`（传统 ABI 版本号）**
**传统 `write()` uverbs 通道**的 ABI 版本常量，值为 **6**（`kernel:include/uapi/rdma/ib_user_verbs.h:46`）。**它不是全树唯一的版本常量**——CM ABI 另有 `RDMA_USER_CM_ABI_VERSION 4`（`rdma_user_cm.h:43`），mlx5 厂商 ABI 另有 `MLX5_IB_UVERBS_ABI_VERSION 1`（`mlx5-abi.h:68`）。它经两条 sysfs 路径暴露：全局的 `/sys/class/infiniband_verbs/abi_version`（`uverbs_main.c:1132` 的 `CLASS_ATTR_STRING`，值为常量 6）与逐设备的 `/sys/class/infiniband_verbs/uverbsN/abi_version`（`uverbs_main.c:1103` 的 `abi_version_show()`，返回该设备的 `ib_dev->ops.uverbs_abi_ver`，**因此逐设备可能不同**）。
→ 见第 7、12 章

**write ABI（传统 `write()` 命令通道）**
通过 `write()` 往 `/dev/infiniband/uverbsN` 写一个「命令头 + 结构体」的通道：命令号是 `IB_USER_VERBS_CMD_*`，第 50 号起（`IB_USER_VERBS_CMD_THRESHOLD = 50`，`kernel:include/uapi/rdma/ib_user_verbs.h:47`）为扩展命令，扩展命令由 `IB_USER_VERBS_CMD_FLAG_EXTENDED = 0x80000000u`（同文件 `:156`）在命令号高位标识。实现在 `uverbs_cmd.c`。它的缺点是**无法表达复杂参数、难以前向兼容**。
→ 见第 7、9 章

**ioctl ABI（新式 ioctl 命令通道）**
用 `ioctl(fd, RDMA_VERBS_IOCTL, hdr)` 提交结构化请求：`RDMA_VERBS_IOCTL = _IOWR(RDMA_IOCTL_MAGIC, 1, struct ib_uverbs_ioctl_hdr)`，`RDMA_IOCTL_MAGIC = 0x1b`（`kernel:include/uapi/rdma/rdma_user_ioctl_cmds.h:40`–`:42`）。头部结构为

```c
struct ib_uverbs_ioctl_hdr {
        __u16 length; __u16 object_id; __u16 method_id; __u16 num_attrs;
        __aligned_u64 reserved1; __u32 driver_id; __u32 reserved2;
        struct ib_uverbs_attr attrs[];
};
```
（同文件 `:76`）。**它自身没有「版本号」**，兼容机制是三条头部校验：`reserved1`/`reserved2` 必须为 0（否则 `-EPROTONOSUPPORT`，`uverbs_ioctl.c:551`），`driver_id` 必须等于 `uapi->driver_id`（否则 `-EINVAL`，`uverbs_ioctl.c:476`）。
→ 见第 7、9 章

**PABI（provider ABI，用户态 provider 接口版本）**
libibverbs 与厂商 provider `.so` 之间的接口版本，由 rdma-core 的 `IBVERBS_PABI_VERSION` 定义（本版 **65**，`rdma-core:CMakeLists.txt:91`）。provider 文件名带此版本后缀（`-rdmav65.so`），libibverbs 只加载后缀匹配的 provider——**这就是「provider 与 libibverbs 版本不匹配」故障的物理形式**。
→ 见第 3、9 章

**mlx5 vendor ABI（`mlx5-abi.h`）**
mlx5 厂商私有的 uAPI：`struct mlx5_ib_alloc_ucontext_resp`（含 `bf_reg_size`、`tot_bfregs`、`num_uars_per_page`、`num_dyn_bfregs`；**没有 `bf_regs_per_page`**——那是 **mlx4** 的字段，见 `rdma-core:kernel-headers/rdma/mlx4-abi.h:59`；mlx5 用户态只在 provider 内部结构 `rdma-core:providers/mlx5/mlx5.h:326` 有同名私有成员）、`mlx5_ib_create_qp`、`mlx5_ib_create_cq`、mmap 命令枚举 `enum mlx5_ib_mmap_cmd`（`MLX5_IB_MMAP_REGULAR_PAGE = 0`、`GET_CONTIGUOUS_PAGES = 1`、`WC_PAGE = 2`、`NC_PAGE = 3`、`CORE_CLOCK = 5`、`ALLOC_WC = 6`、`CLOCK_INFO = 7`、`DEVICE_MEM = 8`，`kernel:include/uapi/rdma/mlx5-abi.h:487`–`:497`），版本常量 `MLX5_IB_UVERBS_ABI_VERSION = 1`（同文件 `:68`）。**它是「用户态直接敲门铃」的钥匙。**
→ 见第 8、9 章

**`/sys/class/infiniband` 与 sysfs**
内核对外的只读属性树：`/sys/class/infiniband/<ibdev>/ports/<n>/{state,rate,gids/,gid_attrs/{types,ndevs}/}`、`/sys/class/infiniband/<ibdev>/fw_ver` 等（`kernel:drivers/infiniband/core/sysfs.c`）。`show_gids`、`gid_table.sh` 这类脚本本质就是读它（**`show_gids` 是 MLNX_OFED 附带的脚本，不在 rdma-core 66.0 中**——本仓库全树检索无此文件，`debian/infiniband-diags.install` 里也没有它；纯 inbox 环境下改用 `ibv_devinfo -d <dev> -v` 的 GID 表或 `rdma link show`）。
→ 见第 3、16 章

**netlink（RDMA netlink）**
内核向用户态提供设备与资源信息的 netlink 族（`kernel:drivers/infiniband/core/netlink.c`、`nldev.c`）。`rdma link show` / `rdma res show` 这类工具的数据来源；`libibverbs/ibdev_nl.c` 是用户态一侧。
→ 见第 3、16 章

**restrack（资源追踪）**
内核侧记录「哪个 QP/MR/CQ 属于哪个进程」的机制（`kernel:drivers/infiniband/core/restrack.c`，驱动侧命名在 `hw/mlx5/restrack.c`），是 `rdma res show` 的数据源。**审计与排障价值极高**：`rdma res show qp` 的输出行会带 `pid` 与 `comm`。
→ 见第 14、16 章

**RDMA cgroup（RDMA 资源限制）**
内核对每个 cgroup 的 RDMA 资源配额（`kernel:drivers/infiniband/core/cgroup.c`），可限制 `rdma` 子系统的资源类型与数量。容器多租户场景的必要配置，否则一个 Pod 可以把全机 QP/MR 用光。
→ 见第 14、15 章

### 7.5 硬件与门铃机制

**UAR（User Access Region，用户访问区域）**
网卡暴露给用户态的**寄存器页**（PCIe BAR 的一段），用户态把 WQE 写进 QP 缓冲后，通过**写 UAR** 来「敲门铃」。`kernel:drivers/net/ethernet/mellanox/mlx5/core/uar.c` 负责 UAR 页分配与 bfreg 位图（`mlx5_alloc_bfreg`/`mlx5_free_bfreg`，`:257`/`:289`）——**本树中该文件已无 `mp_offset` 成员**（相关结构已重构，只剩 `:194` 的局部 `map_offset()`）。
→ 见第 8、9 章

**doorbell（门铃）**
「通知硬件有新工作」的那一次寄存器写。它是**数据面唯一必须做的 MMIO**，因此也是低延迟优化的焦点（是否合并、是否用 BlueFlame、doorbell 落在哪个 cacheline）。
→ 见第 8、9、13 章

**BlueFlame（BF，蓝焰）**
mlx5 的一种门铃机制：把**最多 256 字节的 WQE 数据直接写进 UAR 寄存器区**，硬件从门铃写里就把 WQE 收走了，从而**省掉一次 PCIe DMA 读**。它需要用 BF 寄存器（bfreg），因此是稀缺资源——多进程场景下「BF 寄存器耗尽」是常见故障（`mlx5_ib_alloc_ucontext` 建立 BF 池，`kernel:drivers/infiniband/hw/mlx5/main.c`）。
→ 见第 8、9、13 章

**bfreg（BlueFlame Register，蓝焰寄存器）**
BlueFlame 使用的寄存器名额。用户态注册 context 时由驱动分配（`struct mlx5_bfreg_info`，`kernel:drivers/infiniband/hw/mlx5/mlx5_ib.h:168`；分配函数 `mlx5_alloc_bfreg` 在 `mlx5/core/uar.c`），数量与页大小通过 `struct mlx5_ib_alloc_ucontext_resp` 的 `bf_reg_size`/`tot_bfregs`/`num_uars_per_page` 告诉用户态（`bf_regs_per_page` 是 **mlx4** 的字段，不是 mlx5 的）。
→ 见第 8、9 章

**doorbell record（DBR / `dbrec`）**
**内存里**的一块小结构（而不是寄存器），网卡周期性（或按需）读取它以获取生产者索引，从而知道「QP 缓冲里又多了哪些 WQE」。用途是支持**批量/延迟门铃**与 `mlx5dv` 的软件路径。用户态管理在 `rdma-core:providers/mlx5/dbrec.c`，内核映射在 `kernel:drivers/infiniband/hw/mlx5/doorbell.c` 的 `mlx5_ib_db_map_user_desc`。
→ 见第 8、9 章

**mailbox / 固件命令队列**
驱动与网卡固件之间的命令通道（`kernel:drivers/net/ethernet/mellanox/mlx5/core/cmd.c` 的 `mlx5_cmd_exec`/`mlx5_cmd_do`/`mlx5_cmd_exec_polling`）。**QP 的固件命令不在 `mlx5_core`**，而在 `kernel:drivers/infiniband/hw/mlx5/qpc.c`（`mlx5_qpc_create_qp`、`mlx5_core_destroy_qp`）；本内核树中**不存在** `drivers/net/ethernet/mellanox/mlx5/core/qp.c`，也**不存在** `mlx5_core_create_qp()`。
→ 见第 8 章

**debugfs（驱动调试文件系统）**
驱动暴露的运行时可调参数与统计。RoCE 相关最重要的就是 mlx5 的 **DCQCN `cc_params/`** 目录（见第 6 节），路径形如 `/sys/kernel/debug/mlx5/<PCI 地址>/cc_params/<参数名>`。
→ 见第 8、11、16 章

**devlink**
内核的通用设备参数/健康上报框架。「运行时开关 RoCE」就是一个 devlink 泛型参数 `ENABLE_ROCE`（`kernel:drivers/net/ethernet/mellanox/mlx5/core/devlink.c`），`devlink health` 则提供硬件健康诊断。
→ 见第 8、12、16 章

**tracepoint（内核跟踪点）**
RDMA 子系统提供 `rdma_core` / `rdma_cma` / `mlx5_ib` / `mlx5_core` 等跟踪点组，用于在**不抓包**的前提下观察内核路径（`uverbs_*`、`cma_trace.c`、`mlx5_trace.c`）。调试内核路径问题时的第一选择。
→ 见第 7、16 章

### 7.6 事件与连接管理

**`IBV_EVENT_*`（verbs 异步事件）**
通过 `ibv_get_async_event()` 读取的事件（枚举见 `rdma-core:libibverbs/verbs.h:454`），按对象分组。**RoCE 相关、必须处理的**：

| 事件 | 含义 | 处理建议 |
|---|---|---|
| `IBV_EVENT_GID_CHANGE` | 端口 GID 表变化 | **RoCE 最常触发**：重建/刷新 GID 缓存、必要时重连 |
| `IBV_EVENT_PORT_ERR` | 端口链路不可用 | 停业务、等链路恢复 |
| `IBV_EVENT_PORT_ACTIVE` | 端口链路变为 active | 可继续/重试建连 |
| `IBV_EVENT_DEVICE_FATAL` | 设备进入 FATAL | 进程内所有 QP 作废，需重开设备 |
| `IBV_EVENT_QP_FATAL` | QP 出错并进入 error | 从 CQ 读出具体 `IBV_WC_*` 状态再决定 |
| `IBV_EVENT_QP_REQ_ERR` | 本地工作队列非法请求 | 检查 opcode/mask/SGE |
| `IBV_EVENT_QP_ACCESS_ERR` | 本地访问违例 | 检查 lkey 与 `IBV_ACCESS_*` |
| `IBV_EVENT_COMM_EST` | QP 上通信已建立 | 可开始发数据 |
| `IBV_EVENT_SQ_DRAINED` | SQ 已排空 | 有序停机完成 |
| `IBV_EVENT_CQ_ERR` | CQ 处于错误（CQ overrun） | **CQ 太小或没及时 poll**，QP 会连带失效 |
| `IBV_EVENT_SRQ_LIMIT_REACHED` | SRQ 低水位 | 立即补 `ibv_post_recv` |
| `IBV_EVENT_SRQ_ERR` | SRQ 错误 | 检查 SRQ 配置与 RR 数量 |
| `IBV_EVENT_QP_LAST_WQE_REACHED` | 与 SRQ 关联的 QP 上最后一个 WQE 已处理 | 决定是否把 QP 摘下 SRQ |
| `IBV_EVENT_LID_CHANGE` / `IBV_EVENT_PKEY_CHANGE` / `IBV_EVENT_SM_CHANGE` / `IBV_EVENT_CLIENT_REREGISTER` | IB 管理面事件 | RoCE 上一般不触发（LID/SM 不适用） |
| `IBV_EVENT_PATH_MIG` / `IBV_EVENT_PATH_MIG_ERR` | 备用路径迁移成功/失败 | 只在配了 alt path 时出现 |

（同文件 `:454` 起共 21 个值，另有 `IBV_EVENT_WQ_FATAL`、`IBV_EVENT_DEVICE_SPEED_CHANGE`。）**不处理异步事件的程序一定会在生产环境出问题**——最典型的是 epoll 循环里漏掉 `IBV_EVENT_GID_CHANGE` 之后再也连不上。
→ 见第 4、12 章

**`rdma_cm`（RDMA Connection Manager，连接管理器）**
面向连接的 RDMA 服务（RC/UC/UD）的建连/维护/释放实体，用户态 API 是 `rdma_cma.h`、内核设备是 `/dev/infiniband/rdma_cm`。它基于 socket 风格但适配 QP 语义：**通信必须经由特定 RDMA 设备、数据传输是基于消息的**。
→ 见第 5、7 章

**`RDMA_CM_EVENT_*`（CM 事件）**
CM 的事件枚举（`rdma-core:librdmacm/rdma_cma.h:51` 起），完整列表：`RDMA_CM_EVENT_ADDR_RESOLVED`、`ADDR_ERROR`、`ROUTE_RESOLVED`、`ROUTE_ERROR`、`CONNECT_REQUEST`、`CONNECT_RESPONSE`、`CONNECT_ERROR`、`UNREACHABLE`、`REJECTED`、`ESTABLISHED`、`DISCONNECTED`、`DEVICE_REMOVAL`、`MULTICAST_JOIN`、`MULTICAST_ERROR`、`ADDR_CHANGE`、`TIMEWAIT_EXIT`、`ADDRINFO_RESOLVED`、`ADDRINFO_ERROR`、`USER`、`INTERNAL`。**主线只要记住四步**：`ADDR_RESOLVED` → `ROUTE_RESOLVED` → （服务端 `CONNECT_REQUEST`）→ `ESTABLISHED`。
→ 见第 5 章

**`rdma_cm_event`（CM 事件结构）**
承载事件内容：`event`、`status`、`id`/`listen_id`，以及建连所需的 `private_data`/`private_data_len`、`ah_attr`、`qp_num`、`qkey`。两个易错点：① `private_data` 指向的缓冲区**在调用 `rdma_ack_cm_event()` 时才被释放**；② `private_data_len` 是**缓冲区大小**而非实际收到长度，多余空间被清零。
→ 见第 5 章

**`rdma_cm` ABI（RDMA CM 的用户态 ABI）**
命令号为 `RDMA_USER_CM_CMD_*`（`kernel:include/uapi/rdma/rdma_user_cm.h:48` 起共 25 个：`CREATE_ID`、`DESTROY_ID`、`BIND_IP`、`RESOLVE_IP`、`RESOLVE_ROUTE`、`QUERY_ROUTE`、`CONNECT`、`LISTEN`、`ACCEPT`、`REJECT`、`DISCONNECT`、`INIT_QP_ATTR`、`GET_EVENT`、`GET_OPTION`、`SET_OPTION`、`NOTIFY`、`JOIN_IP_MCAST`、`LEAVE_MCAST`、`MIGRATE_ID`、`QUERY`、`BIND`、`RESOLVE_ADDR`、`JOIN_MCAST`、`RESOLVE_IB_SERVICE`、`WRITE_CM_EVENT`）。内核侧是 `ucma.c:1810` 的 `ucma_cmd_table[]`，处理函数统一叫 `ucma_<动词>`（`ucma_create_id`、`ucma_resolve_addr`、`ucma_join_multicast` …）——这就是「`UCMA_CMD_*` 镜像」的实际形态：**没有 `UCMA_CMD_*` 这组命令号常量，只有 `ucma_*()` 处理函数与 `RDMA_USER_CM_CMD_*` 命令号表**。
→ 见第 7 章

### 7.7 虚拟化与多租户

**SR-IOV（Single Root I/O Virtualization，单根 I/O 虚拟化）**
把一个物理 PCIe 设备虚拟成多个**功能**：PF 管理、VF 给虚拟机/容器直通。RoCE 用它给每个租户一个独立的 uverbs 设备与独立的资源配额。
→ 见第 15 章

**PF（Physical Function，物理功能）**
SR-IOV 中拥有完整配置能力的那个 PCIe 功能，用于创建/管理 VF。宿主机上的 `mlx5_0` 一般对应 PF。
→ 见第 15 章

**VF（Virtual Function，虚拟功能）**
由 PF 派生出的轻量 PCIe 功能，直通给 VM/容器后**在 guest 内表现为一个独立的 RDMA 设备**。VF 的 RoCE 需要显式使能（`port_fn_roce_set`，`kernel:drivers/net/ethernet/mellanox/mlx5/core/eswitch*.c`）。
→ 见第 14、15 章

**representor（代表端口）**
switchdev 模式下为每个 VF 创建的**虚拟网络接口**（`enp1s0f0v0` 这类名字），用于在宿主侧对 VF 流量做策略与观测。IB 侧有对应的 `ib_rep.c`（`CONFIG_MLX5_ESWITCH`）把 representor 暴露为一个 RDMA 设备。
→ 见第 15 章

**VFIO（Virtual Function I/O）**
Linux 的**用户态设备直通**框架：把 VF 绑定到 `vfio-pci` 后，QEMU/DPDK 可在无内核驱动的情况下直接操作设备。对 RDMA 的后果是**内核侧看不到该设备**（`rdma res show` 里没有它），诊断链路完全不同；`rdma-core:providers/mlx5/mlx5_vfio.c` 就是为这个场景准备的。
→ 见第 15 章

**MACsec**
以太网链路层加密（802.1AE）。RoCE 可与 MACsec 卸载共存（`kernel:drivers/infiniband/hw/mlx5/macsec.c`），是「链路加密但不放弃 RDMA 性能」的方案之一。
→ 见第 14、15 章

---

## 8. 性能与计时

**bandwidth（带宽，BW）**
单位时间传输的数据量，RDMA 圈里常说 **Gb/s**（线速单位）或 **MiB/s**。注意 `perftest` 的坑：`MiB = 2^20 byte` 而 `Gb = 10^9 bit`，换算时别搞混。
→ 见第 6、13 章

**latency（时延）**
一次操作从发出到完成的时间。perftest 的 LAT 类工具对 **SEND/WRITE 系**报**半程（one-way）**时延（把测得的 RTT 折半，`rtt_factor = 2`）；**READ/ATOMIC 类测试 `rtt_factor = 1`，不折半**（`perftest:src/perftest_parameters.c:5108`）。时延优化与带宽优化常常互相冲突（例如 inline 与 post_list）。
→ 见第 6、13 章

**RTT（Round-Trip Time，往返时间）**
一次请求-响应往返的总时间。perftest 的 `ib_write_lat` 测的是「WRITE + 反向小包」的往返，因此报出的数字是 RTT/2。
→ 见第 6 章

**message rate（消息速率，Mpps）**
每秒能完成多少条消息。小消息下它是**比带宽更关键的指标**（2 字节消息跑不出带宽，但能压出 Mpps 天花板），瓶颈通常落在 CPU 与门铃频率上。
→ 见第 13 章

**line rate（线速）**
链路物理速率对应的理论上限。例如 200 Gb/s 链路上 `ib_write_bw -q 1` 只能跑 96 Gb/s 说明**单 QP 受 ECMP 单路径限制**，而 `-q 4` 达到 191.8 Gb/s（96% 线速）说明多路径生效。
→ 见第 12、13 章

**bidirectional bandwidth（双向带宽）**
两端同时发送时的总带宽，更接近 AI 训练与分布式存储的真实负载。perftest 用 `-b/--bidirectional`。
→ 见第 6、13 章

**cycles_t（周期计数类型）**
perftest 用于计时的类型（`perftest:src/get_clock.h`），把 CPU 周期数换算成微秒。换算需要知道 CPU 频率——perftest 用 `get_cpu_mhz()` 自动读取。这就是 `-F/--CPU-freq` 与「关掉变频」两件事的由来：**`-F/--CPU-freq` 是一个不带参数的开关**（`perftest:src/perftest_parameters.c:3151`），只用来抑制「cpufreq_ondemand 已加载 / CPU 频率未在最高」这类警告（`:427`–`:428`），**不是用来设置频率的选项**；perftest 6.30 中**不存在 `--cpu_freq`**。
→ 见第 6、13 章

**TSC（Time Stamp Counter，时间戳计数器）**
x86 上用于高精度计时的寄存器，`get_clock.c` 通过它获得 `cycles_t`。跨核/跨 NUMA 读 TSC 的代价与一致性是时延测量精度的关键。
→ 见第 6、13 章

**CPU frequency scaling（变频）**
CPU 频率动态调整会让周期→时间的换算失准并引入唤醒延迟。**做时延测试前必须关掉**（把 governor 设为 `performance`），否则测出的尾延迟会明显偏大。
→ 见第 13 章

**tail latency（尾延迟）**
P99/P999 这类高分位时延，而不是平均值。RDMA 场景里「平均 2 µs、P99 200 µs」是常见的真实分布，只看平均值会漏掉问题。
→ 见第 6、13 章

**NUMA（Non-Uniform Memory Access，非一致内存访问）**
多路服务器上内存访问代价随 CPU 与内存位置而变。RDMA 性能的第一大主机侧陷阱就是**网卡与进程/内存不在同一个 NUMA 节点**：跨节点 PCIe + 跨节点内存访问会直接砍半带宽。
→ 见第 12、13 章

**PCIe**
网卡与主机之间的总线，**它自己就是瓶颈**。必须核对 `LnkCap` 与 `LnkSta` 的 Speed/Width 是否一致——「插在 x8 槽上」能让 200 Gb/s 网卡只能跑一半。
→ 见第 12、13 章

**hugepage（大页）**
用 2 MB/1 GB 页代替 4 KB 页，减少 MTT 条目与 TLB miss。perftest 支持用大页分配缓冲区（`--use_hugepages`）。
→ 见第 13 章

**interrupt affinity（中断亲和）**
把网卡中断绑定到「网卡所在 NUMA 节点内」的多个核上。绑错节点会让完成处理跨节点，延迟与吞吐双输；现代 mlx5 驱动会自动处理，但可以手工调整。
→ 见第 13 章

**batching（批处理：`post_list` 与 `sq_sig_all`）**
用「一次投递多条 WR + 只对部分 WR 要完成事件」把每条消息的 CPU 开销摊薄。它是把吞吐从「每包一次门铃」提升到「每 N 包一次门铃」的核心手段。
→ 见第 6、13 章

---

## 9. 四组最容易混淆的对比小表

### 9.1 `lkey` vs `rkey`

| 维度 | `lkey`（Local Key） | `rkey`（Remote Key） |
|---|---|---|
| 谁用 | **只有本端**用（硬件的本地校验） | **交给对端**用（对端硬件做远端校验） |
| 出现在哪 | 每一条 SGE（`struct ibv_sge.lkey`） | RETH / ATMETH 扩展头（`ibv_send_wr.wr.rdma.rkey`） |
| 校验什么 | 这块内存在本地是否可访问、地址是否越界 | 对端的 RW/READ/ATOMIC 操作是否有权限、地址是否越界 |
| 同一次注册 | 与 `rkey` **同源于一次 `ibv_reg_mr`**，但取值与用途不同 | 同左 |
| 泄露后果 | 影响本端进程（一般不可跨主机利用） | **等价于内存泄露**：拿到 `addr + rkey` 就能直接读写你的内存 |
| 怎么防 | 最小权限、`IBV_ACCESS_ZERO_BASED` | 最小权限、不写日志、抓包脱敏、及时 `LOCAL_INV`/`SEND_WITH_INV` 回收 |

→ 见第 4、14 章

### 9.2 IB MTU vs netdev MTU

| 维度 | IB MTU（RoCE MTU） | netdev MTU |
|---|---|---|
| 含义 | 端口的**报文净荷**上限（**不含包头**） | 以太网**帧净荷**上限（含 RoCE 的 IB 头 + UDP/IP 头） |
| 取值形式 | 固定档位 `IBV_MTU_256/512/1024/2048/4096`（`rdma-core:libibverbs/verbs.h:368`–`:372`） | 任意字节数（常见 1500 / 9000 / 9216） |
| 在哪设 | QP 属性 `path_mtu`（`ibv_modify_qp` 的 `IBV_QP_PATH_MTU`）；perftest `-m/--mtu` | `ip link set <netdev> mtu <n>` |
| 一致性要求 | 两端 QP 必须一致；**全网交换机也得放行** | 整条路径（含隧道）都要够大 |
| 换算关系 | RoCE MTU 4096（IPv4 无 VLAN）需要 netdev MTU ≥ **4192**（内核 `iboe_get_mtu()` 的 **96 字节**保守折算：40+8+12+4+28+4，它决定 `active_mtu`；按 58 字节算成 4154 只会得到 2048，实践建议直接设 4200）。**58 是另一个数**——线缆帧开销，只用于净荷效率：SEND 58、单包 WRITE 74（多 16 字节 RETH）、带 VLAN 62、IPv6 78 | 反过来说 1500 的 netdev 只能承载 RoCE MTU ≤ 1024 |
| 症状 | 不匹配 → 建连失败/带宽上不去 | 不够 → 分片、丢包、带宽骤降 |

→ 见第 2、13 章

### 9.3 RoCEv1 vs RoCEv2

| 维度 | RoCEv1 | RoCEv2 |
|---|---|---|
| 封装 | IB 传输头直接进以太网帧 | IB 传输头进 **UDP/IP** |
| 标识 | EtherType **`0x8915`** | UDP 目的端口 **4791** |
| 层次 | 二层 | 三层（可路由） |
| 跨三层 | **不能** | 能 |
| 参与 ECMP | 不能（无 L3/L4 头可哈希） | 能（靠源/目的 UDP 端口等） |
| GID | 仍是 128 位，但语义偏二层 | GID = IPv4/IPv6 地址载体 |
| 选哪一行 GID | `show_gids` 的 `VER = v1` | **`VER = v2`（生产默认）** |
| 现状 | 基本不再部署 | 生产标准 |

→ 见第 1、2 章

### 9.4 RDMA WRITE vs SEND

| 维度 | RDMA WRITE（单边） | SEND / RECV（双边） |
|---|---|---|
| 对端是否知情 | **不需要**：远端不需 post recv、CPU 不参与 | **必须**事先 `ibv_post_recv` 一条 RR |
| 对端消息边界 | 无「消息」概念，只是往地址区间写 | 硬件保持消息边界 |
| 对端 CQE | 不产生（只有 ACK） | **产生**一个 CQE |
| 定位方式 | `remote_addr` + `rkey`（对端要先告知） | 目的 QPN（建连时已交换） |
| 支持的服务类型 | UC/RC/RD（**UD 不支持**） | UD/UC/RC/RD 全部支持 |
| 常见用途 | NVMe-oF、GPU 显存搬运、零拷贝落盘 | 控制消息、请求-响应、需要「通知对端」的场景 |
| `WRITE_WITH_IMM` 特例 | **会消耗对端一个 RR** 并产生带 IMM 的 CQE | —— |
| 典型实验 | `ib_write_bw` / `ib_write_lat`（**LAT 测试不需要对端 post recv**） | `ib_send_bw` / `ib_send_lat`（**必须 post recv**） |

→ 见第 1、4、6 章

---

## 10. 字母序索引

> `分区` 列对应本文件第 1–8 节。带「对比表」标记的词请回到第 9 节看逐维对比。

| 术语 | 中文 | 分区 |
|---|---|---|
| ACK / NAK | 确认 / 否认 | 1.3 |
| AETH | 确认扩展头 | 1.2 |
| AH | 地址句柄 | 2 |
| alpha | 拥塞度量 α | 6 |
| async fd | 异步事件 fd | 2 |
| ATMACK | 原子确认扩展头 | 1.2 |
| ATMETH | 原子操作扩展头 | 1.2 |
| Atomic | 原子操作 | 1.5 |
| auxiliary bus | 辅助总线 | 7.1 |
| AV | 地址向量 | 2 |
| ABI | 应用二进制接口 | 7.4 |
| bandwidth | 带宽 | 8 |
| batching | 批处理 | 8 |
| bfreg | 蓝焰寄存器 | 7.5 |
| bidirectional bandwidth | 双向带宽 | 8 |
| BlueFlame | 蓝焰 | 7.5 |
| BTH | 基本传输头 | 1.2 |
| Clos / Spine-Leaf | 叶脊拓扑 | 4 |
| CNP | 拥塞通知包 | 1.3 / 6 |
| comp_channel | 完成事件通道 | 2 |
| CQ | 完成队列 | 2 |
| CQE | 完成队列条目 | 2 |
| CQN | CQ 号 | 2 |
| CPU frequency scaling | 变频 | 8 |
| cycles_t | 周期计数类型 | 8 |
| DC / DCT | 动态连接 / 动态连接目标 | 1.4 / 2 |
| DCQCN | 数据中心量化拥塞通知 | 6 |
| debugfs | 驱动调试文件系统 | 7.5 |
| DETH | 数据报扩展头 | 1.2 |
| DevX | 固件对象直通 | 7.3 |
| devlink | 设备参数框架 | 7.5 |
| DGID | 目的 GID | 4 |
| DMA（见「零拷贝」澄清） | 直接内存访问 | 3 |
| dma-buf | 跨设备缓冲区共享 | 3 |
| DM（Device Memory） | 设备内存 | 3 |
| doorbell | 门铃 | 7.5 |
| doorbell record / dbrec | 门铃记录 | 7.5 |
| DR | 直接规则 | 7.3 |
| DSCP | 差分服务代码点 | 4 |
| DV | 直接动词 | 7.3 |
| ECMP | 等价多路径 | 4 |
| ECN | 显式拥塞通知 | 6 |
| ECN marking | CE 标记 | 6 |
| EQ | 事件队列 | 2 |
| ETS | 增强传输选择 | 6 |
| ERROR（`IBV_QPS_ERR`） | 出错状态 | 5 |
| FETH | 冲刷扩展头 | 1.2 |
| flow label | 流标签 | 4 |
| flow steering | 流表 | 7.3 |
| FRWR | 快速注册 WR | 3 |
| GID | 全局标识符 | 4 |
| GID index | GID 索引 | 4 |
| GID table | GID 表 | 4 |
| GID type | GID 类型 | 4 |
| GPUDirect RDMA | GPU 直接 RDMA | 3 |
| GRH | 全局路由头 | 1.2 |
| GUID | 全局唯一标识符 | 4 |
| head-of-line blocking | 队头阻塞 | 4 |
| hop limit | 跳数上限 | 4 |
| hugepage | 大页 | 8 |
| `ib_core.ko` | 内核 RDMA 核心模块 | 7.1 |
| `ib_uverbs.ko` | uverbs 字符设备模块 | 7.1 |
| `ib_uverbs_support.ko` | uobject 生命周期支撑模块 | 7.1 |
| `ib_umad.ko` / `umadN` | MAD 用户态通道 | 7.1 |
| `ibacm` | IB ACM 守护进程 | 7.2 |
| `IBV_ACCESS_*` | MR 访问权限位 | 3 |
| `IBV_EVENT_*` | verbs 异步事件 | 7.6 |
| `IBV_QP_*` | QP 属性掩码 | 5 |
| `IBV_SEND_FENCE` | 栅栏标志 | 5 |
| `IBV_SEND_INLINE` | 内联发送标志 | 5 |
| `IBV_SEND_IP_CSUM` | IP 校验和卸载标志 | 5 |
| `IBV_SEND_SIGNALED` | 要完成事件标志 | 5 |
| `IBV_SEND_SOLICITED` | Solicited 标志 | 5 |
| `IB_USER_VERBS_ABI_VERSION` | 传统 uverbs ABI 版本 | 7.4 |
| ibv_poll_cq | 轮询 CQ | 2 |
| ibv_req_notify_cq | 请求完成通知 | 2 |
| ICRC | 不变式校验 | 1.2 |
| IETH | 失效扩展头 | 1.2 |
| IMMDT | 立即数扩展头 | 1.2 |
| incast | 多打一 | 4 |
| InfiniBand | InfiniBand 架构 | 1.1 |
| `infiniband-diags` | IB 诊断工具集 | 7.2 |
| INIT | 已初始化 | 5 |
| inline | 内联发送 | 5 |
| interrupt affinity | 中断亲和 | 8 |
| ioctl ABI | 新式 ioctl 通道 | 7.4 |
| iWARP | 互联网广域 RDMA | 1.1 |
| `iwpmd` | iWARP 端口映射守护进程 | 7.2 |
| jumbo frame | 巨帧 | 4 |
| Kmin / Kmax / Pmax | ECN 标记阈值与概率 | 6 |
| LAG | 链路聚合 | 4 |
| latency | 时延 | 8 |
| `libibverbs` | verbs 核心库 | 7.2 |
| `libmlx5` | mlx5 用户态驱动 | 7.2 |
| `librdmacm` | 连接管理库 | 7.2 |
| LID | 本地标识符 | 4 |
| line rate | 线速 | 8 |
| lkey | 本地密钥 | 3 / 对比表 9.1 |
| LRH | 本地路由头 | 1.2 |
| MAD | 管理数据报 | 1.5 |
| mailboxes / 固件命令队列 | 命令队列 | 7.5 |
| `max_dest_rd_atomic` | 对端在途读上限 | 5 |
| `max_rd_atomic` | 本端在途读上限 | 5 |
| MACsec | 链路层加密 | 7.7 |
| message rate | 消息速率 | 8 |
| MGID | 组播组 ID | 4 |
| `min_rnr_timer` | RNR 最小退避定时器 | 5 |
| MLID | 组播 LID | 4 |
| `mlx5_core.ko` | mlx5 核心/以太网驱动 | 7.1 |
| `mlx5_ib.ko` | mlx5 verbs 驱动 | 7.1 |
| mlx5 vendor ABI | mlx5 厂商 ABI | 7.4 |
| MR | 内存区域 | 2 |
| MSN | 消息序号 | 1.3 |
| MSN vs PSN | 消息序号与包序号的区别 | 1.3 / 对比表 9.3 相关 |
| MPT / mkey | 内存保护表与密钥 | 3 |
| MTU（IB MTU） | IB 最大传输单元 | 4 / 对比表 9.2 |
| MTT | 内存转换表 | 3 |
| Multi-Plane | 多平面 | 4 |
| MW | 内存窗口 | 2 |
| neighbor resolution | 邻居解析（ARP/ND） | 4 |
| netdev MTU | 网络设备 MTU | 4 / 对比表 9.2 |
| netdev ↔ ibdev 绑定 | 设备对应关系 | 4 |
| netlink | RDMA netlink | 7.4 |
| NP | 通知点 | 6 |
| `np_ecn_marked_roce_packets` | 被标记的 RoCE 包数 | 6 |
| NUMA | 非一致内存访问 | 8 |
| ODP | 按需缺页 | 3 |
| OpCode | 操作码 | 1.5 |
| Outstanding WR | 在途工作请求 | 2 |
| PABI | provider 接口版本 | 7.4 |
| PAUSE frame | PAUSE 帧 | 6 |
| PCIe | PCI Express 总线 | 8 |
| PCP | 优先级码点 | 4 |
| PD | 保护域 | 2 |
| perftest | 性能测试套件 | 7.2 |
| PF | 物理功能 | 7.7 |
| PFC | 优先级流控 | 6 |
| pfcwd | PFC 看门狗 | 6 |
| PKey | 分区键 | 3 |
| path migration | 路径迁移 | 5 |
| post_list | 批量投递 | 5 |
| PSN | 包序号 | 1.3 |
| QKey | 队列键 | 3 |
| QP | 队列对 | 2 |
| QP 状态机 | RESET→INIT→RTR→RTS | 5 |
| QPN | QP 号 | 2 |
| rate limit | QP 限速 | 6 |
| RAW_PACKET | 原始包 QP | 1.4 |
| RC | 可靠连接 | 1.4 |
| RD | 可靠数据报 | 1.4 |
| RDETH | 可靠数据报扩展头 | 1.2 |
| RDMA | 远程直接内存访问 | 1.1 |
| RDMA READ | 单边读 | 1.5 |
| RDMA WRITE | 单边写 | 1.5 / 对比表 9.4 |
| `rdma_cm` | RDMA 连接管理器 | 7.6 |
| `rdma_cm` ABI | RDMA CM 用户态 ABI | 7.6 |
| `RDMA_CM_EVENT_*` | CM 事件 | 7.6 |
| `rdma_cm_event` | CM 事件结构 | 7.6 |
| `rdma_core`（rdma-core） | 用户态仓库/发行包 | 7.2 |
| RDMA cgroup | RDMA 资源限制 | 7.4 |
| `rdma-ndd` | 节点描述守护进程 | 7.2 |
| `rdma_ucm.ko` | RDMA CM 用户态通道 | 7.1 |
| representor | 代表端口 | 7.7 |
| restrack | 资源追踪 | 7.4 |
| RETH | RDMA 扩展头 | 1.2 |
| rkey | 远端密钥 | 3 / 对比表 9.1 |
| RLIMIT_MEMLOCK | 可锁定内存限额 | 3 |
| RNR NAK | 接收方未就绪否认 | 1.3 |
| `rnr_retry` | RNR 重试次数 | 5 |
| RoCE | 融合以太网上的 RDMA | 1.1 |
| RoCE LAG | RoCE 链路聚合 | 4 |
| RoCEv1 | RoCE 第一代 | 1.1 / 对比表 9.3 |
| RoCEv2 | RoCE 第二代 | 1.1 / 对比表 9.3 |
| RoCEv2 UDP 目的端口 4791 | 封装端口 | 4 |
| `roce_adp_retrans` | 自适应重传计数 | 6 |
| `roce_slow_restart_cnps` | 慢启动重启次数 | 6 |
| RP | 反应点 | 6 |
| RR | 接收请求 | 2 |
| RTR | 就绪接收 | 5 |
| RTS | 就绪发送 | 5 |
| `retry_cnt` | 重传次数 | 5 |
| RQ | 接收队列 | 2 |
| `rxe` / `rdma_rxe` | 软件 RoCE | 7.2 |
| SEND / RECV | 双边消息 | 1.5 / 对比表 9.4 |
| S/G Array | 分散聚集数组 | 3 |
| SGE | 分散聚集元素 | 3 |
| `siw` | 软件 iWARP | 7.2 |
| slow restart | 慢启动重启 | 6 |
| SR | 发送请求 | 2 |
| SR-IOV | 单根 I/O 虚拟化 | 7.7 |
| SQ | 发送队列 | 2 |
| SQD | 发送队列排空 | 5 |
| SQE | 发送队列错误 | 5 |
| SQ_PSN / RQ_PSN | 发送/接收起始 PSN | 5 |
| sq_sig_all | 全部发送都产生完成 | 5 |
| SRQ | 共享接收队列 | 2 |
| SRQ limit | SRQ 低水位 | 2 |
| stall watermark | 停顿水位 | 6 |
| sysfs | 内核属性文件系统 | 7.4 |
| tail latency | 尾延迟 | 8 |
| TC（internal traffic class） | 内部流量类别 | 4 |
| `timeout` | 本地 ACK 超时 | 5 |
| tracepoint | 内核跟踪点 | 7.5 |
| traffic class | 流量类别 | 4 |
| trust mode | 信任模式 | 6 |
| TSC | 时间戳计数器 | 8 |
| two-layer validation | 两层状态校验 | 5 |
| UC | 不可靠连接 | 1.4 |
| UD | 不可靠数据报 | 1.4 |
| UAR | 用户访问区域 | 7.5 |
| UMR | 用户态内存注册 | 3 |
| uobject | 内核用户对象 | 2 |
| ucontext / `ibv_context` | 用户态设备上下文 | 2 |
| UDP source port entropy | UDP 源端口熵 | 4 |
| uverbs | 用户态 verbs 内核框架 | 7.3 |
| verb | 单个动词操作 | 1.1 |
| Verbs | verbs 接口 | 1.1 |
| VF | 虚拟功能 | 7.7 |
| VFIO | 用户态设备直通 | 7.7 |
| VLAN | 虚拟局域网标签 | 4 |
| WC | 工作完成 | 2 |
| WC status code | 完成状态码 | 2 |
| WQ | 工作队列 | 2 |
| WQE | 工作队列元素 | 2 |
| WQEBB | WQE 基本块 | 2 |
| WR | 工作请求 | 2 |
| write ABI | 传统 write 命令通道 | 7.4 |
| WRITE_WITH_IMM | 带立即数的 RDMA WRITE | 1.5 |
| XRC | 扩展可靠连接 | 1.4 |
| XRCD | XRC 域 | 2 |

---

## 相关文件

- 按主题速查取值与 11 张对比表：[`glossary-quickref.md`](glossary-quickref.md)
- 代码导航总图（本表所有 `kernel:` / `rdma-core:` / `perftest:` 路径的地图）：[`repo-map.md`](repo-map.md)
- 写作与引用约定、本教程锁定的三个版本：[`00-conventions.md`](00-conventions.md)
- 版本与 ABI 兼容性矩阵：[`versions-and-abi.md`](versions-and-abi.md)
- 高频问题 60 问：[`faq.md`](faq.md)
