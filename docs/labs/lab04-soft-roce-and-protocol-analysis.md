# 实验 4：Soft-RoCE 与协议抓包分析

> **目标**：**亲手看到** RoCEv2 报文的每一个字节，并逐字段映射到第 2 章的讲解与 `rxe` 的源码。做完这个实验，RoCE 对你就不再是黑盒。
>
> **前置**：[实验 1](lab01-environment-and-first-test.md)（有可用环境，最好已经跑通 `ib_write_bw`）。
> **耗时**：2–3 小时。
> **需要**：普通网卡（不需要 RDMA 网卡）+ root。**本实验完全可用 Soft-RoCE 完成。**

---

## 为什么用 Soft-RoCE 学协议

**`rxe` 是学习 RoCEv2 报文的最佳教材**，原因很直接：

| | 真网卡（mlx5） | **Soft-RoCE（rxe）** |
|---|---|---|
| 报文构造 | 网卡硬件完成，看不到 | **内核 C 代码逐字段构造，可读** |
| 学协议 | 只能靠抓包猜 | **源码 + 抓包互相印证** |
| GID 来源 | 固件 | 内核 GID 表（同一套代码） |
| 性能 | 线速 | 几 Gb/s（无意义） |
| 协议正确性 | 完全合规 | **完全合规**（真的是 UDP 4791 的 RoCEv2 报文） |

> **关键认知**：`rxe` 走的是**真实的内核网络栈**，它发出的包就是标准 RoCEv2 包。你用 Wireshark 看到的、用源码读到的，**和真网卡在网上发的是同一套协议**。

---

## 实验 A：启用 Soft-RoCE

```bash
# root
# ① 加载模块
modprobe rdma_rxe
lsmod | grep rxe
# 若失败：内核需要 CONFIG_RDMA_RXE=m

# ② 绑到一个真实 netdev（找一个 UP 的口）
ip -br link
# 假设是 ens3
rdma link add rxe0 type rxe netdev ens3

# ③ 验证
rdma link show
# 期望：link rxe0/1 state ACTIVE physical_state LINK_UP netdev ens3
ls /sys/class/infiniband/          # 应有 rxe0
ibv_devinfo -d rxe0 -v | head -20

# ④ 看 GID 表（应该和 ens3 的 IP 对应）
ibv_devinfo -d rxe0 -v | grep 'GID\['
# 记下行尾 `, RoCE v2` 且就是 ens3 的 IP 的那一行的 INDEX（GID[  N] 的 N），后面用
# （若你的发行版/OFED 提供 show_gids，也可以：show_gids | grep rxe0）

# ⑤ 确认链路层
cat /sys/class/infiniband/rxe0/ports/1/link_layer      # Ethernet
```

**清理（实验做完再执行）**：

```bash
rdma link delete rxe0
modprobe -r rdma_rxe     # ★ 卸载模块会连带注销所有 rxe 设备（不只 rxe0）
# （kernel:drivers/infiniband/sw/rxe/rxe.c:293-301 的 rxe_module_exit() →
#   rdma_link_unregister() + ib_unregister_driver() + rxe_net_exit()）
# 若这台机器上还有别的实验在用 rxe，先确认再卸；只想删掉这一个设备用上面的 rdma link delete。
```

---

## 实验 B：逐字节解码一个 RoCEv2 报文（本实验核心）

### B1. 抓一个 RDMA WRITE 的包

```bash
# 终端 1（server）
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F -s 1024 -n 100

# 终端 2（client）—— 先起抓包再跑
sudo tcpdump -i ens3 -nn -s 0 -w /tmp/roce-rxe.pcap 'udp port 4791' &
sleep 1
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F -s 1024 -n 100 127.0.0.1
sleep 1; sudo pkill tcpdump

# 用十六进制+ASCII 看一眼前几个包
sudo tcpdump -nn -r /tmp/roce-rxe.pcap -c 2 -X
```

**用 Wireshark 打开**（推荐，会自动解析 InfiniBand 层）：
1. 打开 `roce-rxe.pcap`；
2. 若没自动解析，右键 → `Decode As...` → 选 `INFINIBAND`；
3. 展开 `InfiniBand` 层，对照下面表格逐项核对。

### B2. 完整字段对照表（**边看边填**）

以 **RDMA WRITE Only（MTU 1024）** 的**第一个数据包**为例。请在你的抓包里找到对应字段并填入「你的值」列：

#### ① 以太网层

| 偏移 | 字段 | 长度 | 期望值 | 你的值 | 依据 |
|---|---|---|---|---|---|
| 0 | Dst MAC | 6 B | 对端的 MAC（或本机回环时本机 MAC） | | —— |
| 6 | Src MAC | 6 B | 本机 netdev 的 MAC（`ip link show ens3`） | | —— |
| 12 | EtherType | 2 B | **`0x0800`**（IPv4）；IPv6 则 `0x86DD` | | 第 2.1 节 |
| （可选） | VLAN tag | 4 B | 若有 VLAN 子接口则存在，EtherType 变 `0x8100` | | `IB_VLAN_BYTES = 4` |

> **【关键】RoCEv1 的 EtherType 是 `0x8915`；RoCEv2 用普通的 `0x0800`/`0x86DD`。** 所以看到 `0x0800`+UDP 4791 就是 RoCEv2。

#### ② IP 层

| 字段 | 长度 | 期望值 | 你的值 | 依据 |
|---|---|---|---|---|
| Version / IHL | 1 B | `0x45`（IPv4，头长 20 B） | | —— |
| **TOS / DSCP+ECN** | 1 B | **`tclass` 的值**（perftest `--tclass`；未指定则为 0） | | `rxe_net.c` 用 `av->grh.traffic_class` 填 IP TOS |
| Total Length | 2 B | 20 + 8 + 12 + payload + 4（ICRC） | | 第 2.1 节的开销算式 |
| **TTL** | 1 B | **`hop_limit` 的值** | | `rxe_net.c` 用 `av->grh.hop_limit` 填 TTL |
| Protocol | 1 B | **`17`（UDP）** | | —— |
| Checksum | 2 B | 正常 IPv4 校验和 | | —— |
| Src IP | 4 B | **= 你选的 GID 对应的 IP**（本实验是 `127.0.0.1` 或 ens3 的 IP） | | GID 决定源 IP |
| Dst IP | 4 B | 对端 IP | | —— |

> **【源码印证】打开 `kernel:drivers/infiniband/sw/rxe/rxe_net.c`**：
> - `prepare_ipv4_hdr()` 的参数里有 `__u8 tos` 和 `__u8 ttl`，调用处传入 `av->grh.traffic_class` 与 `av->grh.hop_limit`（见 `prepare4()`）。
> - **这就是「GRH 的 traffic_class 就是 IP TOS、hop_limit 就是 IP TTL」的源码证据**。

#### ③ UDP 层

| 字段 | 长度 | 期望值 | 你的值 | 依据 |
|---|---|---|---|---|
| Src Port | 2 B | **落在 `0xC000–0xFFFF`（49152–65535）** | | 见下面的源码分析 |
| **Dst Port** | 2 B | **`4791`** | | `ROCE_V2_UDP_DPORT` |
| Length | 2 B | UDP 头 + BTH + 扩展头 + payload + ICRC | | —— |
| **Checksum** | 2 B | **`0x0000`**（或 Wireshark 报 "Illegal"） | | `rxe_net.c` 的 `prepare_udp_hdr()` 显式把 `check` 置 0 |

> **【常见困惑】Wireshark 报 "UDP checksum incorrect/illegal" —— 这是正常的，不是故障。**
> RoCEv2 的完整性由 **ICRC** 保证，主流实现（含真网卡）都不算 UDP 校验和。
>
> **【源码印证】`rxe_net.c` 的 `prepare_udp_hdr()`**：
> ```c
> static void prepare_udp_hdr(struct sk_buff *skb, __be16 src_port, __be16 dst_port)
> {
>         ...
>         udph->dest   = dst_port;
>         udph->source = src_port;
>         udph->len    = htons(skb->len);
>         udph->check  = 0;            /* ★ 校验和显式置 0 */
> }
> ```
> 调用处：`prepare_udp_hdr(skb, cpu_to_be16(qp->src_port), cpu_to_be16(ROCE_V2_UDP_DPORT));`
> 其中 `ROCE_V2_UDP_DPORT` 定义在 `kernel:include/rdma/ib_verbs.h:151`（值为 **4791**）。

**源端口是怎么来的**（`kernel:drivers/infiniband/sw/rxe/rxe_qp.c:306`）：

```c
/* kernel:drivers/infiniband/sw/rxe/rxe_qp.c:306 —— QP 创建时算出的源端口【初值】 */
qp->src_port = RXE_ROCE_V2_SPORT + (hash_32(qp_num(qp), 14) & 0x3fff);
/* kernel:drivers/infiniband/sw/rxe/rxe.h:38 */
#define RXE_ROCE_V2_SPORT  (0xc000)          /* ★ 这就是 0xC000 的来源 */
```

> **要把两个时刻分清，否则会读错机制**：
> - **创建时（初值）**：`rxe_qp.c:306` 用 QPN 做 `hash_32(..., 14)` 得 14 bit，再加基址 `0xC000`；
> - **改 QP 时（会覆盖它）**：`kernel:drivers/infiniband/sw/rxe/rxe_verbs.c:623-626` 在 `modify_qp` 带 `IB_QP_AV` 且 `attr->ah_attr.ah_flags & IB_AH_GRH` 时，用 ib_core 的统一算法**重算并覆盖**上面的初值：
>   ```c
>   qp->src_port = rdma_get_udp_sport(attr->ah_attr.grh.flow_label,
>                                     qp->ibqp.qp_num,
>                                     qp->attr.dest_qp_num);
>   ```
>   `rdma_get_udp_sport()`（`kernel:include/rdma/ib_verbs.h:5119-5125`）在 `flow_label` 非 0 时直接用它，否则用 `rdma_calc_flow_label(lqpn, rqpn) = fold(lqpn × rqpn)`（对称乘法哈希，`ib_verbs.h:5100-5108`）。
>
> **所以两种实现都真实存在**：`hash_32` 是创建时的初值，而**真实用户态流量（QP 都要 modify_qp→RTR 带 GRH AV）走的是 ib_core 这一套**——真网卡同样用后者，只是算在驱动里（第 2.7 节）。
> **结论不变**：单个 QP 的源端口在一条连接内固定，且必然落在 `0xC000` 以上 —— `0xC000–0xFFFF` 是 IANA 的**动态/私有端口区**，IBTA 的 RoCEv2 规范选取这个区间作为 RoCEv2 的 UDP 源端口范围（内核宏 `IB_ROCE_UDP_ENCAP_VALID_PORT_MIN` / `_MAX`，`kernel:include/rdma/ib_verbs.h:5064-5065`）。

#### ④ BTH —— 基础传输头（12 字节，**所有 RoCE 包都有**）

| 偏移（相对 BTH 起点） | 字段 | 长度 | 期望值 | 你的值 | 依据 |
|---|---|---|---|---|---|
| +0 | **Opcode** | 1 B | **`0x0a`** = RC RDMA_WRITE_ONLY | | `ib_pack.h` |
| +1 | Flags | 1 B | `SE`(bit7) / `MIG`(bit6) / `pad`(bit5-4) / `TVer`(bit3-0，通常 0) | | `rxe_hdr.h` 的 `BTH_PAD_MASK = 0x30`、`BTH_TVER_MASK = 0x0f` |
| +2 | PKey | 2 B | 通常 **`0xffff`** | | `BTH_DEF_PKEY` |
| +4 | QPN 字段（高 8 位） | 1 B | 含 **FECN**(bit31) / **BECN**(bit30) / 保留 | | `BTH_FECN_MASK = 0x80000000`、`BTH_BECN_MASK = 0x40000000` |
| +5 | **Dest QPN**（低 24 位） | 3 B | **应等于 server 打印的 `qp_num`** | | `BTH_QPN_MASK = 0x00ffffff` |
| +8 | APSN 字段 | 4 B | bit31 = **AckReq**；低 24 位 = **PSN** | | `BTH_ACK_MASK = 0x80000000`、`BTH_PSN_MASK = 0x00ffffff` |

**核对方法（很重要）**：

```bash
# 1) 让 server 打印它的 QPN
#    perftest 的输出里会显示 QPN；或用实验 F 的 minfo 类程序
# 2) 在 Wireshark 里看 BTH 的 Destination QP 是否一致
# 3) 看 PSN 是否逐包递增（验证可靠传输的序列号机制）
```

> **【源码印证】`kernel:drivers/infiniband/sw/rxe/rxe_hdr.h` 的 `struct rxe_bth`**：
> ```c
> struct rxe_bth {
>         u8      opcode;
>         u8      flags;
>         __be16  pkey;
>         __be32  qpn;      /* 高 8 位 FECN/BECN/保留 + 低 24 位 QPN */
>         __be32  apsn;     /* 高 1 位 AckReq + 低 24 位 PSN */
> };
> ```
> 掩码常量紧随其后（`BTH_SE_MASK`、`BTH_MIG_MASK`、`BTH_PAD_MASK`、`BTH_TVER_MASK`、
> `BTH_FECN_MASK`、`BTH_BECN_MASK`、`BTH_QPN_MASK`、`BTH_ACK_MASK`、`BTH_PSN_MASK`）。
> **`bth_init()` 就是逐字段填这个结构的函数。**

#### ⑤ RETH —— RDMA 扩展传输头（16 字节，**仅单边操作有**）

| 字段 | 长度 | 期望值 | 你的值 | 依据 |
|---|---|---|---|---|
| **Virtual Address** | 8 B | **对端注册缓冲的虚拟地址**（perftest 交换来的 `vaddr`） | | `rxe_hdr.h` 的 `struct rxe_reth` |
| **RKey** | 4 B | **对端 MR 的 `rkey`** | | 同上 |
| DMA Length | 4 B | 本条消息的长度（≤ MTU） | | 同上 |

```c
/* kernel:drivers/infiniband/sw/rxe/rxe_hdr.h */
struct rxe_reth {
        __be64  va;
        __be32  rkey;
        __be32  len;
};
```

> **【这是全书最重要的三个字段】** RETH 的 `va` + `rkey` + `len` **就是对端网卡要做的全部事情**：
> 用 `rkey` 查 MPT 拿权限与物理地址 → 校验 `va` 落在注册范围内 → DMA 写 `len` 字节。
> **`rkey` 泄露 = 内存可被任意读写**（第 14 章）。

#### ⑥ Payload 与 ICRC

| 字段 | 长度 | 期望值 | 你的值 | 依据 |
|---|---|---|---|---|
| Payload | ≤ MTU | 数据（perftest 填的是随机数或递增模式） | | —— |
| Padding | 0–3 B | 使 payload 4 字节对齐；字节数由 BTH 的 `pad` 字段指示 | | `BTH_PAD_MASK` |
| **ICRC** | **4 B** | 非零；是**不变式 CRC** | | 见实验 C |

> **【数一数】** 一个 MTU 1024 的 RDMA WRITE 包，总长度应该是多少？
> ```
> Ethernet 14 + IPv4 20 + UDP 8 + BTH 12 + RETH 16 + payload 1024 + padding 0 + ICRC 4 = 1098 字节
> ```
> **在 Wireshark 里核对 `Frame length`，与上式对比。** 如果对不上，检查你的 MTU 与是否有 VLAN 标签。

### B3. 数一数分片（理解 IB 传输层的分片）

```bash
# 看一个 8192 字节的 WRITE 被拆成几个包
# 先用 MTU 1024 跑 -s 8192
# server: ib_write_bw -d rxe0 -i 1 -x <IDX> --mtu=1024 -s 8192 -n 10 -F
# client: ib_write_bw ... -s 8192 -n 10 -F 127.0.0.1
# 然后统计 pcap 里的包数与 opcode 分布
```

**填空**：

| 项 | 你的值 |
|---|---|
| 消息大小 | 8192 B |
| MTU | 1024 B |
| 理论包数（8192 / 1024） | 8 |
| 实测包数 | |
| Opcode 分布（FIRST/MIDDLE/LAST/ONLY） | |

**对照 `ib_pack.h` 的 opcode**（RC 传输）：

| opcode | 含义 |
|---|---|
| `0x06` | RC RDMA_WRITE_FIRST |
| `0x07` | RC RDMA_WRITE_MIDDLE |
| `0x08` | RC RDMA_WRITE_LAST |
| `0x0a` | RC RDMA_WRITE_ONLY |
| `0x11` | RC ACKNOWLEDGE |

> **【重要理解】这不是 IP 分片，是 IB 传输层自己的分片。** 每个分片有独立的 PSN，但 RC 的重传是 **Go-Back-N**：一旦 NAK/超时，从最早未被确认的 PSN（`qp->req.psn`）起把在途的包**整段重发**（`kernel:drivers/infiniband/sw/rxe/rxe_comp.c:782-792`；NAK 只带期望 PSN，见 `rxe_resp.c:1648`），**不是「丢一个只重传一个」的选择性重传**。相比 IP 分片丢一个要整包重来，IB 分片仍更细、更可控，但代价是可能重发多个包。

---

## 实验 C：验证 ICRC 的「不变式」特性

### C1. 理解 ICRC 覆盖什么

```c
/* kernel:drivers/infiniband/sw/rxe/rxe_icrc.c 的 rxe_icrc_hdr() */
/* 参与计算的字段（复制到临时缓冲，未修改）： */
/*   整个 IP 头、UDP 头、BTH */
/* 被屏蔽（改成常量）的字段： */
ip4h->ttl    = 0xff;          /* IPv4 TTL 被屏蔽 */
ip4h->check  = CSUM_MANGLED_0;/* IPv4 校验和被屏蔽 */
ip4h->tos    = 0xff;          /* IPv4 TOS 被屏蔽 */
udph->check  = CSUM_MANGLED_0;/* UDP 校验和被屏蔽 */
/* IPv6 时：flow_lbl → 0xff...、priority → 0xf、hop_limit → 0xff */
/* BTH：qpn 字段的高 8 位（FECN/BECN/保留）被置 1，只保留低 24 位 QPN */
bth->qpn |= cpu_to_be32(~BTH_QPN_MASK);
/* 然后继续 CRC 到扩展头与 payload */
```

**CRC 初值与收尾**（源码注释说明）：
```c
/* This seed is the result of computing a CRC with a seed of
 * 0xfffffff and 8 bytes of 0xff representing a masked LRH. */
crc = (__force __be32)0xdebb20e3;
/* ... */
*icrcp = ~icrc;     /* 最后取反 */
```

**算出三条推论**（在源码里都能验证）：

| 推论 | 原因 |
|---|---|
| **改以太网头（MAC/VLAN）不影响 ICRC** | 以太网头**完全不参与** ICRC 计算 |
| **改 IP 地址会导致 ICRC 校验失败** | 源/目的 IP **参与**计算 |
| **TTL/TOS/校验和变化不影响 ICRC** | 这些字段被屏蔽成常量 |

### C2. 亲手验证（两种方式）

**方式一：改以太网 MAC（应该仍然通过）**

```bash
# 前提：安装了 tcpreplay / tcprewrite（或 scapy）
# 复制一份 pcap，改掉目的 MAC，然后重放给协议栈
cp /tmp/roce-rxe.pcap /tmp/roce-macmod.pcap
tcprewrite --enet-dmac=aa:bb:cc:dd:ee:ff --infile=/tmp/roce-rxe.pcap \
           --outfile=/tmp/roce-macmod.pcap

# 关键问题：内核 rxe 收到这个包会怎么样？
#   → ICRC 仍然正确（MAC 不参与），但目的 MAC 不匹配 → 网卡/协议栈直接丢弃（不到 ICRC 校验）
#   所以这个实验在 rxe 上只能观察到"MAC 不匹配丢弃"，不能直接证明 ICRC 通过。
```

**方式二：对比 ICRC 的「参与字段集合」（推荐，可确定性验证）**

这个方式不需要重放，直接算：

```bash
# ① 从 pcap 里取出一个包的完整字节
sudo tcpdump -nn -r /tmp/roce-rxe.pcap -c 1 -w /tmp/one.pkt 'udp port 4791'

# ② 用 Python 逐字段分析（不需要 scapy，纯 struct）
python3 - <<'PY'
import struct, zlib

data = open('/tmp/one.pkt','rb').read()
# pcap 文件头 24 字节 + 包记录头 16 字节
rec_len = struct.unpack_from('<I', data, 24+8)[0]
pkt = data[24+16 : 24+16+rec_len]

eth_len = 14
ip  = pkt[eth_len:]
ihl = (ip[0] & 0x0f) * 4
proto = ip[9]
src = '.'.join(map(str, ip[12:16]))
dst = '.'.join(map(str, ip[16:20]))
tos = ip[1]; ttl = ip[8]

udp = ip[ihl:]
sport, dport, ulen, uck = struct.unpack_from('>HHHH', udp, 0)

bth = udp[8:]
opcode = bth[0]
flags  = bth[1]
pkey   = struct.unpack_from('>H', bth, 2)[0]
qpn_f  = struct.unpack_from('>I', bth, 4)[0]
apsn   = struct.unpack_from('>I', bth, 8)[0]

print(f"EtherType   : 0x{struct.unpack_from('>H', pkt, 12)[0]:04x}  (IPv4=0x0800)")
print(f"IP  TOS     : 0x{tos:02x}  -> DSCP={tos>>2} ECN={tos&3}")
print(f"IP  TTL     : {ttl}")
print(f"IP  Src/Dst : {src} -> {dst}")
print(f"UDP SrcPort : {sport}  (0x{sport:04x})  in-range(0xC000-0xFFFF): {sport>=0xC000}")
print(f"UDP DstPort : {dport}  (should be 4791)")
print(f"UDP Checksum: 0x{uck:04x}  (RoCEv2 通常为 0)")
print(f"BTH Opcode  : 0x{opcode:02x}")
print(f"BTH Flags   : 0x{flags:02x}  SE={flags>>7} MIG={(flags>>6)&1} pad={(flags>>4)&3} TVer={flags&0xf}")
print(f"BTH PKey    : 0x{pkey:04x}")
print(f"BTH QPN     : 0x{qpn_f & 0x00ffffff:06x}   FECN={qpn_f>>31} BECN={(qpn_f>>30)&1}")
print(f"BTH PSN     : {apsn & 0x00ffffff}   AckReq={apsn>>31}")
# ★ Payload 长度必须按 opcode 分支：带扩展头的报文要把扩展头也减掉
#   SEND 类（0x00-0x05）：无扩展头                        → ulen - 8 - 12 - 4
#   WRITE 类（0x06-0x0b）、READ REQUEST（0x0c）：RETH 16B  → ulen - 8 - 12 - 16 - 4
#   READ RESPONSE 类（0x0d-0x10）：AETH 4B                → ulen - 8 - 12 - 4 - 4
#   ATOMIC 请求（0x13 COMPARE_SWAP / 0x14 FETCH_ADD）：AtomicETH 28B → ulen - 8 - 12 - 28 - 4
#   （RETH 布局见 rxe_hdr.h:526-530；AETH 见 :773-775；AtomicETH 见 :659-664）
EXT = {**{o: 0 for o in range(0x00, 0x06)},
       **{o: 16 for o in range(0x06, 0x0d)},
       **{o: 4 for o in range(0x0d, 0x11)},
       0x13: 28, 0x14: 28}
ext = EXT.get(opcode, 0)
print(f"Payload len : {ulen - 8 - 12 - ext - 4}  (UDP len - UDP hdr - BTH - 扩展头({ext}B) - ICRC)")
print(f"  （本实验抓的是 RDMA WRITE，opcode=0x0a → ext=16，即 ulen-8-12-16-4；只有 SEND 才是 ulen-8-12-4）")
print(f"ICRC        : 0x{struct.unpack_from('>I', bth, ulen-8-4)[0]:08x}")
PY
```

**把输出与 B2 的表格对照。** 这就是「逐字节解码」的可复现版本。

**方式三：用 Wireshark 的字段过滤验证结构**

在 Wireshark 的显示过滤器里尝试：

```
# 只看 RDMA WRITE Only
ib.opcode == 0x0a

# 只看 PSN 在某个范围
ib.psn > 1000

# 只看某个 QPN
ib.dest_qp == 0x0000a1

# 看所有带 GRH 的包（UD）—— 本实验是 RC，应该没有
ib.flags.grh == 1
```

> **【如果 Wireshark 没自动解析】** 用 `Decode As...` 手动指定 UDP 4791 为 `INFINIBAND`；或检查你的 Wireshark 版本是否支持 RoCEv2 解析（较新版本都支持）。

---

## 实验 D：验证 ECMP 熵（源端口的分散性）

### D1. 多 QP 的源端口分布

```bash
# 用 4 个 QP 跑一次
# server: ib_write_bw -d rxe0 -i 1 -x <IDX> --report_gbits -F -q 4 -s 512 -n 500
# client: ib_write_bw ... -q 4 -s 512 -n 500 -F 127.0.0.1
# 同时抓包

sudo tcpdump -i ens3 -nn -s 0 -w /tmp/roce-qp4.pcap 'udp port 4791' &
sleep 1
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F -q 4 -s 512 -n 500 127.0.0.1
sleep 1; sudo pkill tcpdump

# 提取源端口，看有几个不同的值
sudo tcpdump -nn -r /tmp/roce-qp4.pcap 'udp port 4791' 2>/dev/null \
  | awk '{print $3}' | sed 's/.*\.\([0-9]*\)$/\1/' | sort -n | uniq -c | sort -rn
```

**填空**：

| 项 | 你的值 |
|---|---|
| QP 数 | 4 |
| 不同的源端口数 | |
| 每个源端口的包数（大致） | |
| 源端口是否都在 0xC000–0xFFFF | |
| 是否符合 `0xC000 + (hash_32(qpn,14) & 0x3fff)`（创建时初值） | |
| 是否符合 ib_core 算法 `rdma_get_udp_sport(flow_label, lqpn, rqpn)`（RTR 后生效） | |

> **【源码印证】** 回到 `rxe_qp.c`（**创建时初值**）：
> ```c
> qp->src_port = RXE_ROCE_V2_SPORT + (hash_32(qp_num(qp), 14) & 0x3fff);
> ```
> 但 QP 一旦 `modify_qp → RTR` 且带 GRH AV，这个初值会被 `rxe_verbs.c:623-626` 用 `rdma_get_udp_sport(flow_label, lqpn, rqpn)` **覆盖**（见实验 B 的说明），所以抓到的真实流量**通常按 ib_core 算法**生成源端口。
> 两种算法的共同点是：结果都落在 `[0xC000, 0xFFFF]`（`hash_32(...) & 0x3fff` 落在 `[0, 0x3fff]`；`rdma_flow_label_to_udp_sport()` 最后或上 `IB_ROCE_UDP_ENCAP_VALID_PORT_MIN`）。
> **所以「RoCEv2 的 UDP 源端口 ≥ 0xC000」是一个可以硬编码检查的判据。**

### D2. 单 QP 的源端口是固定的（解释 ECMP 问题）

```bash
# 只跑 1 个 QP，反复测，观察源端口
for i in 1 2 3; do
  sudo tcpdump -i ens3 -nn -c 20 -w /tmp/one-qp-$i.pcap 'udp port 4791' 2>/dev/null &
  sleep 0.5
  ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F -s 512 -n 50 127.0.0.1 >/dev/null
  sleep 0.5; sudo pkill tcpdump
  echo -n "run $i src ports: "
  sudo tcpdump -nn -r /tmp/one-qp-$i.pcap 'udp port 4791' 2>/dev/null \
    | awk '{print $3}' | sed 's/.*\.\([0-9]*\)$/\1/' | sort -u | tr '\n' ' '
  echo
done
```

**结论（写下来）**：

> 单个 QP 的源端口在**一次连接内是固定的**（创建时算一次存入 `qp->src_port`，`modify_qp → RTR` 带 GRH AV 时由 ib_core 算法覆盖一次，之后不再变）。
> 因此**单个 QP = 单一 5 元组 = ECMP 只能选一条路径**。
> **这就是「单 QP 带宽 ≈ 链路带宽 ÷ ECMP 路径数」的根本原因**（第 12.6.3 节）。

---

## 实验 E：读 `rxe` 源码（问题驱动）

**不要从第一行读到最后一行。** 带着下列问题去读：

| # | 问题 | 去看 | 你要找的答案 |
|---|---|---|---|
| 1 | UDP 目的端口 4791 定义在哪？ | `kernel:include/rdma/ib_verbs.h` 搜 `ROCE_V2_UDP_DPORT` | 常量定义 |
| 2 | UDP 头是怎么填的？校验和呢？ | `kernel:drivers/infiniband/sw/rxe/rxe_net.c` 的 `prepare_udp_hdr()` | `udph->check = 0` |
| 3 | IP 的 TOS 和 TTL 从哪来？ | 同文件 `prepare_ipv4_hdr()` 与 `prepare4()` | `av->grh.traffic_class` / `av->grh.hop_limit` |
| 4 | 源端口怎么算？ | `kernel:drivers/infiniband/sw/rxe/rxe_qp.c` 搜 `src_port`（再看 `rxe_verbs.c:623-626` 的覆盖） | 创建时 `RXE_ROCE_V2_SPORT + (hash_32(...) & 0x3fff)`；RTR 后 `rdma_get_udp_sport(flow_label, lqpn, rqpn)` |
| 5 | `0xc000` 定义在哪？ | `kernel:drivers/infiniband/sw/rxe/rxe.h` 搜 `RXE_ROCE_V2_SPORT` | `#define RXE_ROCE_V2_SPORT (0xc000)` |
| 6 | BTH 的位掩码有哪些？ | `kernel:drivers/infiniband/sw/rxe/rxe_hdr.h` | `BTH_SE_MASK`、`BTH_PAD_MASK`、`BTH_FECN_MASK`、`BTH_QPN_MASK`、`BTH_ACK_MASK`、`BTH_PSN_MASK` … |
| 7 | RETH 有哪三个字段？ | 同文件搜 `struct rxe_reth` | `va` / `rkey` / `len` |
| 8 | AETH 的 syndrome 取值？ | 同文件搜 `enum aeth_syndrome` | `AETH_ACK 0x00`、`AETH_RNR_NAK 0x20`、`AETH_NAK 0x60`、`AETH_NAK_PSN_SEQ_ERROR 0x60`、`AETH_NAK_INVALID_REQ 0x61`、`AETH_NAK_REM_ACC_ERR 0x62`、`AETH_NAK_REM_OP_ERR 0x63` |
| 9 | ICRC 屏蔽了哪些字段？ | `kernel:drivers/infiniband/sw/rxe/rxe_icrc.c` 的 `rxe_icrc_hdr()` | `ttl/tos/check/flow_lbl/priority/hop_limit/udp check` + BTH 高 8 位 |
| 10 | ICRC 的初值是多少？ | 同文件 | `0xdebb20e3`（注释解释了它的来历） |
| 11 | opcode 表在哪？ | `kernel:drivers/infiniband/sw/rxe/rxe_opcode.c` | `rxe_opcode[]` 与 `rxe_wr_opcode_info[]` |
| 12 | opcode 的传输类型怎么编码？ | `kernel:include/rdma/ib_pack.h` | 高 3 位是传输类型（RC=0x00、UC=0x20、RD=0x40、UD=0x60、CNP=0x80） |

**练习：把上面 12 个答案写成一页笔记。** 这一页就是你的 RoCE 报文速查表。

---

## 实验 F：Soft-RoCE vs 真网卡对比

如果你有真网卡，跑同一组测试做对比：

```bash
# ① rxe
ib_write_bw -d rxe0 -i 1 -x <rxe_gid> --report_gbits -F -s 65536 -n 1000 127.0.0.1
ib_write_lat -d rxe0 -i 1 -x <rxe_gid> -F -n 1000 127.0.0.1

# ② 真卡（两台机器）
ib_write_bw -d mlx5_0 -i 1 -x <gid> --report_gbits -F -s 65536 -n 1000 <peer>
ib_write_lat -d mlx5_0 -i 1 -x <gid> -F -n 1000 <peer>
```

**对比表（自己填）**：

| 项 | `rxe0`（Soft-RoCE） | `mlx5_0`（真卡） | 倍数 |
|---|---|---|---|
| `ib_write_bw -s 65536` BW | | | |
| `ib_write_lat` t_avg | | | |
| CPU 占用（`--cpu_util`） | | | |

**解释差异（这是重点，不是数字）**：

| 为什么 `rxe` 慢 | 对应真卡的做法 |
|---|---|
| 每个包都要经过内核网络栈（skb 分配、协议栈处理） | 网卡硬件直接生成报文 |
| WQE 由内核软件解析（`rxe_req.c`） | 网卡解析 WQE |
| 数据要 memcpy 到 skb | 网卡直接 DMA |
| 轮询/中断走内核（软中断） | 用户态直接轮询 CQ（mmap） |
| ICRC 由 CPU 算 | 网卡硬件算 |

> **【关键洞察】这个对比表就是「RDMA 为什么快」的答案。**
> 它不是魔法，是把「协议栈处理 + 内存拷贝 + 中断」全部搬到了硬件。**`rxe` 恰好把这些工作留在了软件里，所以你能看到差距有多大。**

---

## 故障速查（本实验最可能遇到的问题）

| 症状 | 最可能原因 | 处理 |
|---|---|---|
| `modprobe rdma_rxe` 失败 | 内核未编译 `CONFIG_RDMA_RXE` | 换发行版内核，或自行编译该模块 |
| `rdma link add` 报 `No such device` | netdev 名字错 / 未 UP | `ip -br link` 确认；`ip link set <dev> up` |
| 抓不到 UDP 4791 的包 | **抓错网卡**（RoCE 走 netdev，不是 `lo`） | 用 `rdma link show` 找到绑定的 netdev |
| Wireshark 不解析 InfiniBand | 版本或端口映射 | 右键 `Decode As...` → `INFINIBAND` |
| Wireshark 报 UDP checksum 错 | **正常现象** | 忽略（RoCEv2 用 ICRC，不算 UDP 校验和） |
| 源端口不在 0xC000 以上 | 不是 RoCEv2（可能是别的 UDP 流量） | 确认目的端口是 4791；确认没有混入其他流量 |
| 看到 EtherType `0x8915` | 这是 **RoCEv1**，不是 v2 | 检查 GID 选的是 v1 还是 v2（`ibv_devinfo -v` 的 `GID[  N]` 行尾 `, RoCE v1/v2`；或 `show_gids` 的 VER 列，若提供） |
| 8192 字节消息的包数与预期不符 | MTU 被自动协商成更小值 | 看 perftest 输出里的 MTU 值；显式 `--mtu=1024` |
| Python 解析脚本报 `IndexError` | pcap 里有非 RoCE 包（如 ARP） | 用 `'udp port 4791'` 过滤后再抓 |

---

## 本实验的「完成标准」

- [ ] 成功启用 `rxe0`，并确认 `link_layer = Ethernet`
- [ ] 抓到 RoCEv2 报文，并在 Wireshark 里**逐项填完** B2 的字段对照表
- [ ] 能说出 UDP 目的端口（4791）、源端口范围（0xC000–0xFFFF）及其来源
- [ ] 能指出 BTH 的 Opcode / Dest QPN / PSN / AckReq，并与 server 的 QPN 核对一致
- [ ] 能指出 RETH 的三个字段，并解释对端网卡用它们做什么
- [ ] 用 Python 脚本逐字段解析了一个包，输出与 Wireshark 一致
- [ ] 完成实验 C，能说出 ICRC 覆盖/屏蔽哪些字段、以及三条推论
- [ ] 完成实验 D，能用源码解释「单 QP 源端口固定 → ECMP 单路径」
- [ ] 完成实验 E 的 12 个问题，写下自己的一页速查表
- [ ] （有真卡时）完成实验 F 的对比表，能解释每一处差异的原因

---

## 下一步

- 把协议理解用到编程上 → [第 4 章](../04-verbs-model.md)、[第 5 章](../05-hands-on-code.md)、[实验 2](lab02-verbs-programming.md)
- 把 ECMP 的理解用到性能调优 → [第 12 章](../12-troubleshooting.md)、[实验 3](lab03-tuning-and-troubleshooting.md)
- 把 `rkey` 的理解用到安全 → [第 14 章](../14-security.md)、[实验 5](lab05-security-and-observability.md)
