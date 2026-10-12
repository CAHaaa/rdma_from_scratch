# 实验 2：verbs 编程实战（对象模型 · 单双边语义 · 故障注入）

> **目标**：把第 4 章的「对象树 + 四条规则」和第 5 章的代码变成**你能亲手验证的事实**。
> 做完这个实验，你将能：① 用 `strace` 指出每个 `ibv_*` 调用在内核里对应什么系统调用；② 用实验证明「单边操作不消耗对端 RECV」；③ 亲手制造 6 种典型错误并记住它们的错误码。
> **前置**：完成 [`lab01-environment-and-first-test.md`](lab01-environment-and-first-test.md)，拥有一个可用的 ibdev（真卡或 `rxe0`）与两台可互通的机器（或单机 loopback）。
> **耗时**：90–150 分钟。
>
> **本实验的定位**：lab01 解决「环境能不能跑」，本实验解决「**你为什么这么写**」。
> 全程只需要两个自写程序（来自第 5 章）+ 一个 20 行的 trace 小程序，不需要任何额外框架。

---

## 实验 A：编译环境检查与 RDMA-CM 客户端/服务端

### A1. 检查头文件与库

```bash
# Debian / Ubuntu
dpkg -l | grep -E 'libibverbs-dev|librdmacm-dev'
# 期望：两个包都是 ii 状态

# 头文件是否在位（这两个是编译期唯一必须的）
ls -l /usr/include/infiniband/verbs.h        # libibverbs-dev 提供
ls -l /usr/include/rdma/rdma_cma.h           # librdmacm-dev 提供

# 库与符号
ldconfig -p | grep -E 'libibverbs\.so|librdmacm\.so'
# 期望：
#   libibverbs.so.1 (libc6,x86-64) => /lib/x86_64-linux-gnu/libibverbs.so.1
#   librdmacm.so.1 (libc6,x86-64) => /lib/x86_64-linux-gnu/librdmacm.so.1

# 开发用的软链接（很重要：-libverbs / -lrdmacm 找的是它）
ls -l /usr/lib/x86_64-linux-gnu/libibverbs.so /usr/lib/x86_64-linux-gnu/librdmacm.so
```

**如果缺包**：

```bash
sudo apt update && sudo apt install -y libibverbs-dev librdmacm-dev build-essential
# RHEL 系：sudo dnf install -y libibverbs-devel librdmacm-devel gcc make
```

**一条命令自检编译链**：

```bash
printf '#include <infiniband/verbs.h>\n#include <rdma/rdma_cma.h>\nint main(void){return 0;}\n' > /tmp/probe.c
gcc /tmp/probe.c -o /tmp/probe -lrdmacm -libverbs && echo "编译链 OK"
```

> **【注意链接顺序】** `-lrdmacm` 必须写在源文件**之后**，且 `-lrdmacm` 要在 `-libverbs` **之前**（`librdmacm` 依赖 `libibverbs`，GNU ld 是单遍解析，顺序反了会报 `undefined reference to ibv_...`）。
> 从本仓源码编译 rdma-core 时（lab01 路线 2），如果 `pkg-config --cflags --libs libibverbs` 有输出，也可以用 `gcc $(pkg-config --cflags libibverbs librdmacm) ... $(pkg-config --libs librdmacm libibverbs)`。

### A2. 抄下第 5 章的代码

本实验**不重复粘贴长代码**。请打开 [`../05-hands-on-code.md`](../05-hands-on-code.md)，把这两段原样抄成两个文件：

| 文件 | 来源 | 行数 |
|---|---|---|
| `cm_server.c` | 第 [5.2.2](../05-hands-on-code.md#522-服务端完整代码约-80-行) 节的完整代码块 | **157 行**（`docs/05-hands-on-code.md:51-209`；该节标题写「约 80 行」，与代码块实际行数不符，**以代码块为准**） |
| `cm_client.c` | 第 [5.2.3](../05-hands-on-code.md#523-客户端完整代码约-70-行) 节的完整代码块 | **155 行**（`docs/05-hands-on-code.md:213-369`；该节标题写「约 70 行」，**以代码块为准**） |

```bash
mkdir -p ~/roce-lab02 && cd ~/roce-lab02
# 用你顺手的方式把代码写进 cm_server.c / cm_client.c（vi / cat <<'EOF' / 编辑器）
```

> **手工抄写的三个雷区**（抄错一定编不过）：
> 1. `#include <rdma/rdma_cma.h>`（**不是** `<infiniband/rdma_cma.h>`）；
> 2. `conn_param.rnr_retry_count = 7;` 与 `conn_param.retry_count = 7;` 是两个不同字段；
> 3. 服务端 `struct sockaddr_in sin` 里的 `sin_port = htons(7471)`，客户端必须用**同一个端口**。

### A3. 精确编译命令

```bash
cd ~/roce-lab02

# 最保守的一行（无优化、全警告）
gcc -O0 -g -Wall -Wextra cm_server.c -o cm_server -lrdmacm -libverbs
gcc -O0 -g -Wall -Wextra cm_client.c -o cm_client -lrdmacm -libverbs

# 生产/性能向（-O2，去掉 -Wextra 以免噪声过多）
gcc -O2 -Wall cm_server.c -o cm_server_O2 -lrdmacm -libverbs
gcc -O2 -Wall cm_client.c -o cm_client_O2 -lrdmacm -libverbs

# 看链接到了什么
ldd ./cm_server
# 期望包含：librdmacm.so.1 => ... / libibverbs.so.1 => ... / libc.so.6
```

> `-g` 很关键：实验 B 要 `strace`，实验 F 要 `gdb`，没有调试符号就只能看地址。

### A4. 运行（两台机器）

假设 `hostA` = 192.168.100.1（服务端），`hostB` = 192.168.100.2（客户端）。

```bash
# ---------- hostA ----------
cd ~/roce-lab02
./cm_server
# 期望：
#   [server] listening on port 7471 ...
#   [server] connected. local QPN=0xXXXXXX, GID index used=-1
#   [server] received 31 bytes: Hello from client over RoCEv2!
#   [server] sent reply.

# ---------- hostB ----------
cd ~/roce-lab02
./cm_client 192.168.100.1
# 期望：
#   [client] address resolved. Using device mlx5_0
#   [client] route resolved.
#   [client] connected. local QPN=0xXXXXXX
#   [client] send completed (32 bytes sent).
#   [client] received reply (32 bytes): Hello from server over RoCEv2!
```

> **注意端口**：这里用的 **7471** 是**第 5 章示例代码自己选的监听端口**（`docs/05-hands-on-code.md:96` 的 `htons(7471)`），**不是** RDMA-CM 或 IANA 保留给 RDMA 的端口；它与 perftest 的 TCP 握手端口 18515 **完全无关**。防火墙要单独放通 7471/TCP。
> **内核模块**：只有**使用** RDMA-CM（链接 `librdmacm`）时才需要内核 `rdma_ucm` 模块提供 `/dev/infiniband/rdma_cm`（`kernel:drivers/infiniband/core/ucma.c:1948-1951`）；**纯 verbs 程序不需要**。

### A5. 单机验证（没有第二台机器时）

```bash
# 终端 1
cd ~/roce-lab02 && ./cm_server
# 终端 2 —— 连自己
./cm_client 127.0.0.1
# 或者连本机业务 IP：
./cm_client 192.168.100.1
```

**单机能不能跑通**取决于 CM 能否把 `127.0.0.1` 解析成一个可用的 RoCE 路径。经验规律：

| 设备 | 连 `127.0.0.1` | 连本机业务 IP | 说明 |
|---|---|---|---|
| `rxe0` | 通常可以 | 可以 | rxe 走内核 UDP 栈，loopback 是合法路径 |
| 真卡（mlx5） | **常常失败** | 通常可以 | loopback 地址不会生成 RoCE-usable GID（无 link-local 匹配） |

> **如果单机失败**：不要怀疑代码。改成两台机器，或者退一步用 **`rxe0` + 业务 IP** 验证功能正确性（`rxe` 性能低但协议路径是真的）。

### A6. 顺手抓一次包，确认它真的是 RoCEv2

```bash
# root，在 hostA 上
tcpdump -i <netdev> -nn -s 0 -c 6 -X 'udp port 4791'
```

**核对点**（对照第 2 章）：

| 项 | 期望 |
|---|---|
| UDP 目的端口 | `4791` |
| UDP 源端口 | `0xC000–0xFFFF` |
| BTH OpCode | `0x04`（RC SEND_ONLY）或 `0x05`（带 IMM） |
| BTH Dest QP | 等于服务端打印的 `local QPN`（**这是最好用的连接排障手段**） |
| UDP checksum | `0x0000` —— **正常，Wireshark 报 "Illegal" 别管它** |

---

## 实验 B：把对象模型「钉」到系统调用上（strace 追踪）

第 4 章说 verbs 是「一棵对象树」。**这一节要让你亲眼看到：树上每个节点对应一次系统调用。**

### B1. 先理解要抓什么

核心事实（先记住，再用实验验证）：

| verbs 动作 | 用户态做什么 | 内核入口 |
|---|---|---|
| `ibv_get_device_list` | 扫 `/sys/class/infiniband/` | 只有 `openat`/`getdents`，**不进 uverbs** |
| `ibv_open_device` | 打开字符设备 | **`openat("/dev/infiniband/uverbsN")`** |
| `ibv_alloc_pd` / `ibv_reg_mr` / `ibv_create_cq` / `ibv_create_qp` / `ibv_modify_qp` | 组命令缓冲区 | **`write(fd, cmd, len)`**（传统 ABI）或 **`ioctl(fd, RDMA_VERBS_IOCTL, ...)`**（新式 ioctl ABI） |
| `ibv_post_send` / `ibv_poll_cq` | **纯用户态**：写 mmap 出来的 SQ 缓冲 + 敲门铃 | **没有系统调用** |
| `ibv_create_cq`（带 `comp_channel`） | 取事件 fd | 额外 `mmap` + `poll` |

**两代 ABI 的判别方法**（这是本节的核心技能）：

| 现象 | 含义 |
|---|---|
| `write(N, "\x03\x00\x00\x00...", 56)` | **传统 write 命令**：**前 4 字节**是 `IB_USER_VERBS_CMD_*` 命令号 |
| `ioctl(N, RDMA_VERBS_IOCTL, ...)` | **新式 ioctl**：载荷是 `struct ib_uverbs_ioctl_hdr { object_id, method_id, num_attrs, ... }` |
| `openat("/dev/infiniband/uverbsN")` | `ibv_open_device` |

> **【重要澄清】** 本内核里**没有 `UVERBS_IOCTL_VERSION` 这个常量**。新式 ioctl 的兼容机制是三条头部校验：`hdr.reserved1`/`hdr.reserved2` 必须为 0（否则 `-EPROTONOSUPPORT`），`hdr.driver_id` 必须等于 `uapi->driver_id`（否则 `-EINVAL`）。详见 [`../reference/repo-map.md`](../reference/repo-map.md) 第 2.4 节。
> 判断一个具体调用走哪条路，**最可靠的办法是看命令大小与第二次 write/ioctl 的内容**，而不是背版本号。

### B2. 写一个「只建对象、不传数据」的 trace 程序

我们要把 6 个动作**串成一条命令**，这样 `strace` 输出里每一步都看得见。

```c
/* trace_obj.c —— 编译：gcc -O0 -g trace_obj.c -o trace_obj -libverbs
 * 用法：./trace_obj <ibdev> [gid_index]
 * 只做控制平面：open_device → alloc_pd → reg_mr → create_cq → create_qp → modify_qp(RESET→INIT→RTR→RTS)
 * 不做任何 post_send / post_recv（那部分是纯用户态，strace 看不到，正好用来对照）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <infiniband/verbs.h>

#define BUF_SIZE (1 << 20)

static void die(const char *m) { fprintf(stderr, "%-28s: %s\n", m, strerror(errno)); exit(1); }

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: %s <ibdev> [gid_index]\n", argv[0]); return 1; }
    const char *want = argv[1];
    int gid_index = (argc > 2) ? atoi(argv[2]) : 0;

    /* ---------- ① ibv_get_device_list：找设备（只读 sysfs） ---------- */
    struct ibv_device **list = ibv_get_device_list(NULL);
    if (!list) die("ibv_get_device_list");
    struct ibv_device *dev = NULL;
    for (int i = 0; list[i]; i++)
        if (!strcmp(ibv_get_device_name(list[i]), want)) dev = list[i];
    if (!dev) { fprintf(stderr, "device %s not found\n", want); return 1; }

    /* ---------- ② ibv_open_device：open /dev/infiniband/uverbsN ---------- */
    struct ibv_context *ctx = ibv_open_device(dev);
    if (!ctx) die("ibv_open_device");
    ibv_free_device_list(list);
    printf("opened %s\n", want);

    /* ---------- ③ ibv_alloc_pd ---------- */
    struct ibv_pd *pd = ibv_alloc_pd(ctx);
    if (!pd) die("ibv_alloc_pd");
    printf("pd handle = 0x%08x\n", pd->handle);

    /* ---------- ④ ibv_reg_mr：pin 内存并建 MPT ---------- */
    char *buf = NULL;
    if (posix_memalign((void **)&buf, 4096, BUF_SIZE)) die("posix_memalign");
    struct ibv_mr *mr = ibv_reg_mr(pd, buf, BUF_SIZE,
                                   IBV_ACCESS_LOCAL_WRITE  |
                                   IBV_ACCESS_REMOTE_WRITE |
                                   IBV_ACCESS_REMOTE_READ);
    if (!mr) die("ibv_reg_mr (check ulimit -l)");
    printf("mr lkey=0x%08x rkey=0x%08x\n", mr->lkey, mr->rkey);

    /* ---------- ⑤ ibv_create_cq ---------- */
    struct ibv_cq *cq = ibv_create_cq(ctx, 64, NULL, NULL, 0);
    if (!cq) die("ibv_create_cq");
    printf("cq handle = 0x%08x cqe=%d\n", cq->handle, cq->cqe);

    /* ---------- ⑥ ibv_create_qp ---------- */
    struct ibv_qp_init_attr qia = {
        .send_cq = cq, .recv_cq = cq,
        .cap = { .max_send_wr = 64, .max_recv_wr = 64,
                 .max_send_sge = 1, .max_recv_sge = 1, .max_inline_data = 64 },
        .qp_type = IBV_QPT_RC,
        .sq_sig_all = 0,
    };
    struct ibv_qp *qp = ibv_create_qp(pd, &qia);
    if (!qp) die("ibv_create_qp");
    printf("qp_num = 0x%06x\n", qp->qp_num);

    /* ---------- ⑦ 三次 ibv_modify_qp：三次独立 write/ioctl ---------- */
    {   /* RESET → INIT */
        struct ibv_qp_attr a = {
            .qp_state = IBV_QPS_INIT, .pkey_index = 0, .port_num = 1,
            .qp_access_flags = IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE |
                               IBV_ACCESS_REMOTE_READ  | IBV_ACCESS_REMOTE_ATOMIC,
        };
        if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_PKEY_INDEX |
                                  IBV_QP_PORT  | IBV_QP_ACCESS_FLAGS))
            die("modify_qp RESET->INIT");
        printf("--> INIT  done\n");
    }
    {   /* INIT → RTR（本实验不发数据，dgid 填本机 GID 即可） */
        union ibv_gid g; if (ibv_query_gid(ctx, 1, gid_index, &g)) die("ibv_query_gid");
        struct ibv_qp_attr a = {
            .qp_state = IBV_QPS_RTR, .path_mtu = IBV_MTU_1024,
            .dest_qp_num = qp->qp_num,          /* 自己连自己，仅为了走通状态机 */
            .rq_psn = 0, .max_dest_rd_atomic = 1, .min_rnr_timer = 12,
            .ah_attr = { .is_global = 1, .port_num = 1,
                         .grh = { .dgid = g, .sgid_index = (uint8_t)gid_index,
                                  .hop_limit = 64, .traffic_class = 0, .flow_label = 0 } },
        };
        if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_AV | IBV_QP_PATH_MTU |
                                  IBV_QP_DEST_QPN | IBV_QP_RQ_PSN |
                                  IBV_QP_MAX_DEST_RD_ATOMIC | IBV_QP_MIN_RNR_TIMER))
            die("modify_qp INIT->RTR");
        printf("--> RTR   done\n");
    }
    {   /* RTR → RTS */
        struct ibv_qp_attr a = {
            .qp_state = IBV_QPS_RTS, .timeout = 14, .retry_cnt = 7, .rnr_retry = 7,
            .sq_psn = 0, .max_rd_atomic = 1,
        };
        if (ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_TIMEOUT | IBV_QP_RETRY_CNT |
                                  IBV_QP_RNR_RETRY | IBV_QP_SQ_PSN | IBV_QP_MAX_QP_RD_ATOMIC))
            die("modify_qp RTR->RTS");
        printf("--> RTS   done\n");
    }

    /* 数据路径（post_send/poll_cq）不在这里做：它们是纯用户态，strace 看不到 —— 这本身就是结论 */

    ibv_destroy_qp(qp); ibv_destroy_cq(cq); ibv_dereg_mr(mr);
    free(buf); ibv_dealloc_pd(pd); ibv_close_device(ctx);
    printf("all destroyed\n");
    return 0;
}
```

```bash
gcc -O0 -g trace_obj.c -o trace_obj -libverbs
./trace_obj mlx5_0 3        # rxe 用户改成 ./trace_obj rxe0 0
```

**先确认它能跑通**（期望输出）：

```text
opened mlx5_0
pd handle = 0xXXXXXXXX
mr lkey=0xXXXXXXXX rkey=0xXXXXXXXX
cq handle = 0xXXXXXXXX cqe=64
qp_num = 0xXXXXXX
--> INIT  done
--> RTR   done
--> RTS   done
all destroyed
```

> **【注意】上面的句柄与 key 用 `0xXXXXXXXX` 占位，不是真实值。**
> 这些值每次运行都不同（`rkey` 由 `ibv_reg_mr` 现场生成，且**离开那台机器立即失效**，因为它只在网卡 MPT 里有意义）。
> **你运行时会看到具体数值，但不要把真实 `rkey` 贴进 issue、日志或文档** —— 这正是第 14 章第 14.2.2 节的第 1 条规则。

### B3. 抓系统调用

```bash
# 关键：-f 跟线程（libibverbs 可能起线程），-e 只留我们关心的四类
strace -f -e trace=write,ioctl,mmap,openat -o /tmp/trace_obj.log ./trace_obj mlx5_0 3

# 只看 uverbs 相关的行（把噪声过滤掉）
grep -nE 'infiniband|RDMA_VERBS_IOCTL' /tmp/trace_obj.log
```

### B4. 期望的 strace 输出「形状」（**示意**，数值因设备/版本而异）

> **【务必看清】下面标注「示意」的片段是用来说明行文结构与字段含义的，不是某台机器的原样拷贝。**
> 你的实际输出里长度、命令号、地址一定不同 —— **要看的是"哪一类调用出现在哪个阶段"**。

```text
# ── 阶段 ⓪：设备发现（纯 sysfs，不进 uverbs）──────────────────────────
openat(AT_FDCWD, "/sys/class/infiniband", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 3
openat(AT_FDCWD, "/sys/class/infiniband/mlx5_0", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 4
openat(AT_FDCWD, "/sys/class/infiniband/mlx5_0/ibdev", O_RDONLY|O_CLOEXEC) = 5
    ↑ ibv_get_device_list 只是读 sysfs；此时还没有任何 uverbs 节点被打开

# ── 阶段 ①：ibv_open_device → openat uverbs 节点 ──────────────────────
openat(AT_FDCWD, "/dev/infiniband/uverbs0", O_RDWR|O_CLOEXEC) = 6
    ↑ 这一步之后，所有控制平面命令都发到 fd=6

# ── 阶段 ②：ibv_alloc_pd ─────────────────────────────────────────────
write(6, "\x03\x00\x00\x00\x00\x00\x00\x00\xa2\x01\x00\x00", 12) = 12      [示意]
    ↑ 传统 ABI：write 的第 1 个 4 字节字是命令号；长度就是该命令的 ABI 结构体大小
    ↑ 新式库在这里会变成：ioctl(6, RDMA_VERBS_IOCTL, {object_id=UVERBS_OBJECT_PD, method_id=UVERBS_METHOD_PD_ALLOC, num_attrs=1, ...})

# ── 阶段 ③：ibv_reg_mr（这里一定伴随 mmap，因为要建 doorbell/缓冲映射）──
write(6, "...", 48) = 48                                                    [示意]
    ↑ 命令体里带 addr / length / access flags；内核在 umem.c 里 pin 页
mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_SHARED, 6, 0x... /*offset 由驱动定义*/) = 0x7f...
    ↑ ★ 关键：这个 mmap 把内核/硬件资源映射进用户态，是后面"post_send 不需要系统调用"的前提

# ── 阶段 ④：ibv_create_cq ────────────────────────────────────────────
write(6, "...", 40) = 40                                                    [示意]
mmap(NULL, 8192, PROT_READ|PROT_WRITE, MAP_SHARED, 6, 0x... ) = 0x7f...
    ↑ CQ 缓冲被 mmap 进用户态 —— 所以 ibv_poll_cq 是纯内存读，没有系统调用

# ── 阶段 ⑤：ibv_create_qp ────────────────────────────────────────────
write(6, "...", 96) = 96                                                    [示意]
mmap(NULL, 65536, PROT_READ|PROT_WRITE, MAP_SHARED, 6, 0x... ) = 0x7f...
    ↑ SQ/RQ 缓冲 + doorbell record

# ── 阶段 ⑥：三次 ibv_modify_qp = 三次独立的 write ─────────────────────
write(6, "...", 88) = 88        ← RESET → INIT                              [示意]
write(6, "...", 152) = 152      ← INIT  → RTR（带 ABI 里的 AH/GRH 字段）      [示意]
write(6, "...", 56) = 56        ← RTR   → RTS                              [示意]
    ↑ ★ 记住这条：**modify_qp 不是一次调用**，是每迁移一次状态一次系统调用
    ↑ 长度差异本身就说明"RTR 携带的信息最多"（要 dgid/sgid_index/MTU/dest_qpn/PSN...）

# ── 阶段 ⑦：销毁 ─────────────────────────────────────────────────────
write(6, "...", 8) = 8          ← destroy_qp                               [示意]
write(6, "...", 8) = 8          ← destroy_cq                               [示意]
write(6, "...", 8) = 8          ← dereg_mr                                 [示意]
write(6, "...", 8) = 8          ← dealloc_pd                               [示意]
close(6) = 0                    ← ibv_close_device
```

### B5. 逐项对照表：你要在日志里「找到」的 7 件事

| # | 要找到的东西 | 在 strace 里长什么样 | 对应第 4 章哪个对象 |
|---|---|---|---|
| 1 | **uverbs 节点被打开** | `openat(..., "/dev/infiniband/uverbsN", O_RDWR...) = <fd>` | `ibv_context` |
| 2 | `ibv_open_device` **之前**只有 sysfs 读 | 无 `uverbs` 字样的 `openat` | `ibv_device` |
| 3 | PD / MR / CQ / QP 各一次 write（或 ioctl） | 4 条长度不同的 `write(6, ...)` | `ibv_pd` / `ibv_mr` / `ibv_cq` / `ibv_qp` |
| 4 | **`mmap` 是「用户态快路径」的物理基础** | 至少 2–4 条 `mmap(..., fd=6, ...)` | CQ/SQ/RQ/doorbell |
| 5 | **3 次 `ibv_modify_qp` = 3 次系统调用** | 3 条连续 `write`，长度递增后回落 | QP 状态机 |
| 6 | `ibv_post_send` / `ibv_poll_cq` **完全不出现** | 日志里找不到 | —— （这就是结论） |
| 7 | 销毁是逆序的 | destroy_qp → destroy_cq → dereg_mr → dealloc_pd → close | 第 4.4.3 节 |

### B6. 把「数据路径不进内核」这件事钉死

```bash
# 把 post_send 循环塞进 strace 里，看它到底产生了多少系统调用
strace -f -c -e trace=all ./your_send_recv_program   # -c 只打印统计摘要
```

期望看到的形状（示意）：

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 60.00    0.001200           1      1200           write      ← ★ 只有 1200 次 = 建连/销毁的 write，
                                                              和"发了 100 万个包"完全不成比例
 30.00    0.000600           0       600           mmap
 ...
```

> **判读**：如果一个跑了 100 万次 `ibv_post_send` 的程序里 `write` 只有几十/几百次，说明**数据路径确实没有系统调用** —— 这正是 [`../reference/repo-map.md`](../reference/repo-map.md) 第 1 节那张图里「数据平面几乎不经过内核」的实证。

### B7. 如果你想看「内核收到了什么命令号」

```bash
# 用 -x 打印十六进制，再手算第 1 个 4 字节字
strace -f -x -e trace=write -o /tmp/w.log ./trace_obj mlx5_0 3
head -3 /tmp/w.log
# 例：write(6, "\x03\x00\x00\x00\xa2\x01\x00\x00...", 12) = 12
#              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#              前 4 字节小端 = 0x00000003 → 传统 ABI 里的一个 IB_USER_VERBS_CMD_* 命令号
```

命令号常量在 `kernel:include/uapi/rdma/ib_user_verbs.h` 的 `IB_USER_VERBS_CMD_*` 枚举里。**不要背数字** —— 内核是向后兼容演进的，数字会随版本增删；用「调用出现在哪个阶段 + 命令长度」来对应关系更可靠。

---

## 实验 C：证明「单边 vs 双边」的语义差异

**这是本实验最有价值的一节。** 第 4.3.6 节那张表（opcode × 是否需要对端 RECV）是**可以实验证明**的。

### C0. 三个实验的共同脚手架

把第 5.2 节的 `cm_client.c` / `cm_server.c` 复制成三份，每份只改「发送侧 post 什么 opcode」和「接收侧 post 不 post RECV」。

```bash
cd ~/roce-lab02
cp cm_client.c c1_client.c ; cp cm_server.c c1_server.c   # WRITE，对端不 post_recv
cp cm_client.c c2_client.c ; cp cm_server.c c2_server.c   # SEND， 对端不 post_recv
cp cm_client.c c3_client.c ; cp cm_server.c c3_server.c   # WRITE_WITH_IMM
```

**为了看清结果，请给每个程序加一行完成事件打印**（发送侧）：

```c
static void drain_cq(struct ibv_cq *cq, const char *tag)
{
    struct ibv_wc wc;
    int n = ibv_poll_cq(cq, 1, &wc);
    if (n == 0) { printf("[%s] no completion yet\n", tag); return; }
    printf("[%s] opcode=%d status=%d(%s) wr_id=%llu byte_len=%u flags=0x%x\n",
           tag, wc.opcode, wc.status, ibv_wc_status_str(wc.status),
           (unsigned long long)wc.wr_id, wc.byte_len, wc.wc_flags);
}
```

**轮询要有超时**，否则会因为「永远等不到 CQE」而挂死：

```c
/* 最多轮询约 5 秒；用 clock_gettime(CLOCK_MONOTONIC) 计时 */
static int poll_with_timeout(struct ibv_cq *cq, struct ibv_wc *wc, int seconds)
{
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (;;) {
        int n = ibv_poll_cq(cq, 1, wc);
        if (n > 0) return n;
        clock_gettime(CLOCK_MONOTONIC, &t1);
        if ((t1.tv_sec - t0.tv_sec) >= seconds) return 0;   /* 超时 */
    }
}
```

### C1. 实验一：`IBV_WR_RDMA_WRITE`，对端 **不** post 任何 RECV

**发送侧（c1_client.c）改成：**

```c
/* 握手阶段额外交换对端的 rkey 与 buffer 地址（用 conn_param.private_data 传，或临时硬编码） */
struct ibv_sge sge = { .addr = (uintptr_t)buf, .length = 64, .lkey = mr->lkey };
struct ibv_send_wr wr = {
    .wr_id = 101, .sg_list = &sge, .num_sge = 1,
    .opcode = IBV_WR_RDMA_WRITE,
    .send_flags = IBV_SEND_SIGNALED,
    .wr.rdma = { .remote_addr = peer_vaddr, .rkey = peer_rkey },
};
struct ibv_send_wr *bad;
if (ibv_post_send(id->qp, &wr, &bad)) die("post_send RDMA_WRITE");
```

**接收侧（c1_server.c）：把 `ibv_post_recv()` 那一段整个删掉**（或注释掉），只保留连接与服务端循环。

| 观察项 | 期望结果 |
|---|---|
| 发送侧 CQE | **`IBV_WC_SUCCESS`**，`opcode = IBV_WC_RDMA_WRITE` |
| 接收侧 CQE | **没有任何完成事件**（对端 RQ 深度可以是 0 都不影响） |
| 接收侧缓冲内容 | 数据**确实写进来了**（打印 `buf[0..63]` 能看到客户端写的内容） |
| 接收侧 QP 状态 | 仍然是 `RTS`，没有任何错误事件 |

**打印接收缓冲验证（服务端）：**

```c
printf("[server] no recv posted. buf[0..15] = ");
for (int i = 0; i < 16; i++) printf("%02x ", (unsigned char)buf[i]);
printf("\n");
/* 期望：正是客户端 sge.addr 处的 16 字节 —— 证明数据落进来了，而 CPU 完全没参与 */
```

> **【本实验的结论】** RDMA WRITE 是**单边**操作：**对端不需要投递 RECV、不需要运行任何代码、CPU 零感知**。
> 这正是第 4.3.6 节表格里 `IBV_WR_RDMA_WRITE` 那一行的「对端需要 RECV：✗」。

### C2. 实验二：`IBV_WR_SEND`，对端 **不** post RECV → 必须失败

**发送侧（c2_client.c）：**

```c
struct ibv_send_wr wr = {
    .wr_id = 201, .sg_list = &sge, .num_sge = 1,
    .opcode = IBV_WR_SEND,
    .send_flags = IBV_SEND_SIGNALED,
};
if (ibv_post_send(id->qp, &wr, &bad)) die("post_send SEND");
```

**接收侧（c2_server.c）：同样把 `ibv_post_recv()` 删掉。**

但要**控制失败速度快慢** —— 这取决于 `rnr_retry`：

| 接收侧 `rnr_retry` | 现象 | 耗时 |
|---|---|---|
| `7`（**默认推荐值，特殊含义 = 无限重试**） | 发送侧**一直等不到 CQE**，接收侧一直不发 RNR 终止信号 | **永不返回**（必须靠你的超时兜底） |
| `0`（不重试） | 发送侧**立刻**拿到 `IBV_WC_RNR_RETRY_EXC_ERR` | 毫秒级 |
| `1`–`6` | 重试 N 次后拿到 `IBV_WC_RNR_RETRY_EXC_ERR` | 秒级 |

**要做这个实验，请把发送侧改成 `rnr_retry = 0`：**

```c
struct ibv_qp_attr a = {
    .qp_state = IBV_QPS_RTS, .timeout = 14, .retry_cnt = 7,
    .rnr_retry = 0,          /* ★ 为了快速看到失败，实验里设 0；生产里设 7 */
    .sq_psn = 0, .max_rd_atomic = 1,
};
```

| 观察项 | 期望结果 |
|---|---|
| 发送侧 CQE | **`IBV_WC_RNR_RETRY_EXC_ERR`**（`ibv_wc_status_str()` 打印为 `RNR retry exceeded`） |
| 发送侧 opcode | `IBV_WC_SEND` |
| 接收侧 | 无 CQE（它根本没收到东西） |
| 线上报文 | 对端回的是 **RNR NAK**（AETH syndrome `0x20`，见第 2.3 节） |

**在第三个终端抓包佐证（可选但极有说服力）：**

```bash
sudo tcpdump -i <netdev> -nn -c 20 -X 'udp port 4791'
# 找到 opcode = 0x11 (RC ACKNOWLEDGE) 的包，看 AETH 第一个字节：
#   0x20 → RNR NAK
#   0x00 → 正常 ACK
```

> **【本实验的结论】** SEND 是**双边**操作：**对端没有 RECV 信用就会 NAK**。
> `rnr_retry = 7` 是「无限重试」这个特殊语义（第 4.3.5 节），所以**默认配置下不会报错，而是卡住** —— 生产代码必须自己设超时，否则表现为「程序无声卡死」。

### C3. 实验三：`IBV_WR_RDMA_WRITE_WITH_IMM`，对端收到完成并**消耗一个 RECV WR**

这是前两个实验的「合题」：**数据是单边写进去的，但完成事件是双边产生的。**

**发送侧（c3_client.c）：**

```c
wr.opcode    = IBV_WR_RDMA_WRITE_WITH_IMM;
wr.imm_data  = htonl(0x1234);          /* ★ 网络字节序！ */
/* wr.rdma 与 sge 同实验一 */
```

**接收侧（c3_server.c）：恢复 `ibv_post_recv()`，但只投 `1` 个 WR（RQ 深度 1）**，并把 CQE 打印出来：

```c
/* 只投一个 RECV，这样才能看出"消耗一个" */
struct ibv_sge rsge = { .addr = (uintptr_t)buf, .length = BUF_SIZE, .lkey = mr->lkey };
struct ibv_recv_wr rr = { .wr_id = 9001, .sg_list = &rsge, .num_sge = 1 };
struct ibv_recv_wr *bad;
if (ibv_post_recv(conn_id->qp, &rr, &bad)) die("post_recv");
printf("[server] posted exactly 1 RECV WR\n");
```

**接收侧轮询时把关键字段打全：**

```c
struct ibv_wc wc;
if (poll_with_timeout(cq, &wc, 5) > 0) {
    printf("[server] RECV CQE: opcode=%d(%s) status=%s byte_len=%u flags=0x%x imm=0x%08x\n",
           wc.opcode,
           (wc.opcode & IBV_WC_RECV) ? "RECV-family" : "SEND-family",
           ibv_wc_status_str(wc.status),
           wc.byte_len, wc.wc_flags, wc.imm_data);
}
```

| 观察项 | 期望结果 |
|---|---|
| 接收侧 CQE 的 `opcode` | **`IBV_WC_RECV_RDMA_WITH_IMM`**（值 = `IBV_WC_RECV(1<<7) + 1` = `0x81`） |
| 接收侧 `wc_flags` | **包含 `IBV_WC_WITH_IMM`** |
| 接收侧 `imm_data` | `0x1234` —— **注意读之前要 `ntohl()`** |
| 接收侧的 `wc.byte_len` | **通常是 0** —— 因为 WRITE 的数据**不落在 RECV 缓冲里**，只落在 `remote_addr` 指向的位置。RECV WR 在这里只是"通知载体" |
| 再投一次 `WRITE_WITH_IMM`（对端**不补投** RECV） | 接收侧第二次收不到完成；发送侧（`rnr_retry=0`）拿 `RNR_RETRY_EXC_ERR` |

> **【必须记住的三条结论】**（第 4.3.6 / 5.4.2 节）
> 1. `IBV_WR_RDMA_WRITE`：**对端零感知**，不消耗 RECV WR，不产生对端 CQE；
> 2. `IBV_WR_RDMA_WRITE_WITH_IMM`：数据仍然是单边写入 `remote_addr`，**但会消耗对端一个 RECV WR 并产生一个接收 CQE**；
> 3. 所以 **「用 WRITE 不消耗 RECV」这条经验只对纯 WRITE 成立**。用 `WRITE_WITH_IMM` 就必须像 SEND 一样准备并补充 RECV 信用 —— 否则对端会被 RNR。

### C4. 三合一对照表（把结论抄进笔记）

| 实验 | opcode | 对端 post RECV | 本端 CQE | 对端 CQE | 数据落在哪 | 典型 WC 错误 |
|---|---|---|---|---|---|---|
| C1 | `IBV_WR_RDMA_WRITE` | **不需要** | `IBV_WC_RDMA_WRITE` | **无** | 对端 `remote_addr` | 仅 rkey/权限错 → `REM_ACCESS_ERR` |
| C2 | `IBV_WR_SEND` | **必须** | `IBV_WC_SEND` | `IBV_WC_RECV` | 对端 RECV 缓冲 | `RNR_RETRY_EXC_ERR` |
| C3 | `IBV_WR_RDMA_WRITE_WITH_IMM` | **必须**（消耗 1 个） | `IBV_WC_RDMA_WRITE` | `IBV_WC_RECV_RDMA_WITH_IMM` | 对端 `remote_addr`（**不是** RECV 缓冲） | `RNR_RETRY_EXC_ERR` |

---

## 实验 D：故意搞坏它 —— 6 个故障注入练习

**这一节的目标不是"跑通"，而是"跑挂并认出错误码"。**

> **纪律**：每次只注入**一个**错误，记录现象后再恢复。跑之前先把正确的程序保存一份：
> ```bash
> cp -r ~/roce-lab02 ~/roce-lab02.good
> ```

### D0. 先准备一个「能稳定跑通」的基线

用实验 A 的 `cm_client` / `cm_server`，确认一次成功，记下：

```text
基线：client qpn=0x______  server qpn=0x______  rkey(peer)=0x________  vaddr(peer)=0x____________
```

### D1. 注入错误 1：`lkey` 填错（跨 PD / 废弃 / 随便编）

```c
/* 正确：.lkey = mr->lkey */
/* 注入： */
struct ibv_sge sge = { .addr = (uintptr_t)buf, .length = 64,
                       .lkey = mr->lkey ^ 0x00000007 };   /* 改掉低位 */
```

| 项 | 期望 |
|---|---|
| `ibv_post_send` 返回值 | **0（成功入队）** —— 用户态**不校验** lkey |
| CQE `status` | **`IBV_WC_LOC_PROT_ERR`**（= 4） |
| `ibv_wc_status_str()` | `Local protection error` |
| QP 后续 | 进 `ERROR` 态，SQ 中后续 WR 报 `IBV_WC_WR_FLUSH_ERR` |

**等价更强的注入方式（跨 PD，安全性实验的核心）**：

```c
struct ibv_pd *pd_other = ibv_alloc_pd(ctx);
struct ibv_mr *mr_other = ibv_reg_mr(pd_other, buf, BUF_SIZE, IBV_ACCESS_LOCAL_WRITE);
/* 用 mr_other->lkey 去喂属于 pd 的 QP → LOC_PROT_ERR */
```

> **原理（软件实现可读到源码）**：`kernel:drivers/infiniband/sw/rxe/rxe_mr.c:713-716` 的 `lookup_mr()` 检查**五项**，任一不满足就先 `rxe_put(mr)` 再把 `mr` 置 `NULL` 返回：
> ① **键匹配（按查找类型分两种）**：`type == RXE_LOOKUP_LOCAL` 时要求 `mr->lkey == key`；`type == RXE_LOOKUP_REMOTE` 时要求 `mr->rkey == key`；
> ② `mr_pd(mr) != pd` —— PD 不匹配；
> ③ `(access & mr->access) != access` —— 请求的权限不是 MR 授权权限的子集；
> ④ `mr->state != RXE_MR_STATE_VALID` —— MR 未处于有效状态。
> 这五种不满足最终由 `rxe_req.c:810-811`（`finish_packet()` 返回 `-EFAULT`）置 `IB_WC_LOC_PROT_ERR`。
> 真卡上这一步是**网卡的 MPT 查表**，但语义完全一样。

### D2. 注入错误 2：`rkey` 填错（远端键错）

```c
wr.wr.rdma.rkey = peer_rkey ^ 0x00000010;   /* 改掉 rkey 的低位 */
```

| 项 | 期望 |
|---|---|
| 本端 CQE `status` | **`IBV_WC_REM_ACCESS_ERR`**（= 10） |
| 对端 | 回 **NAK REM_ACC_ERR**（AETH syndrome `0x62`） |
| QP 后续 | 进 `ERROR`，后续 `WR_FLUSH_ERR` |
| 软件实现源码 | `kernel:drivers/infiniband/sw/rxe/rxe_resp.c:1692` 置 `IB_WC_REM_ACCESS_ERR` |

**抓包佐证 AETH**：

```bash
sudo tcpdump -i <netdev> -nn -X 'udp port 4791' | grep -A2 '0x11'   # RC ACKNOWLEDGE
# 找 AETH 字节：0x62 = NAK REM_ACC_ERR
```

### D3. 注入错误 3：接收缓冲**漏了** `IBV_ACCESS_LOCAL_WRITE`

这是最隐蔽的一个：**发送侧完全正常，问题出在接收侧的内存权限上。**

```c
/* 正确 */
mr = ibv_reg_mr(pd, buf, BUF_SIZE, IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE);
/* 注入：只给 REMOTE_WRITE，漏掉 LOCAL_WRITE —— 注意内核会先拦住它，见下 */
mr = ibv_reg_mr(pd, buf, BUF_SIZE, IBV_ACCESS_REMOTE_WRITE);
```

**先撞上的是内核的强制规则**（`kernel:include/rdma/ib_verbs.h:4645-4647`）：

```c
if (flags & (IB_ACCESS_REMOTE_ATOMIC | IB_ACCESS_REMOTE_WRITE) &&
    !(flags & IB_ACCESS_LOCAL_WRITE))
        return -EINVAL;
```

| 注入写法 | 期望 |
|---|---|
| `REMOTE_WRITE` 单独给（不带 `LOCAL_WRITE`） | **`ibv_reg_mr` 返回 NULL，`errno = EINVAL`** —— 内核直接拒绝，注册不成功 |
| 真的「只给最小权限」的接收缓冲：`ibv_reg_mr(pd, buf, len, 0)` | `ibv_reg_mr` **成功**；但用它当 RECV 缓冲时 → CQE `status = IBV_WC_LOC_ACCESS_ERR`，或对端 SEND 完成而数据写不进去 |

**所以这个练习的正确读法是**：

| 层 | 谁在校验 | 期望结果 |
|---|---|---|
| `ibv_reg_mr` | **内核 `ib_check_mr_access()`** | 组合非法 → `EINVAL`，**连注册都过不去** |
| 收数据时 | **网卡 / 软件实现的 MR access 位** | 注册成功但权限不足 → 接收侧 `LOC_ACCESS_ERR`；对端 `REMOTE_ACCESS` 失败 |

> **【结论】** 「接收缓冲必须设 `IBV_ACCESS_LOCAL_WRITE`」有两层保障：内核挡住最危险的组合，硬件挡住其余情况。**别指望报错来找 bug** —— 一定在代码 review 阶段就看权限表（第 4.3.3 节的「权限组合速查」）。

### D4. 注入错误 4：两端 `path_mtu` 不一致

```c
/* 发送侧（client）： */
.path_mtu = IBV_MTU_4096,
/* 接收侧（server）： */
.path_mtu = IBV_MTU_256,
```

**先记住：两端 MTU 不一致时，能不能连上取决于硬件/驱动的宽松程度。**

| 场景 | 期望现象 |
|---|---|
| 两端**只改 MTU、不传大消息** | 常常**能连上**（RTR 迁移不校验对端 MTU），但 CQE 可能正常 |
| 发送 `-s`/消息 > 256 字节 | **接收侧或发送侧报错 / 数据截断 / 卡住** |
| 用 perftest 时 | **`check_mtu()` 会交换 MTU 并静默取较小值**（`perftest:src/perftest_communication.c:2098-2103`，**没有任何打印**）—— 所以 perftest 上不容易复现，**必须用自写程序**。（会打印 `... mismatch:` 的是参数协商 `negotiate_params()`，见 `perftest:src/perftest_negotiation.c:321-324`，只针对 size/iters/tx_depth 等参数，**不针对 MTU**） |
| 更严格的做法 | 有的驱动在 RTR 时校验，直接 `ibv_modify_qp` 失败（`EINVAL`） |

**用 perftest 交叉验证（推荐）**：

```bash
# hostA
ib_write_bw -d <ibdev> -i 1 -x <idx> --mtu=4096 --report_gbits -F
# hostB —— 故意给 256
ib_write_bw -d <ibdev> -i 1 -x <idx> --mtu=256  --report_gbits -F <hostA-ip>
# 观察 hostB/hostA 打印的 MTU 是否被统一到 256，以及带宽是否骤降
```

**抓包佐证**：`ib_write_bw` 是 **WRITE**，每个包带 16 字节 RETH（`rxe_hdr.h:526-530`），所以 MTU=256 时抓到的以太网帧长应该是 `14+20+8+12+16+256+4 = 330` 字节（IPv4、无 VLAN，即 `256 + 74`），而不是 `4096 + 74`。（若换成 `ib_send_bw`（SEND，无 RETH），同样 MTU 下才是 `256 + 58 = 314`。）

### D5. 注入错误 5：CQ 深度 < 在途 WR 数 → `IBV_EVENT_CQ_ERR`

```c
/* 正确：CQ 深度 >= 在途 WR 总数 */
cq = ibv_create_cq(ctx, 64, NULL, NULL, 0);
/* 注入：CQ 只有 2 个槽，却一次性投 16 个 SIGNALED 的 WR */
cq = ibv_create_cq(ctx, 2, NULL, NULL, 0);

/* 然后一次投 16 个（每个都 SIGNALED），并且"故意不去 poll" */
for (int i = 0; i < 16; i++) {
    wrs[i].wr_id = i;
    wrs[i].send_flags = IBV_SEND_SIGNALED;   /* ★ 全部要 CQE */
    wrs[i].next = (i == 15) ? NULL : &wrs[i+1];
}
ibv_post_send(qp, &wrs[0], &bad);
printf("posted 16 SIGNALED WRs into a CQ of depth 2, not polling...\n");
sleep(3);   /* ★ 关键：不 poll，让 CQE 堆积溢出 */
```

| 观察项 | 期望结果 |
|---|---|
| 异步事件 | **`IBV_EVENT_CQ_ERR`**（CQ overrun） |
| 从哪看 | 用 `ibv_asyncwatch`（见实验 F）或自己的 async 事件线程 |
| CQE 是否还在 | 溢出后 CQ 语义不再可靠；后续 `ibv_poll_cq` 可能返回 0 或异常 |
| 软件实现源码 | `kernel:drivers/infiniband/sw/rxe/rxe_cq.c:64-72`：`queue_full()` 为真时打印 `queue full` 并投递 `IB_EVENT_CQ_ERR` |

> **【正确做法】** `cqe >= 在途 WR 数`。用「批量发、稀疏 SIGNALED」（每 N 个只给最后一个 `IBV_SEND_SIGNALED`）时，**在途未收割 CQE 数 = 你标了 SIGNALED 的 WR 数**，不是总 WR 数。
> 这条错误在真卡上也一样会来，只是表现为 `IBV_EVENT_CQ_ERR` + 后续 CQE 混乱。

### D6. 注入错误 6：GID index 选错 → 连不上

```c
/* trace_obj.c / cm_* 里把 gid_index 改成明显越界的值 */
./trace_obj mlx5_0 999
```

| 注入方式 | 期望结果 |
|---|---|
| `sgid_index` **越界**（>= `gid_tbl_len`） | **`ibv_modify_qp` 失败，`errno = EINVAL`** —— 内核 `kernel:drivers/infiniband/core/cache.c:1187-1188` 校验 `index >= table->sz` 后返回 `-EINVAL`，`verbs.c:524-525` 把它透传上来 |
| `sgid_index` 指向**非 RoCEv2 的行**（例如 v1 或 link-local） | `ibv_modify_qp` **可能成功**，但**连不上**：对端收不到 / `RETRY_EXC_ERR` |
| `sgid_index` 指向**另一个 IP 的 GID**（管理网） | 报文从错误的源 IP 发出，对端 ARP/路由不通 → `RETRY_EXC_ERR` |

**诊断三件套**：

```bash
ibv_devinfo -d <ibdev> -v | grep 'GID\['   # ① 确认哪一行是 RoCE v2 + 业务 IP
sudo tcpdump -i <netdev> -nn -c 5 -v 'udp port 4791'
# ② 看源 IP 是不是你以为的那个（这一条最直接）
ip neigh show                            # ③ 对端 IP 的 ARP 是否有条目
```

**交叉验证（第 12.4 节的技巧）**：

```bash
# perftest 用 -R（RDMA-CM，让 CM 自己选 GID）
ib_write_bw -d <ibdev> -i 1 --report_gbits -F -R
# 若 -R 能通而固定 -x 不通 → 一定是 GID index 选错了
```

### D7. 注入错误速查表（把这张表背下来）

| # | 注入的错误 | 现象 | 错误码 / 事件 | 从哪一章找原因 |
|---|---|---|---|---|
| 1 | `lkey` 错（跨 PD / 废弃 / 编造） | `post_send` 成功入队，CQE 报错 | **`IBV_WC_LOC_PROT_ERR`**，后续 `WR_FLUSH_ERR` | 第 [4.3.3](../04-verbs-model.md)/[4.3.4](../04-verbs-model.md) 节；`kernel:drivers/infiniband/sw/rxe/rxe_mr.c:713` |
| 2 | `rkey` 错 / 对端未给 `REMOTE_WRITE` | 对端回 NAK，本端 CQE 报错 | **`IBV_WC_REM_ACCESS_ERR`**（对端 AETH `0x62`） | 第 [2.3](../02-rocev2-protocol.md)/[4.3.4](../04-verbs-model.md) 节；`rxe_resp.c:1692` |
| 3a | 接收缓冲漏 `LOCAL_WRITE` 且带 `REMOTE_WRITE` | **`ibv_reg_mr` 直接失败** | **`errno = EINVAL`** | 第 [4.3.3](../04-verbs-model.md)/[7.6.4](../07-kernel-rdma-core.md) 节；`kernel:include/rdma/ib_verbs.h:4645` |
| 3b | 接收缓冲 access = 0（注册成功） | 收数据时报错 / 收不到 | **`IBV_WC_LOC_ACCESS_ERR`** 或对端失败 | 第 [4.3.3](../04-verbs-model.md) 节 |
| 4 | 两端 `path_mtu` 不一致 | perftest 自动取小值；自写程序上大消息截断/卡住 | 可能无显式错误码，表现为**数据错误或超时** | 第 [2.1](../02-rocev2-protocol.md)/[4.3.5](../04-verbs-model.md) 节 |
| 5 | CQ 深度 < 在途 SIGNALED WR 数 | CQ 溢出，完成事件丢失/混乱 | **异步事件 `IBV_EVENT_CQ_ERR`** | 第 [4.3.4](../04-verbs-model.md)/[5.6.3](../05-hands-on-code.md) 节；`rxe_cq.c:64` |
| 6 | `sgid_index` 越界 | `ibv_modify_qp` 失败 | **`errno = EINVAL`** | 第 [12.4](../12-troubleshooting.md) 节；`core/cache.c:1187` |
| 6b | `sgid_index` 指向错的 GID 行 | 连不上 / 卡住 | **`IBV_WC_RETRY_EXC_ERR`**（重试耗尽） | 第 [2.5](../02-rocev2-protocol.md)/[12.4](../12-troubleshooting.md) 节 |
| 7（附加） | 对端没 post RECV 且 `rnr_retry=0` | 发送侧快速失败 | **`IBV_WC_RNR_RETRY_EXC_ERR`**（AETH `0x20`） | 第 [4.3.5](../04-verbs-model.md) 节 |

### D8. 注入实验的记录模板

每注入一个错误，填一行。**这张表是你自己的排障手册**：

| 注入 | 预期（书上写的） | 我实际看到的 | 一致？ | 差异原因 |
|---|---|---|---|---|
| `lkey` 错 | `LOC_PROT_ERR` | | | |
| `rkey` 错 | `REM_ACCESS_ERR` | | | |
| 漏 `LOCAL_WRITE` | `reg_mr` 返回 `EINVAL` | | | |
| MTU 不一致 | 数据错/卡住 | | | |
| CQ 深度 2 + 16 WR | `IBV_EVENT_CQ_ERR` | | | |
| `sgid_index = 999` | `modify_qp` `EINVAL` | | | |

---

## 实验 E：在四个 QP 状态点上 `ibv_query_qp`

第 4.3.5 节的状态机图是「画出来」的；本节要**在每一步把它读回来**。

### E1. 加一个打印函数

```c
/* qp_dump.c 片段 —— 插到你的程序里，每步迁移前后各调一次 */
static const char *qp_state_str(enum ibv_qp_state s)
{
    switch (s) {
    case IBV_QPS_RESET: return "RESET";
    case IBV_QPS_INIT:  return "INIT";
    case IBV_QPS_RTR:   return "RTR";
    case IBV_QPS_RTS:   return "RTS";
    case IBV_QPS_SQD:   return "SQD";
    case IBV_QPS_SQE:   return "SQE";
    case IBV_QPS_ERR:   return "ERROR";
    default:            return "?";
    }
}

static void dump_qp(struct ibv_qp *qp, const char *tag)
{
    struct ibv_qp_attr a;
    struct ibv_qp_init_attr ia;
    memset(&a, 0, sizeof(a));

    /* ★ 本版本没有 IBV_QP_ALL 之类的一次性宏：需自行按需列出 IBV_QP_* 位
     *  （verbs.h:1040-1070 的 enum ibv_qp_attr_mask；下面按本函数真正读的字段列全） */
    if (ibv_query_qp(qp, &a,
                     IBV_QP_STATE | IBV_QP_CUR_STATE | IBV_QP_ACCESS_FLAGS |
                     IBV_QP_CAP | IBV_QP_PATH_MTU | IBV_QP_DEST_QPN |
                     IBV_QP_RQ_PSN | IBV_QP_SQ_PSN | IBV_QP_TIMEOUT |
                     IBV_QP_RETRY_CNT | IBV_QP_RNR_RETRY |
                     IBV_QP_MAX_QP_RD_ATOMIC | IBV_QP_MAX_DEST_RD_ATOMIC |
                     IBV_QP_MIN_RNR_TIMER | IBV_QP_PKEY_INDEX | IBV_QP_PORT |
                     IBV_QP_AV, &ia)) {
        perror("ibv_query_qp"); return;
    }

    printf("== %-22s qp_num=0x%06x\n", tag, qp->qp_num);
    printf("   state            = %s (%d)\n", qp_state_str(a.qp_state), a.qp_state);
    printf("   cur_qp_state     = %s\n", qp_state_str(a.cur_qp_state));
    printf("   path_mtu         = %d   (IBV_MTU_256=%d 512=%d 1024=%d 2048=%d 4096=%d)\n",
           a.path_mtu, IBV_MTU_256, IBV_MTU_512, IBV_MTU_1024, IBV_MTU_2048, IBV_MTU_4096);
    printf("   dest_qp_num      = 0x%06x\n", a.dest_qp_num);
    printf("   rq_psn/sq_psn    = 0x%06x / 0x%06x\n", a.rq_psn, a.sq_psn);
    printf("   qp_access_flags  = 0x%x\n", a.qp_access_flags);
    printf("   pkey_index/port  = %u / %u\n", a.pkey_index, a.port_num);
    printf("   timeout/retry    = %u / %u   rnr_retry=%u\n", a.timeout, a.retry_cnt, a.rnr_retry);
    printf("   max_rd_atomic    = %u   max_dest_rd_atomic=%u  min_rnr_timer=%u\n",
           a.max_rd_atomic, a.max_dest_rd_atomic, a.min_rnr_timer);
    printf("   ah: is_global=%u port_num=%u sgid_index=%u hop_limit=%u tclass=%u flow_label=0x%05x\n",
           a.ah_attr.is_global, a.ah_attr.port_num, a.ah_attr.grh.sgid_index,
           a.ah_attr.grh.hop_limit, a.ah_attr.grh.traffic_class, a.ah_attr.grh.flow_label);
    printf("   cap: max_send_wr=%u max_recv_wr=%u max_send_sge=%u max_inline_data=%u\n",
           ia.cap.max_send_wr, ia.cap.max_recv_wr, ia.cap.max_send_sge, ia.cap.max_inline_data);
}
```

**调用序列：**

```c
dump_qp(qp, "① after ibv_create_qp");        /* RESET */
/* ibv_modify_qp → INIT */
dump_qp(qp, "② after modify R->INIT");       /* INIT  */
/* ibv_modify_qp → RTR */
dump_qp(qp, "③ after modify INIT->RTR");     /* RTR   */
/* ibv_modify_qp → RTS */
dump_qp(qp, "④ after modify RTR->RTS");      /* RTS   */
```

```bash
gcc -O0 -g qp_state_lab.c -o qp_state_lab -libverbs
./qp_state_lab mlx5_0 3
```

### E2. 四个状态点的「期望读数」对照表

| 字段 | ① RESET | ② INIT | ③ RTR | ④ RTS | 依据 |
|---|---|---|---|---|---|
| `a.qp_state` | `IBV_QPS_RESET`(0) | `IBV_QPS_INIT`(1) | `IBV_QPS_RTR`(2) | `IBV_QPS_RTS`(3) | `verbs.h` 的 `enum ibv_qp_state` |
| `path_mtu` | 未定义/0 | 未定义/0 | **你设的值**（如 1024） | 同 RTR | `IBV_QP_PATH_MTU` 只在 RTR 生效 |
| `dest_qp_num` | 0 | 0 | **对端 QPN** | 同 RTR | `IBV_QP_DEST_QPN` |
| `rq_psn` | 0 | 0 | **对端 SQ 的 PSN 起点** | 同 RTR | `IBV_QP_RQ_PSN` |
| `sq_psn` | 0 | 0 | 0 | **本端 SQ 的 PSN 起点** | `IBV_QP_SQ_PSN` 只在 RTS 生效 |
| `qp_access_flags` | 0 | **你设的 4 个位** | 同 INIT | 同 INIT | `IBV_QP_ACCESS_FLAGS` 只在 INIT 设 |
| `pkey_index` / `port_num` | 0 | **0 / 1** | 同 INIT | 同 INIT | `IBV_QP_PKEY_INDEX`、`IBV_QP_PORT` |
| `ah_attr.grh.sgid_index` | 0 | 0 | **本端 GID index** | 同 RTR | `IBV_QP_AV` |
| `ah_attr.grh.hop_limit` | 0 | 0 | **你设的值或邻居解析结果** | 同 RTR | `IBV_QP_AV`（内核可能覆盖，见第 5.5.2 节） |
| `ah_attr.grh.traffic_class` | 0 | 0 | **你设的值**（→ IP TOS/DSCP） | 同 RTR | `IBV_QP_AV` |
| `timeout` / `retry_cnt` / `rnr_retry` | 0 | 0 | 0 | **你设的值** | `IBV_QP_TIMEOUT`、`IBV_QP_RETRY_CNT`、`IBV_QP_RNR_RETRY` |
| `max_dest_rd_atomic` | 0 | 0 | **你设的值** | 同 RTR | `IBV_QP_MAX_DEST_RD_ATOMIC` |
| `max_rd_atomic` | 0 | 0 | 0 | **你设的值** | `IBV_QP_MAX_QP_RD_ATOMIC` |
| `min_rnr_timer` | 0 | 0 | **你设的值**（如 12） | 同 RTR | `IBV_QP_MIN_RNR_TIMER` |

### E3. 两个必读的「为什么」

**① 为什么 `ibv_query_qp` 要把掩码列全？**

```c
/* 掩码控制"内核要不要为该字段填值"。不给掩码位 = 字段保持 0（mlx5_ib_query_qp 会先 memset） */
ibv_query_qp(qp, &attr, IBV_QP_STATE, &ia);            /* 只有 qp_state 有意义 */
/* 想要全部字段：自己把需要的 IBV_QP_* 位或起来（调试时把上面 dump_qp 的掩码抄过来） */
ibv_query_qp(qp, &attr,
             IBV_QP_STATE | IBV_QP_CUR_STATE | IBV_QP_ACCESS_FLAGS |
             IBV_QP_CAP | IBV_QP_PATH_MTU | IBV_QP_DEST_QPN |
             IBV_QP_RQ_PSN | IBV_QP_SQ_PSN | IBV_QP_TIMEOUT |
             IBV_QP_RETRY_CNT | IBV_QP_RNR_RETRY |
             IBV_QP_MAX_QP_RD_ATOMIC | IBV_QP_MAX_DEST_RD_ATOMIC |
             IBV_QP_MIN_RNR_TIMER | IBV_QP_PKEY_INDEX | IBV_QP_PORT |
             IBV_QP_AV, &ia);
```

> **本版本没有 `IBV_QP_ALL` 之类的一次性宏**，需自行按需列出 `IBV_QP_*` 位（`rdma-core:libibverbs/verbs.h:1040-1070` 的 `enum ibv_qp_attr_mask`，枚举止于 `IBV_QP_RATE_LIMIT = 1 << 25`）。**用掩码只取你需要的字段**在生产代码里更省系统调用（少一次 write/ioctl 载荷）。

**② `qp_state` 与 `cur_qp_state` 的区别**

| 字段 | 含义 |
|---|---|
| `qp_state` | **你想要迁移到的目标状态**（写路径用） |
| `cur_qp_state` | **当前实际所处的状态**（读路径有意义） |

调用 `ibv_query_qp` 时 `qp_state` 可能被回填成当前状态，**要判断"现在在哪"请以 `cur_qp_state` 为准**。这也是为什么很多人 `ibv_query_qp` 后觉得自己"读错了状态"。

### E4. 内核的两层校验（读一次源码，理解报错从哪来）

```c
/* 第一层：通用语义（kernel:drivers/infiniband/core/verbs.c:1763 ib_modify_qp_is_ok） */
bool ib_modify_qp_is_ok(enum ib_qp_state cur_state, enum ib_qp_state next_state, ...);
/*   查 qp_state_table[IB_QPS_ERR + 1][IB_QPS_ERR + 1]（verbs.c:1462）
     表里 valid=false 的迁移一律拒绝，并检查该迁移的 req_param/opt_param */

/* 第二层：驱动专属（kernel:drivers/infiniband/hw/mlx5/qp.c:3668 opt_mask[][][]）
   mlx5_ib_modify_qp 里：optpar &= opt_mask[mlx5_cur][mlx5_new][mlx5_st];  （qp.c:4513）
   把该状态迁移下"允许的 optpar"裁剪掉不允许的 */
```

**动手验证第一层**：

```c
/* 跳过 INIT，直接从 RESET 打 RTR */
struct ibv_qp_attr a = { .qp_state = IBV_QPS_RTR, /* ... 其余字段 ... */ };
int rc = ibv_modify_qp(qp, &a, IBV_QP_STATE | IBV_QP_AV | IBV_QP_PATH_MTU |
                               IBV_QP_DEST_QPN | IBV_QP_RQ_PSN);
printf("RESET->RTR rc=%d errno=%d(%s)\n", rc, errno, strerror(errno));
/* 期望：rc != 0，errno = EINVAL */
```

> 这解释了为什么第 4.2 节的 10 步流程里 `ibv_modify_qp` 必须**调三次**：不是 API 设计啰嗦，而是**状态机不接受跳跃**。

---

## 实验 F：不靠 `printf` 的调试（异步事件 + 计数器）

**问题**：`ibv_post_send` 返回 0 不代表什么都不出错；很多错误是**异步**来的（QP FATAL、CQ ERR、端口 DOWN、GID 变化）。在数据路径里插 `printf` 会直接毁掉性能，还会掩盖时序问题。

### F1. 用 `ibv_asyncwatch` 把异步事件变成一行行日志

```bash
# 终端 1：盯着设备
ibv_asyncwatch -d <ibdev>
# rxe 也可以：ibv_asyncwatch -d rxe0
```

```bash
# 终端 2：一边压测，一边制造事件
ib_write_bw -d <ibdev> -i 1 -x <idx> --report_gbits -F -D 60 --run_infinitely

# 终端 3：制造一个事件（选一个）
sudo ip link set <netdev> down ; sleep 2 ; sudo ip link set <netdev> up   # → PORT_ERR / PORT_ACTIVE
sudo ip addr del 192.168.100.1/24 dev <netdev>                            # → GID_CHANGE
```

**期望在终端 1 看到的形状（示意）**：

```text
async event: LID change
async event: port error
async event: port active
async event: GID table change
async event: QP fatal on QP 0xXXXXXX
```

**RoCE 工程师必须处理的三个事件**（第 4.3.9 节）：

| 事件 | 什么时候来 | 正确处理 |
|---|---|---|
| **`IBV_EVENT_GID_CHANGE`** | **RoCE 特有**：netdev 的 IP/VLAN 变化 → GID 表变化 → 你缓存的 gid_index 可能已失效 | 重新 `ibv_query_gid` / 重建 QP |
| `IBV_EVENT_PORT_ERR` / `IBV_EVENT_PORT_ACTIVE` | 链路抖动 | 暂停发送、等 ACTIVE、按需重建 |
| `IBV_EVENT_QP_FATAL` | QP 进 ERROR | **重建 QP**（不能只改回 RESET 后继续用旧的协议状态） |

### F2. 自己写事件线程（15 行）

```c
/* async_thread.c 片段 —— 起一个线程专门收异步事件，主线程只管数据路径 */
#include <pthread.h>
#include <infiniband/verbs.h>

static volatile int g_stop = 0;

static void *async_monitor(void *arg)
{
    struct ibv_context *ctx = arg;
    struct ibv_async_event ev;

    while (!g_stop) {
        if (ibv_get_async_event(ctx, &ev)) {        /* 阻塞直到有事件 */
            if (g_stop) break;
            perror("ibv_get_async_event");
            break;
        }
        switch (ev.event_type) {
        case IBV_EVENT_CQ_ERR:      fprintf(stderr, "[async] CQ_ERR (overrun) cq=0x%x\n",  ev.element.cq->handle); break;
        case IBV_EVENT_QP_FATAL:    fprintf(stderr, "[async] QP_FATAL qpn=0x%06x\n",       ev.element.qp->qp_num); break;
        case IBV_EVENT_QP_REQ_ERR:  fprintf(stderr, "[async] QP_REQ_ERR qpn=0x%06x\n",     ev.element.qp->qp_num); break;
        case IBV_EVENT_PORT_ERR:    fprintf(stderr, "[async] PORT_ERR port=%d\n",           ev.element.port_num); break;
        case IBV_EVENT_PORT_ACTIVE: fprintf(stderr, "[async] PORT_ACTIVE port=%d\n",        ev.element.port_num); break;
        case IBV_EVENT_GID_CHANGE:  fprintf(stderr, "[async] GID_CHANGE port=%d\n",         ev.element.port_num); break;
        case IBV_EVENT_DEVICE_FATAL:fprintf(stderr, "[async] DEVICE_FATAL → 应让全程序退出\n"); g_stop = 1; break;
        default:                    fprintf(stderr, "[async] event type=%d\n",              ev.event_type); break;
        }
        ibv_ack_async_event(&ev);        /* ★ 必须 ack，否则事件队列会一直堆 */
    }
    return NULL;
}

/* 用法： */
pthread_t tid;
pthread_create(&tid, NULL, async_monitor, ctx);
/* ... 主线程只做 post_send / poll_cq ... */
g_stop = 1;
/* 让 ibv_get_async_event 返回的办法：销毁 QP/关闭设备前先制造一次事件，或用 poll(ctx->async_fd) */
pthread_join(tid, NULL);
```

> **【实现细节】** `struct ibv_context` 有 `async_fd` 成员，可以直接 `poll(ctx->async_fd, ...)` 实现「可中断的等待」—— 这是让事件线程优雅退出的标准做法。

### F3. Counter 路线：不打印任何东西也能定位问题

**思路**：把「程序内部状态」换成「网卡/内核计数器」。计数器是**零侵入**的，加在数据路径外面。

```bash
DEV=mlx5_0 ; ND=$(ls /sys/class/infiniband/$DEV/device/net/ | head -1)

# ---------- ① 跑测试前先拍一张"底片" ----------
ethtool -S $ND | grep -Ei 'pause|ecn|cnp|roce|discard|drop|retrans' > /tmp/snap.before
ls /sys/class/infiniband/$DEV/ports/1/counters/ | head -20
cat /sys/class/infiniband/$DEV/ports/1/counters/port_xmit_data   > /tmp/snap.before.ib
cat /sys/class/infiniband/$DEV/ports/1/counters/port_rcv_data   >> /tmp/snap.before.ib
cat /sys/class/infiniband/$DEV/ports/1/counters/port_xmit_discards >> /tmp/snap.before.ib

# ---------- ② 跑测试 ----------
ib_write_bw -d $DEV -i 1 -x <idx> --report_gbits -F -D 30

# ---------- ③ 拍"后片"并求差 ----------
ethtool -S $ND | grep -Ei 'pause|ecn|cnp|roce|discard|drop|retrans' > /tmp/snap.after
diff -y --suppress-common-lines /tmp/snap.before /tmp/snap.after
```

**本实验最该看的 6 个计数器**（第 12.5.3 节）：

| 计数器 | 位置 | 正常值 | 不为正常值时说明 |
|---|---|---|---|
| `port_xmit_discards` | `ports/1/counters/` | **0** | 发送被丢弃（PFC/缓冲/链路问题） |
| `port_rcv_errors` | `ports/1/counters/` | **0** | 接收侧校验/协议错误 |
| `out_of_buffer` | `ports/1/hw_counters/`（或 `ethtool -S`） | **0** | 缓冲不足 → **PFC/ECN 没配好** |
| `roce_adp_retrans` | `hw_counters/` / `ethtool -S` | **0（一票否决）** | 网络在丢包，任何性能结论都无效 |
| `np_ecn_marked_roce_packets` | `hw_counters/` / `ethtool -S` | 压测时应有增长 | 完全不增长 → ECN 没生效（查 DSCP） |
| `roce_slow_restart_cnps` | `hw_counters/` / `ethtool -S` | 少量正常 | 持续增长 → 拥塞未被控制 |

```bash
# 逐项读（有的设备没有 hw_counters 子目录，那就走 ethtool -S）
for f in /sys/class/infiniband/$DEV/ports/1/counters/*; do
    printf "%-28s %s\n" "$(basename $f)" "$(cat $f 2>/dev/null)"
done
```

> **【为什么 Counter 比 printf 好】** ① 零性能损失；② 能看到**内核和硬件视角**（你的 printf 只能看到你的视角）；③ 可以**事后**对比（拍底片 → 跑 → 拍后片），不需要预先知道要打什么。

### F4. 「不打印」的第三种武器：`ibv_query_qp` + 退出码

生产程序的正确姿势：

```c
/* 数据路径里不做任何 IO；错误只记录到内存里的统计结构 */
struct stats { uint64_t tx, rx, err_loc_prot, err_rem_acc, err_rnr, err_flush; };

/* 主循环结束（或每 N 秒）才 dump 一次 */
static void dump_stats(struct stats *s)
{
    fprintf(stderr, "tx=%lu rx=%lu | LOC_PROT=%lu REM_ACC=%lu RNR=%lu FLUSH=%lu\n",
            s->tx, s->rx, s->err_loc_prot, s->err_rem_acc, s->err_rnr, s->err_flush);
}
```

`WR_FLUSH_ERR` 计数暴涨 ⇒ **QP 已经进 ERROR**，去看**第一个非 FLUSH 的错误**（第 4.3.4 节的铁律）。

### F5. 用 gdb 看「数据路径里到底填了什么」

```bash
gcc -O0 -g cm_client.c -o cm_client -lrdmacm -libverbs
gdb -q ./cm_client
(gdb) break ibv_post_send
(gdb) run 192.168.100.1
# 命中后：
(gdb) print *wr
(gdb) print wr->opcode
(gdb) print/x wr->wr.rdma.rkey
(gdb) print/x wr->wr.rdma.remote_addr
(gdb) print wr->sg_list[0]
(gdb) finish          # 看返回值
```

**gdb 的三个高价值断点**：

| 断点 | 为什么 |
|---|---|
| `ibv_post_send` | 看 WQE 字段是不是你想的（尤其 `lkey`/`rkey`/`remote_addr`） |
| `ibv_modify_qp` | 看 `attr->ah_attr.grh.sgid_index` / `.dgid`（GID 类问题的第一现场） |
| `ibv_poll_cq` 返回处 | 看 `wc.status` 的**原始值**（printf 的字符串可能被截断/误导） |

> **【注意】** 用 `-O2` 编译时 `wr` 可能已被优化进寄存器，`print *wr` 会失败。**调试请用 `-O0 -g`。**

---

## 故障速查（本实验最可能遇到的问题）

| 症状 | 最可能原因 | 处理 |
|---|---|---|
| `gcc` 报 `undefined reference to ibv_create_qp` | 链接顺序错 / 缺 `-libverbs` | 用 `-lrdmacm -libverbs`，且放在源文件之后 |
| `gcc` 报找不到 `<rdma/rdma_cma.h>` | 缺 `librdmacm-dev` | `sudo apt install librdmacm-dev` |
| `cm_client` 卡在 `rdma_resolve_addr` | 对端 IP 不可达 / 没有到该 IP 的 RoCE GID | `ping` 先通；用 `ibv_devinfo -v` 的 `GID[  N]` 确认业务 IP 有 RoCE v2 GID |
| `cm_client` 卡在 `wait_event(...ESTABLISHED)` | 服务端没起 / 防火墙拦 7471 | `ss -tlnp \| grep 7471`；放通端口 |
| `ibv_reg_mr` 返回 NULL | `ulimit -l` 太小 | `ulimit -l unlimited`（或用 `--mmap` 类的内存后端思路） |
| `ibv_create_qp` 返回 NULL | `max_send_wr` 超过设备上限 | 查 `ibv_devinfo -v` 的 `max_qp_wr`；降深度 |
| `modify_qp INIT->RTR` 失败 `EINVAL` | `sgid_index` 越界 / `is_global=0` | 用 `ibv_devinfo -v` 的 `GID[  N]` 重选；RoCE 必须 `is_global = 1` |
| 程序"卡住"且无任何输出 | `rnr_retry = 7`（无限重试）+ 对端没投 RECV | 用实验 C0 的 `poll_with_timeout()`；实验里把 `rnr_retry` 设 0 |
| `strace` 里看不到 `write` | 用的是新式 ioctl ABI | 改成 `-e trace=write,ioctl,mmap,openat`，看 `ioctl(..., RDMA_VERBS_IOCTL, ...)` |
| `ibv_asyncwatch: command not found` | 缺 `ibverbs-utils`（**不是** `infiniband-diags`） | `sudo apt install ibverbs-utils`（`rdma-core:debian/ibverbs-utils.install:1` 含 `usr/bin/ibv_asyncwatch`；lab01 路线 1 已装，故这条排障路径本身可能误导；打包归属随发行版而异） |
| 实验 C1 里对端收到了数据但"没有任何 CQE"，以为是 bug | **这是正确行为** | 纯 WRITE 不给对端 CQE；要通知就用 `WRITE_WITH_IMM` |
| 实验 D4 用 perftest 复现不出 MTU 错配 | perftest 的 `check_mtu()` 自动取小值 | 必须用自写程序做这个注入 |

---

## 本实验的「完成标准」

- [ ] `libibverbs-dev` / `librdmacm-dev` 检查通过，`printf` 探针程序能编译
- [ ] 用 `-lrdmacm -libverbs` 编译并**成功运行**第 5 章的 `cm_client` / `cm_server`（两机或 `rxe0`）
- [ ] 抓包确认这对程序发的是 **UDP 4791**，且 BTH Dest QP 等于服务端打印的 QPN
- [ ] 用 `strace -f -e trace=write,ioctl,mmap,openat` 抓到 `/dev/infiniband/uverbsN` 的 `openat` 与后续的 `write`/`ioctl`
- [ ] 能从日志中**指出**：`ibv_open_device`、`ibv_alloc_pd`、`ibv_reg_mr`、`ibv_create_cq`、`ibv_create_qp` 各对应哪一条系统调用，并说明 `mmap` 的作用
- [ ] 能说明 `ibv_post_send` / `ibv_poll_cq` **为什么不出现在 `strace` 里**
- [ ] 实验 C1：`RDMA_WRITE` 在对端**没有 post RECV** 的情况下成功，且对端数据正确
- [ ] 实验 C2：`SEND` 在对端没有 RECV 时拿到 `RNR_RETRY_EXC_ERR`（或观察到无限重试）
- [ ] 实验 C3：`WRITE_WITH_IMM` 对端收到 `IBV_WC_RECV_RDMA_WITH_IMM` + 正确的 `imm_data`，并**消耗掉一个 RECV WR**
- [ ] 实验 D 的 6 个注入全部做过，并填完 D8 的记录模板
- [ ] 能不看资料说出：`LOC_PROT_ERR` / `REM_ACCESS_ERR` / `RNR_RETRY_EXC_ERR` / `WR_FLUSH_ERR` 各指向什么根因
- [ ] 实验 E：在 RESET / INIT / RTR / RTS 四点各打印一次 `ibv_query_qp`，并与 E2 的表逐行核对
- [ ] 试验过 `RESET → RTR` 的跳跃迁移，看到 `EINVAL`
- [ ] 用 `ibv_asyncwatch` 观察到至少一种 `IBV_EVENT_*`，并能说出该事件该做什么
- [ ] 写出（或抄通）一个异步事件线程，`ibv_ack_async_event()` 没漏
- [ ] 跑过一次「拍计数器底片 → 压测 → 对比」的流程，能解释 `roce_adp_retrans` 为什么是"一票否决"

**下一步**：带着这套「能从错误码反推根因」的能力，进入 [`lab03-tuning-and-troubleshooting.md`](lab03-tuning-and-troubleshooting.md) —— 把性能调优变成 A/B 实验，把排障变成分层检查。
