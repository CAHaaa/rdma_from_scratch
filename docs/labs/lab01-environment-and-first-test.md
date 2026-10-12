# 实验 1：搭建你的第一套 RoCE 环境（含 Soft-RoCE 仿真）

> **目标**：在**没有 RDMA 网卡**的情况下，也能完整跑通 RoCE 数据路径，并亲眼看到 RoCEv2 报文。
> **前置**：Ubuntu 22.04/24.04 或 RHEL 9（x86_64），内核 ≥ 5.10，有 root 权限。
> **耗时**：30–60 分钟。
>
> 本实验是后续所有实验的基础。做完它，你将拥有：
> - 一个可用的 verb 设备（真网卡或 `rxe0`）
> - 一套可用的 perftest / rdma-core 工具
> - 一次成功的带宽/时延测试
> - 一次真实的 RoCEv2 抓包

---

## 实验 A：准备工具链（两种路线，选一）

### 路线 1：发行版包（最快，推荐首次使用）

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install -y rdma-core ibverbs-utils ibverbs-providers \
                    perftest infiniband-diags iproute2 tcpdump \
                    libibverbs-dev librdmacm-dev build-essential cmake

# RHEL / Rocky / Alma
sudo dnf install -y rdma-core libibverbs-utils librdmacm-utils perftest \
                    infiniband-diags iproute tcpdump libibverbs-devel \
                    librdmacm-devel gcc make cmake
```

验证安装：

```bash
ibv_devinfo -l          # 列出 RDMA 设备（此时可能为空或只有真卡）
ibv_devinfo -v | head   # 详细属性
which ib_write_bw ib_send_lat   # 应能找到这些命令（perftest 提供）
```

> **关于 `show_gids`**：这个脚本**不在 rdma-core 仓库里**（历史上属于 OFED 脚本集），所以「装上 `rdma-core` 就一定有 `show_gids`」不成立。若你的发行版/OFED 恰好提供了它，可以直接用；否则**本实验统一用 `ibv_devinfo -v`（其 GID 段的格式见 `rdma-core:libibverbs/examples/devinfo.c:188-227`）或实验 F 的 `minfo.c` 看 GID 表**，两者等价。

### 路线 2：从本仓源码编译（想读代码/改代码时用）

```bash
# 编译 rdma-core（用户态库）
cd rdma-core-master
mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
sudo make install
sudo ldconfig

# 编译 perftest（应用）
cd ../../perftest-master/perftest-master
./autogen.sh        # 若没有 configure 脚本
./configure --prefix=/usr
make -j$(nproc)
sudo make install
```

> **常见编译错误**：缺少 `libnuma-dev`、`libpci-dev`、`libnl-3-dev`、`libnl-route-3-dev`、`python3-dev`。按提示补装即可。

---

## 实验 B：真网卡路线 —— 确认 RoCE 已就绪

```bash
# root 或 sudo

# 1) 确认驱动加载
lsmod | grep -E 'mlx5_ib|mlx5_core'
# 期望：mlx5_ib 和 mlx5_core 都在

# 2) 找到 netdev 与 ibdev 的对应关系
# ★ 最可靠的一条命令（直接给出 ibdev ↔ netdev 绑定）
rdma link show
# 输出示例：
#   link mlx5_0/1 state ACTIVE physical_state LINK_UP netdev enp1s0f0
ibdev2netdev 2>/dev/null || ip -br link
ls /sys/class/infiniband/
# 期望：看到 mlx5_0 / mlx5_1（RoCE LAG 激活时会看到 mlx5_bond_0）
# 注意：部分发行版 / MLNX_OFED 会用 udev 规则改名为 roceP1p1s0f0 这类「带 PCI 槽位」的名字，
#       而主流上游内核注册的是 mlx5_%d。不要靠名字猜对应关系，用上面的 rdma link show。

# 3) 给业务网口配 IP（如果是新建环境）
ip addr add 192.168.100.1/24 dev <netdev>
ip link set <netdev> up

# 4) 关键一步：确认 GID 表已经根据 IP 自动生成
ibv_devinfo -d <ibdev> -v | grep 'GID\['
# 期望输出（示例）：
#   GID[  0]:        fe80:0000:...:ee01
#   GID[  1]:        fe80:0000:...:ee01
#   GID[  2]:        ::ffff:192.168.100.1, RoCE v2
#                                          ^^^^^^^^^^^^^
#                                          这一行才是你要用的 RoCEv2 GID（INDEX = 2）
#
# 说明（格式由 rdma-core:libibverbs/examples/devinfo.c:188-227 决定）：
#   * `GID[  N]` 的 N 就是 GID 索引（perftest 的 -x）；
#   * v1 行打印 16 字节十六进制，v2 行打印 `::ffff:a.b.c.d`（最后 4 字节就是 IPv4）；
#   * 行尾 `, RoCE v1` / `, RoCE v2` 由 ibv_query_gid_type() 得到（devinfo.c:220）。
```

### 怎么读 GID 表（下面以 `show_gids` 的列为例，**这是本实验最重要的技能**）

> **【工具来源与版本差异】** `show_gids` **不在 rdma-core 仓库**（历史属 OFED 脚本集），列名与格式随发行版/OFED 版本可能不同。下表用它的列是为了把「索引 / IPv4 / 版本」讲清楚；没有它时用 `ibv_devinfo -v` 的 `GID[  N]:` 行（N = INDEX，`::ffff:` 后的点分十进制 = IPv4，行尾 `, RoCE v2` = VER）或本实验 F 的 `minfo.c` 得到同样信息。

| 列 | 含义 | 怎么用 |
|---|---|---|
| `DEV` | ibdev 名 | perftest 的 `-d` |
| `PORT` | 端口号 | perftest 的 `-i`（通常 1） |
| `INDEX` | **GID 索引** | **perftest 的 `-x <INDEX>`** |
| `GID` | 128 bit 全局标识 | IPv4 场景下最后 4 字节是 IP |
| `IPv4` | 该 GID 对应的 IP | **必须是业务网 IP** |
| `VER` | `v1`（RoCEv1）或 `v2`（RoCEv2） | **RoCEv2 选 `v2`** |
| `DEV`（末列） | 对应 netdev | 用来确认走的是哪个物理口 |

**选择规则（背下来）**：

```
要跑 RoCEv2 → 找 VER = v2 的行
             → 且 IPv4 列 = 你配的业务网 IP
             → 记下它的 INDEX，作为 -x 参数
```

**查看端口状态**：

```bash
ibv_devinfo -d <ibdev> -v | grep -Ei 'state|phys_state|link_layer|active_mtu|max_mtu|port_lid'
# 期望：
#   state:            PORT_ACTIVE (4)
#   phys_state:       LINK_UP (5)
#   link_layer:       Ethernet        ← 必须是以太网
#   active_mtu:       1024 (or 4096)
```

> **如果 `link_layer` 是 `InfiniBand`**，说明你连的是 IB 交换机/IB 模式，不是 RoCE。检查网卡端口配置（`mlxconfig` 的 `LINK_TYPE`）与线缆。

---

## 实验 C：Soft-RoCE 路线 —— 没有网卡也能做

```bash
# root

# 1) 加载软件 RoCE 模块
modprobe rdma_rxe
# 若无此模块：apt install rdma-core 后仍缺，需内核开启 CONFIG_RDMA_RXE=m

# 2) 绑定到一个真实 netdev（loopback 也可以，但真实口更接近实际）
ip -br link                      # 找一个 UP 的口，比如 ens3
rdma link add rxe0 type rxe netdev ens3 || { echo "创建 rxe 失败，见 3.6/本节排障"; exit 1; }

# 3) 验证
rdma link show
# 期望：link rxe0/1 state ACTIVE physical_state LINK_UP netdev ens3
ibv_devinfo -d rxe0 -v | head -20

# 4) 查看 rxe 的 GID（应与 ens3 的 IP 对应）
ibv_devinfo -d rxe0 -v | grep 'GID\['
# 若你的发行版/OFED 提供 show_gids，也可以：show_gids | grep rxe0
```

**单机自测（loopback，能验证代码正确性）**：

```bash
# 终端 1：服务端
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F

# 终端 2：客户端（连到本机 IP 即可）
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F 127.0.0.1
```

> **注意**：`rxe` 走内核网络栈，性能很低（几 Gb/s 量级），**测性能没有意义，但测功能和协议完全有效**。它跑的是真正的 RoCEv2 报文（UDP 4791）。

**清理**：

```bash
rdma link delete rxe0
modprobe -r rdma_rxe
```

---

## 实验 D：第一次 perftest（两台机器）

假设 `hostA` = 192.168.100.1，`hostB` = 192.168.100.2，都用 `-x 3`（以实际 GID 表为准 —— `ibv_devinfo -v` 或 `minfo.c`）。

### D1. RDMA WRITE 带宽（最常用的测试）

```bash
# hostA（服务端，先起）
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F

# hostB（客户端）
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F 192.168.100.1
```

**期望输出（hostB 侧）**：

```
---------------------------------------------------------------------------------------
                    RDMA_Write BW Test
 Dual-port       : OFF          Device         : mlx5_0
 Number of qps   : 1            Transport type : IB
 Connection type : RC           Using SRQ      : OFF
 PCIe relax order: ON
 ...
 #bytes     #iterations    BW peak[Gb/sec]    BW average[Gb/sec]   MsgRate[Mpps]
 65536      1000             196.42              196.15              0.374
---------------------------------------------------------------------------------------
```

### D2. 时延测试

```bash
# hostA
ib_write_lat -d <ibdev> -i 1 -x <gid_index> -F

# hostB
ib_write_lat -d <ibdev> -i 1 -x <gid_index> -F 192.168.100.1
```

**期望输出**：`t_avg` 在各代硬件上的量级参考

| 硬件代次 | 典型 `t_avg`（RDMA WRITE 时延） |
|---|---|
| ConnectX-4 100G | ~2.5–3.5 μs |
| ConnectX-5 100G | ~1.8–2.5 μs |
| ConnectX-6 200G | ~1.5–2.2 μs |
| ConnectX-7 400G | ~1.3–2.0 μs |
| Soft-RoCE (`rxe`) | ~30–100 μs（正常，不要慌） |

> **【重要】数字不达标时，先确认三件事，再去怀疑硬件**：
> 1. `--report_gbits` 加了吗？（不加看到的是 MB/s，容易被误读）
> 2. MTU 是 1024 还是 4096？（`--mtu=4096` 通常提升明显）
> 3. 是不是只测了**单 QP**？（受 ECMP 哈希限制，见第 2.7 节）

### D3. 双向带宽（更接近真实负载）

```bash
# hostA
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F -b
# hostB
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F -b 192.168.100.1
```

### D4. 多 QP（验证 ECMP 哈希与扩展性）

```bash
# 8 个 QP
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F -q 8
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F -q 8 192.168.100.1
```

**观察点**：`-q 1` 与 `-q 8` 的总带宽对比。若 `-q 8` 明显更高 → 说明之前受 ECMP 单路径限制（第 2.7 节）。

---

## 实验 E：亲眼看到 RoCEv2 报文（本实验的核心）

```bash
# root，在 hostA 上
# 1) 抓 RoCEv2 报文（UDP 4791）
tcpdump -i <netdev> -nn -s 0 -w /tmp/roce.pcap 'udp port 4791' &
TCPDUMP_PID=$!

# 2) 跑一次小规模测试，便于数包
ib_write_bw -d <ibdev> -i 1 -x <gid_index> --report_gbits -F -n 100 -s 8192

# 3) 停止抓包
sleep 1; kill $TCPDUMP_PID

# 4) 文本方式先看一眼
tcpdump -nn -r /tmp/roce.pcap -c 5 -X
```

**用 Wireshark 打开** `roce.pcap`，按下面的清单逐项核对（对照第 2 章）：

| 要看的字段 | 期望值 | 说明 |
|---|---|---|
| UDP 目的端口 | `4791` | RoCEv2 标志 |
| UDP 源端口 | `0xC000–0xFFFF` | 流标签/熵（`IB_ROCE_UDP_ENCAP_VALID_PORT_MIN = 0xC000`） |
| IP Protocol | `17` (UDP) | |
| IP ECN 字段 | `ECT(0)` 或 `Not-ECT`；拥塞时应出现 `CE` | 判断 ECN 是否生效 |
| IP TTL | perftest 的 verbs 路径固定 `0xFF` | 对应 GRH `hop_limit`（`perftest_resources.c:3551`；perftest 的 `--hop_limit` 仅 RawEth 合法） |
| IP DSCP / TOS | `--tclass` 设的值（**注意是 `dscp << 2`**） | 决定 PFC 优先级 |
| **BTH OpCode** | `0x0a` = RDMA WRITE Only | 对照 `ib_pack.h` |
| **BTH Dest QP** | 应等于服务端打印的 `qp_num` | 排连接问题的利器 |
| BTH PSN | 连续递增（每个包 +1） | 验证可靠传输 |
| BTH Flags | `AckReq` 位在需要 ACK 的包上为 1 | |
| RETH VA / rkey / Len | Len 应 ≤ MTU；va 是远端地址 | |
| ICRC | 非零，且改 IP 会导致校验失败 | 不变式 CRC |
| Payload | 数据 | 8KB 消息会被拆成多个包 |
| UDP checksum | 可能是 0 / Wireshark 报 "Illegal" | **正常，别管它**（第 2.4 节） |

> **练习**：数一数 8192 字节的消息在 MTU=1024 下被拆成了几个包？每个包的 OpCode 分别是什么？（提示：FIRST/MIDDLE/LAST）

---

## 实验 F：读一遍你自己的 QP 号与 GID

写一个 20 行的最小程序，把「书上讲的字段」打印出来。这是建立直觉最快的方式。

```c
/* minfo.c —— 编译：gcc minfo.c -o minfo -libverbs */
#include <stdio.h>
#include <infiniband/verbs.h>

int main(void)
{
    struct ibv_device **list = ibv_get_device_list(NULL);
    if (!list) { perror("ibv_get_device_list"); return 1; }

    for (int i = 0; list[i]; i++) {
        struct ibv_context *ctx = ibv_open_device(list[i]);
        if (!ctx) continue;

        struct ibv_device_attr da;
        ibv_query_device(ctx, &da);
        printf("=== %s ===\n", ibv_get_device_name(list[i]));
        printf("  fw_ver=%s  node_guid=%016llx  max_qp=%u max_mr=%u max_cqe=%u\n",
               da.fw_ver,
               (unsigned long long)da.node_guid,
               da.max_qp, da.max_mr, da.max_cqe);

        struct ibv_port_attr pa;
        ibv_query_port(ctx, 1, &pa);
        printf("  port1: state=%d lid=%u link_layer=%s active_mtu=%d max_mtu=%d gid_tbl_len=%d\n",
               pa.state, pa.lid,
               pa.link_layer == IBV_LINK_LAYER_ETHERNET ? "Ethernet" : "InfiniBand",
               pa.active_mtu, pa.max_mtu, pa.gid_tbl_len);

        /* 打印 GID 表 —— 等价于 `ibv_devinfo -v` 的 GID 段（以及 show_gids 若有的话） */
        for (int g = 0; g < pa.gid_tbl_len; g++) {
            union ibv_gid gid;
            if (ibv_query_gid(ctx, 1, g, &gid) == 0) {
                int nonzero = 0;
                for (int k = 0; k < 16; k++) if (gid.raw[k]) { nonzero = 1; break; }
                if (!nonzero) continue;                 /* 全零 GID 跳过 */

                if (gid.raw[10] == 0xff && gid.raw[11] == 0xff) {
                    printf("    gid[%2d] = ::ffff:%u.%u.%u.%u   (IPv4-mapped)\n", g,
                           gid.raw[12], gid.raw[13], gid.raw[14], gid.raw[15]);
                } else {
                    printf("    gid[%2d] = %02x%02x:%02x%02x:...:%02x%02x\n", g,
                           gid.raw[0], gid.raw[1], gid.raw[2], gid.raw[3],
                           gid.raw[14], gid.raw[15]);
                }
            }
        }
        ibv_close_device(ctx);
    }
    ibv_free_device_list(list);
    return 0;
}
```

```bash
gcc minfo.c -o minfo -libverbs && ./minfo
```

**核对**：程序打印的 `gid[N]` 应该与 `ibv_devinfo -v` 的 `GID[  N]`（以及 `show_gids` 若有的话）的 INDEX 一一对应。

> **【进阶】想连 GID 的**类型**（RoCE v1 / RoCE v2）一起打印**，用 `ibv_query_gid_ex()`（`rdma-core:libibverbs/verbs.h:2547`）：
> ```c
> struct ibv_gid_entry entry;
> if (ibv_query_gid_ex(ctx, 1, g, &entry, 0) == 0)
>         printf("    gid[%2d] type=%u ndev_ifindex=%u\n",
>                g, entry.gid_type, entry.ndev_ifindex);
> /* entry.gid_type 是 enum ibv_gid_type（verbs.h:73），
>  * 取值含 IBV_GID_TYPE_IB / _ROCE_V1 / _ROCE_V2 */
> ```
> **注意：`ibv_query_gid_type()` 已从公开头 `verbs.h` 移除**（原型仅在 `rdma-core:libibverbs/driver.h:848`），但库内仍实现并导出（`verbs.c:998`、`libibverbs.map.in:291`），`ibv_devinfo -v` 调用的正是它（`examples/devinfo.c:220`）；应用侧推荐用 `ibv_query_gid_ex()`（`verbs.h:2547`）读 `struct ibv_gid_entry.gid_type`（`struct ibv_gid_entry` 见 `verbs.h:79`，`enum ibv_gid_type` 见 `verbs.h:73`）。

---

## 实验 G：可选 —— 用 pyverbs 做同样的实验（Python）

如果你装了 rdma-core 的 pyverbs（`rdma-core:pyverbs/`，需要 cython）：

```python
# minfo.py —— python3 minfo.py <ibdev>
import sys
from pyverbs.device import Context
from pyverbs.pyverbs_error import PyverbsError

def main(dev_name):
    ctx = Context(name=dev_name)
    try:
        da = ctx.query_device()
        print('fw_ver   :', da.fw_ver)
        print('node_guid:', hex(da.node_guid))
        pa = ctx.query_port(1)
        print(f'link_layer={pa.link_layer} state={pa.state} '
              f'active_mtu={pa.active_mtu} gid_tbl_len={pa.gid_tbl_len}')
        for i in range(pa.gid_tbl_len):
            try:
                gid = ctx.query_gid(1, i)
                if gid is not None and any(gid.raw):
                    print(f'  gid[{i:2d}] = {gid}')
            except PyverbsError:
                continue
    finally:
        ctx.close()

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'rxe0')
```

> **注意**：pyverbs 的 API 名称随版本演进，请以你安装版本的 `pyverbs/device.pyx` 为准。详见第 16.4 节。

---

## 故障速查（本实验最可能遇到的问题）

| 症状 | 最可能原因 | 处理 |
|---|---|---|
| `ibv_devinfo` 无输出 | 驱动未加载 / 无 RDMA 设备 | `lsmod \| grep mlx5`；`dmesg \| tail`；或走 Soft-RoCE 路线 |
| `ibv_devinfo` 有设备但 `PORT_DOWN` | netdev 没 up / 没 IP / 线缆 | `ip link set up`；`ethtool <netdev>` 看链路 |
| perftest 卡在 `Waiting for client` | 防火墙 / TCP 握手端口不通 | 开端口：`ib_write_bw` 默认 TCP 18515（可用 `-p` 改） |
| perftest 报 `Couldn't create QP` / `Failed to modify QP to RTR` | **`-x` GID index 选错** | `ibv_devinfo -v`（或 `show_gids`，若提供）重选，务必选 `RoCE v2` + 业务 IP 行 |
| `Failed to modify QP to RTS` | 两端 MTU 不一致 / `--mtu` 超出 `max_mtu` | 两端统一 `--mtu` |
| 报 `Failed to register MR` | `memlock` 限制（`ulimit -l`） | `ulimit -l unlimited`（或调 `/etc/security/limits.conf`） |
| 带宽极低（< 1 Gb/s） | 走到了 Soft-RoCE；或 MTU 256；或单 QP 受 ECMP 限制 | 确认 `-d` 是真卡；`--mtu=1024/4096`；试 `-q 4` |
| `rxe` 加载失败 | 内核未编译 `CONFIG_RDMA_RXE` | 用发行版内核或自行编译内核模块 |
| 两端报 `mismatch` 后退出 | **两端 perftest 版本或参数不同** | 统一版本；`negotiate_params()` 会逐项比对参数 |

---

## 本实验的「完成标准」

- [ ] 能列出至少一个 RDMA 设备，且 `link_layer` 为 `Ethernet`
- [ ] 能用 `ibv_devinfo -v`（或 `show_gids`，若提供）指出哪个 index 是「RoCEv2 + 业务 IP」
- [ ] 成功跑通 `ib_write_bw` 并得到非零带宽
- [ ] 成功跑通 `ib_write_lat` 并读出 `t_avg`
- [ ] 抓到 RoCEv2 报文，并在 Wireshark 里指出 BTH OpCode、Dest QP、PSN、RETH
- [ ] 能解释你看到的 UDP 源端口为什么落在 `0xC000–0xFFFF`
- [ ] （进阶）用 `minfo.c` 打印出 GID 表并与 `ibv_devinfo -v` 的 `GID[  N]` 对照一致

**下一步**：带着这套可用环境，进入第 4 章 —— 用 verbs 亲手写一个 RDMA 程序。
