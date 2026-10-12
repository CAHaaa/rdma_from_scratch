# 第 13 章　性能工程：从「能跑」到「跑满」

> **本章目标**：建立**系统化**的性能优化方法。区分「网络瓶颈」「主机瓶颈」「软件瓶颈」，并给出每一类的优化手段与验证方法。
>
> **前置阅读**：第 6 章（测量方法）、第 12 章（排障流程）。**先会用，再会调。**
>
> **重要观念**：性能优化不是「把参数都调到最大」，而是**先找到瓶颈，再针对瓶颈优化**。
>
> **配套实验**：[`labs/lab03-tuning-and-troubleshooting.md`](labs/lab03-tuning-and-troubleshooting.md)（A/B 实验纪律、ECMP 验证、基线表模板）

---

## 13.1 性能模型：带宽与延迟的两个公式

### 13.1.1 带宽的制约因素（最小值决定上限）

```
有效带宽 = min(
    ┌─ 网络路径带宽        ← ECMP 路径数 × 单路径带宽
    ├─ 网卡线速 × (1 - 开销率)   ← MTU 决定开销率（第 2.1 节）
    ├─ PCIe 带宽          ← 代数 × 宽度（第 12.7.2 节）
    ├─ 内存带宽           ← NUMA + 通道数 + 访问模式
    ├─ CPU 处理能力       ← post_send / poll_cq 的指令数 × PPS
    └─ 对端处理能力       ← 单边操作为零，双边操作要算
)
```

**核心方法论**：**逐项测量，找到最小的那一项，然后只优化它。** 优化非瓶颈项是零收益。

### 13.1.2 延迟的构成

```
端到端延迟 = 
    发送端 CPU（post_send）           ~50-100 ns
  + 发送端 PCIe（doorbell + DMA 读）   ~100-300 ns
  + 网卡发送处理                      ~100-200 ns
  + 交换机转发（每跳）                 ~200-500 ns/跳  ★ 跳数越多越明显
  + 网卡接收处理                      ~100-200 ns
  + 接收端 PCIe（DMA 写）              ~100-300 ns
  + 接收端 CPU（poll_cq）              ~50-100 ns
  ─────────────────────────────────────────────
  合计（单跳）                        ~1-2 μs
```

> **【关键洞察】延迟的「木桶效应」更明显**：任何一环的抖动（PFC、中断、调度）都会直接加到总延迟上。**这就是为什么延迟优化主要是「消除抖动」而不是「降低平均值」。**

---

## 13.2 网络层优化

### 13.2.1 MTU：最直接的带宽优化

```bash
# ① 确认两端网卡支持的最大 MTU
ibv_devinfo -d mlx5_0 -v | grep -E 'max_mtu|active_mtu'

# ② 确认 netdev MTU 足够（RoCE MTU 4096 需要 >= 4192，IPv4 无 VLAN）
#    内核 iboe_get_mtu() 按最坏情况扣 96 字节（40+8+12+4+28+4），
#    4154 只是线缆帧长口径，按它配只会得到 IB_MTU_2048
ip link show <netdev> | grep mtu

# ③ 全网统一设置（交换机也要改！）
ip link set <netdev> mtu 4200
# ⚠️ 动态改 MTU 会导致链路瞬时中断（接口 reset），且必须两端 + 沿途交换机同步修改；
#    生产环境请在维护窗口执行，先记录原值以便回滚。

# ④ 测试对比
ib_write_bw ... --mtu=1024
ib_write_bw ... --mtu=4096
```

**收益估算**（第 2.1 节的 58 字节是**线缆帧开销**口径；netdev MTU 的门槛要按内核 `iboe_get_mtu()` 的 96 字节口径算）：

| RoCE MTU | 单包帧开销（SEND，无 RETH） | SEND 有效载荷占比 | 相对 4096 的带宽损失 |
|---|---|---|---|
| 256 | 58 B | 81.5% | -17.3% |
| 512 | 58 B | 89.8% | -8.9% |
| 1024 | 58 B | 94.6% | -4.0% |
| 2048 | 58 B | 97.2% | -1.4% |
| **4096** | 58 B | **98.6%** | 基准 |

> 表中的「相对损失」= 1 −（本尺寸载荷占比 ÷ 4096 的载荷占比），即 256 字节：1 − 81.5/98.6 = 17.3%。
> 若只看「1 − 载荷占比」（即开销占比），对应数值是 18.5% / 10.2% / 5.4% / 2.8%。

> **【易错】上表是 SEND（`ib_send_bw`，无 RETH）口径**，即 `MTU/(MTU+58)`。
> **RDMA WRITE（`ib_write_bw`）的单包消息必须携带 16 字节 RETH**，帧开销是 `58 + 16 = 74`，
> 占比按 `MTU/(MTU+74)` 算：256→77.6%、512→87.4%、1024→93.3%、2048→96.5%、4096→98.2%，
> 相对 4096 的损失分别是 21.0% / 11.1% / 5.1% / 1.7%（第 2.1 节与 lab03 的 B1 表用的就是 WRITE 口径）。
> **两组数不要混用**：用 `ib_write_bw` 量的结果要按 74 字节估上限，用 `ib_send_bw` 才按 58 字节。

> **【注意】MTU 提高会增加单包延迟**（大包传输时间长），所以**延迟敏感的应用反而可能选小 MTU**。这是一个真实的取舍。
> 而且 RoCE MTU 越大，**丢包重传的代价越高**（一个 4096 的包丢了要重传 4096 字节）。

### 13.2.2 ECMP 与多 QP（最高频的带宽问题）

第 2.7 节与第 12.6.3 节已经详细讲过。**总结成操作清单**：

```bash
# ① 先确诊
ib_write_bw ... -q 1     # 记录带宽 B1
ib_write_bw ... -q 4     # 记录带宽 B4
# 若 B4 ≈ 4 × B1 → 确认是 ECMP 单路径问题

# ② 主机侧立即可用的方案：多 QP
ib_write_bw ... -q 8

# ③ 网络侧根本解：交换机 ECMP 哈希加入 L4 源端口
#    （需要网络团队配合，或检查是否已是默认配置）

# ④ 应用侧配合：确认 flow_label 未被写死
#    gRPC/NCCL 等框架通常有多 QP 配置项
```

**多 QP 的数量选择**：

| ECMP 等价路径数 | 建议 QP 数 | 说明 |
|---|---|---|
| 2 | 2–4 | |
| 4 | 4–8 | |
| 8 | 8–16 | QP 太多会增加 CQ 处理开销 |
| 16+ | 8–16 | 收益递减，CPU 成为瓶颈 |

> **【经验】QP 数不是越多越好**：每个 QP 都要占 SQ/RQ 内存、产生独立 CQE、增加轮询开销。**一般是 ECMP 路径数的 1–2 倍是最优区间。**

### 13.2.3 PFC/ECN 调优

见第 11 章。**核心要点**：

| 现象 | 调整 |
|---|---|
| ECN 标记过多、带宽低 | **调大 `Kmin`**（交换机侧）；调小 `rp_min_dec_fac` |
| 有重传 | **调小 `Kmin`**；确认 PFC 生效 |
| PFC 频繁触发 | 配 ECN 承担主要控制；调大 PFC 阈值 |
| 延迟尖刺 | 检查 `rp_dce_tcp_g`、`rp_ai_rate`；确认 CNP 的 DSCP 正确 |

### 13.2.4 DSCP / QoS 的带宽影响

**容易忽略的点**：如果 RoCE 流量落到了**低优先级队列**，而该队列被其他流量挤占，带宽就会异常。

```bash
# 确认 DSCP 正确（第 11.2.2 节）
tcpdump -i <netdev> -nn -v 'udp port 4791' | grep -i tos
# 确认该 DSCP 在交换机上映射到期望的队列
```

---

## 13.3 主机层优化

### 13.3.1 NUMA 亲和（影响巨大，最简单易做）

```bash
# ① 找网卡的 NUMA 节点
NODE=$(cat /sys/class/infiniband/mlx5_0/device/numa_node)
echo "NIC on NUMA node $NODE"

# ② 查看该节点的 CPU 列表
cat /sys/devices/system/node/node$NODE/cpulist

# ③ 用 numactl 绑定（内存也绑，这是关键）
numactl --cpunodebind=$NODE --membind=$NODE ib_write_bw ...

# ④ 或用 perftest 自带的（推荐，它还会处理 mempolicy）
ib_write_bw --pin_cores=<该节点的核> -d mlx5_0 ...
```

**为什么「内存绑定」和「CPU 绑定」都要做**：

- 只绑 CPU：线程在正确的核上跑，但**内存可能分配在远端节点** → 每次 DMA 都走 UPI；
- 只绑内存：内存在本地，但**线程可能被调度到远端核** → poll_cq 的开销变大。

**收益量级**：跨 NUMA 可能导致带宽下降 **20–50%**。**这是最容易拿到的大幅提升。**

### 13.3.2 大页内存

```bash
# 检查当前大页配置
cat /proc/meminfo | grep -i huge
ls /sys/kernel/mm/hugepages/

# 配置 2MB 大页（示例：预留 8GB = 4096 个 2MB 页）
echo 4096 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
# ⚠️ 4096 个 2MB 页 = 直接预留 8GB 物理内存（永久占用，不会给普通页复用）；
#    设置前请确认空闲内存足够，否则会引发 OOM 或分配失败。
# 持久化到 /etc/sysctl.conf：vm.nr_hugepages = 4096

# 用大页跑 perftest
ib_write_bw --use_hugepages ...
```

**大页的三个收益**：

| 收益 | 原因 |
|---|---|
| **MR 注册更快** | 页数少 → `pin_user_pages` 循环次数少（第 7.6.2 节第 ⑩ 步） |
| **TLB miss 更少** | 4KB 页需要 1024 个 TLB 项覆盖 4MB，2MB 页只需 2 个 |
| **DMA 效率更高** | SG 表更短，网卡解析更快 |

**收益量级**：带宽提升 **5–15%**，MR 注册时间可能降低 **数十倍**。

**perftest 的大页实现**（`perftest:src/host_memory.c`）：优先 `MAP_HUGETLB | MAP_HUGE_1GB`，失败回落 2MB，再失败回落普通页（`alloc_huge_pages_with_fallback()`）。

### 13.3.3 PCIe（先检查，再优化）

```bash
# 检查（第 12.7.2 节）
lspci -vv -s <PCI> | grep -E 'LnkCap|LnkSta'
```

| 问题 | 处理 |
|---|---|
| 插槽代数不够 | 换到更高代次的插槽（**物理解决，无法软件优化**） |
| 链路宽度不足 | 检查是否有其他设备共享 PCIe 通道（如 M.2 插槽） |
| **Relaxed Ordering 未开** | `IBV_ACCESS_RELAXED_ORDERING`（第 4.3.3 节）—— 放宽 PCIe 顺序要求，**典型提升 5–10%** |
| TPH（TLP Processing Hints） | 较新硬件支持，perftest `--tph_mem` |

> **【必会】`IBV_ACCESS_RELAXED_ORDERING` 是「免费的带宽」**：它告诉网卡「DMA 写入不需要严格遵守顺序」，从而允许 PCIe 更高效地批量传输。**大多数场景都安全**，perftest 默认就开（除非 `--disable_pcie_relaxed`）。

### 13.3.4 CPU 与中断

```bash
# ① 关变频（延迟测试必备）
cpupower frequency-set -g performance
# 或
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > $g; done

# ② 关 C-state（避免唤醒延迟）
cpupower idle-set -D 0     # 禁用所有 idle state（激进，注意功耗）

# ③ 检查中断分布
grep mlx5 /proc/interrupts
# ④ 中断亲和：分散到网卡所在 NUMA 节点的多个核
#    现代 mlx5 驱动会自动做，但可以手工调整
echo <cpu_mask> > /proc/irq/<irq>/smp_affinity
# ⚠️ 改写 smp_affinity 会立即迁移该 IRQ，**生效瞬间会短暂影响该网卡的全部流量**
#    （丢包/延迟抖动）。生产环境请在维护窗口执行，并先记录原值以便回滚。

# ⑤ 用 isolcpus 隔离核（彻底方案，需重启）
# 内核参数：isolcpus=2,3,4,5 nohz_full=2,3,4,5 rcu_nocbs=2,3,4,5
```

**收益量级**：

| 优化 | 延迟收益 | 带宽收益 |
|---|---|---|
| 关变频 | **显著**（消除周期性尖刺） | 小 |
| 关 C-state | 中（减少唤醒延迟） | 小 |
| isolcpus | 中–大（消除调度干扰） | 小 |
| 中断亲和 | 小–中 | 小–中 |

### 13.3.5 内存访问模式（大带宽场景的关键）

```bash
# 检查内存带宽是否成为瓶颈
# 方法一：perf 看 NUMA 相关的 miss
perf stat -e node-loads,node-load-misses -a sleep 5

# 方法二：用 STREAM 类工具测本机内存带宽，与网卡速率对比
# 若内存带宽 < 网卡带宽 × 2（读+写），则内存就是瓶颈
```

**优化手段**：

| 手段 | 说明 |
|---|---|
| 多内存通道利用 | 大页 + 交错分配（memory interleaving） |
| 避免跨 socket | NUMA 绑定 |
| 缓冲对齐 | 按 cache line（64B）与页对齐，避免伪共享 |
| 分散到多个缓冲 | 避免所有 QP 争用同一块内存的带宽 |

---

## 13.4 软件层优化（verbs 程序）

### 13.4.1 post_send 侧

| 优化 | 做法 | 效果 |
|---|---|---|
| **批量投递** | 用 `wr.next` 链起 N 个 WR，一次 `post_send` | 减少函数调用与门铃次数 |
| **稀疏 SIGNALED** | 只给每 N 个 WR 中的最后一个加 `IBV_SEND_SIGNALED` | 减少 CQE 数量（**带宽提升明显**） |
| **`sq_sig_all = 0`** | 建 QP 时设 | 同上 |
| **INLINE 小消息** | `IBV_SEND_INLINE`（≤ `max_inline_data`） | 省一次 DMA 读，**小消息延迟显著改善** |
| **避免 fence** | 只在必要时用 `IBV_SEND_FENCE` | fence 会串行化 |
| **CQ moderation 慎用** | `-Q`/`cq_mod` 会累积完成 | 带宽可用，**延迟禁用** |
| **限速参数** | `ibv_modify_qp_rate_limit` | 多租户公平性 |

**稀疏 SIGNALED 的代价与正确用法**：

```c
/* 每 64 个 WR 只让最后一个产生 CQE */
#define SIG_EVERY 64
for (i = 0; i < n; i++) {
    wrs[i].next = (i == n - 1) ? NULL : &wrs[i + 1];
    wrs[i].send_flags = ((i % SIG_EVERY) == SIG_EVERY - 1) ? IBV_SEND_SIGNALED : 0;
}
ibv_post_send(qp, &wrs[0], &bad);

/* ★ 代价：出错时你只知道「最后一批（第 64 个 WR）出错了」，
 *   需要回退到上一个已 signal 的 WR 重新发送未确认的部分。
 *   所以：能容忍「批量重传」的场景才用。 */
```

### 13.4.2 poll_cq 侧

| 优化 | 做法 |
|---|---|
| **轮询用批量** | `ibv_poll_cq(cq, 16, wcs)` 一次取多个（perftest 的动态批量见 `poll_completions()`） |
| **避免每次 poll 后敲 CQ 门铃** | 只在 CQ 快满时敲，或按批敲 |
| **多线程分 CQ** | 每个线程自己的 CQ，避免锁 |
| **`IBV_CREATE_CQ_ATTR_SINGLE_THREADED`** | 告诉库「这个 CQ 只有一个线程用」，省掉内部锁 |
| **CQ 大小合理** | 够用即可，太大浪费 cache |

**示例如下**：

```c
/* 批量轮询（推荐） */
struct ibv_wc wcs[32];
int n;
while ((n = ibv_poll_cq(cq, 32, wcs)) > 0) {
    for (int i = 0; i < n; i++) {
        if (wcs[i].status != IBV_WC_SUCCESS) {
            handle_error(&wcs[i]);
            continue;
        }
        handle_completion(&wcs[i]);
    }
}
if (n < 0) { /* CQ 错误 */ }
```

### 13.4.3 线程与 QP 的组织

| 模型 | 适用 | 说明 |
|---|---|---|
| **单线程单 QP** | 延迟敏感 | 最简单、无锁，但受单核限制 |
| **多线程多 QP（1:1）** | 带宽敏感 | 每线程独立 QP+CQ，**推荐** |
| **多线程共享 QP** | ❌ 不推荐 | 需要锁，且违反第 4.6 节的规则 |
| **线程 + 每线程多 QP** | 极高带宽 | 一个线程管多个 QP，减少线程数 |

```c
/* 推荐模式：N 个线程，每线程自己的 QP/CQ/MR 切片 */
for (int t = 0; t < nthreads; t++) {
    pthread_create(&th[t], NULL, worker, &ctx[t]);
    /* ctx[t] 有独立的 qp[t]、cq[t]、buf[t] 切片 */
}
/* 把所有线程绑到网卡所在 NUMA 节点的核上，且互不重叠 */
```

> **【关键】不要把两个线程绑到同一个物理核**（超线程的兄弟核也算）。用 `lscpu -e` 看 CPU 拓扑，按物理核分配。

### 13.4.4 用 DV 进一步减少开销（进阶）

第 9.4 节讲过 DV 的价值。**实测通常能提升小消息的 PPS 5–15%**，主要来自：

- 去掉库函数的参数检查；
- 把 WQE 构造内联进自己的循环；
- 自己控制批量与门铃时机。

```c
/* DV 骨架（第 9.4.2 节的 mlx5dv_qp） */
struct mlx5dv_obj obj = { .qp.in = qp, .cq.in = cq };
struct mlx5dv_qp dv_qp;
struct mlx5dv_cq dv_cq;
obj.qp.out = &dv_qp;
obj.cq.out = &dv_cq;
mlx5dv_init_obj(&obj, MLX5DV_OBJ_QP | MLX5DV_OBJ_CQ);

/* 现在你有了：
 *   dv_qp.sq.buf / .stride      → 自己算 WQE 地址并填充
 *   dv_qp.bf.reg / .size        → 自己敲门铃
 *   dv_qp.dbrec                 → 自己更新 doorbell record
 *   dv_cq.buf / .cqe_size       → 自己轮询 CQE
 *   dv_cq.cq_uar                → 自己敲 CQ 门铃
 */
```

> **【务实建议】先确认瓶颈在软件再上 DV。** 判断方法：把消息大小调到最大（如 8MB），如果带宽依然达不到网络上限，瓶颈在**网络或主机**而不是软件；如果大消息能跑满而小消息 PPS 上不去，**瓶颈在软件**，DV 才有意义。

---

## 13.5 延迟专项优化清单

延迟优化与带宽优化的重点不同。**按收益排序**：

| # | 优化项 | 预期收益 | 代价 |
|---|---|---|---|
| 1 | **用轮询而不是事件模式**（去掉 `-e`） | **1–3 μs** | CPU 100% 占用一个核 |
| 2 | **绑定 CPU 且关变频** | **0.5–2 μs** + 消除尖刺 | 需要独占核 |
| 3 | **NUMA 亲和（内存+CPU）** | 0.3–1 μs | 无 |
| 4 | **小消息用 INLINE** | 0.2–0.5 μs | 占用 WQE 空间 |
| 5 | **关 cq-mod（`-Q 1`）** | 0.5–2 μs（若之前开着） | CQE 变多 |
| 6 | **关 C-state** | 0.1–0.5 μs | 功耗上升 |
| 7 | **减少交换机跳数** | 0.2–0.5 μs/跳 | 拓扑限制 |
| 8 | **MTU 适中**（大 MTU 单包时间长） | 视场景 | 与带宽取舍 |
| 9 | **消除 PFC 触发** | 消除 ms 级尖刺 | 需要网络调优 |
| 10 | **用 DV 减少软件开销** | 0.05–0.2 μs | 复杂度 |

**延迟测试的标准配置**：

```bash
# 一遍拿到最优延迟
ib_write_lat -d mlx5_0 -i 1 -x 3 \
    --pin_cores=2,3 \
    -F \
    --mtu=1024 \
    -I 220 \
    -Q 1 \
    192.168.100.1
```

> **【测量前提】延迟数字只有在「环境干净」时才有意义**：关变频、绑核、无其他负载、无并发测试。
> 报告时要写清这些前提，否则数字无法对比。

---

## 13.6 建立性能基线（工程实践）

### 13.6.1 为什么要基线

**「快」和「慢」是相对的。** 没有基线，你无法判断「当前性能是否正常」，也无法发现性能随时间的退化（固件升级、配置漂移、硬件老化）。

### 13.6.2 基线表模板

| 项 | 值 |
|---|---|
| 硬件型号 | ConnectX-6 Dx，200Gb/s，双口 |
| 固件版本 | 22.39.1002 |
| 驱动 | MLNX_OFED 24.10 / kernel 6.8 |
| PCIe | Gen4 x16（LnkSta = LnkCap ✓） |
| 拓扑 | 单跳，无 ECMP（直连） |

| 测试 | 参数 | 基线值 | 记录日期 |
|---|---|---|---|
| 带宽（单 QP） | `ib_write_bw -s 65536 --mtu=4096 -q 1` | 196.2 Gb/s | 2025-01-15 |
| 带宽（多 QP） | `ib_write_bw -s 65536 --mtu=4096 -q 4` | 197.8 Gb/s | 2025-01-15 |
| 带宽（双向） | `ib_write_bw -s 65536 -b -q 4` | 394.1 Gb/s | 2025-01-15 |
| 全尺寸扫描 | `ib_write_bw -a -N` | 见 CSV 附件 | 2025-01-15 |
| 延迟（WRITE） | `ib_write_lat --pin_cores=2,3 -I 220` | t_avg 1.62 μs / t_99 2.1 μs | 2025-01-15 |
| 延迟（READ） | `ib_read_lat -o 16` | t_avg 2.85 μs | 2025-01-15 |
| 消息率（64B） | `ib_send_bw -s 64` | 8.2 Mpps | 2025-01-15 |
| 正确性 | `ib_write_bw --data_validation` | PASSED | 2025-01-15 |

> **【易错】`-l` 不是消息大小**：`-l N` 是 `--post_list`，表示每批 post N 个 WR（perftest:src/perftest_parameters.c:3175）。
> 测 64 字节消息率只需 `-s 64`；加上 `-l 64` 是在「每批 64 个 WR」的条件下测吞吐，语义完全不同。
> 量化 PPS 时才考虑 `-l`（批量投递能降低每 WR 的门铃/函数调用开销）。

### 13.6.3 自动化（纳入 CI/巡检）

```bash
#!/bin/bash
# roce_baseline.sh —— 定期跑并把结果存 JSON，与基线对比
DEV=mlx5_0; GID=3; PEER=$1
STAMP=$(date +%Y%m%d-%H%M)

# ① 先做一次全尺寸扫描（不加 --out_json，只看屏幕/文本表定位拐点）
# 服务端（在 peer 上跑）： ib_write_bw -d $DEV -i 1 -x $GID --report_gbits -F -a -N
ib_write_bw -d $DEV -i 1 -x $GID --report_gbits -F -a -N $PEER

# ② 再用「逐尺寸 + 每尺寸一个 JSON 文件」的方式留档（见下方循环）

# 与基线对比（用 jq 提取，超阈值告警）
# JSON 顶层是**单个对象**（test_info + results），results 里的键是
# MsgSize / n_iterations / BW_peak / BW_average / MsgRate（perftest:src/perftest_parameters.h:222）
# 加了 --report_gbits 时 BW_average 的单位就是 Gb/s，直接可用

# ⚠️ 注意：perftest 每次写 JSON 都以 O_TRUNC 重新打开文件
#    （perftest:src/perftest_parameters.c:1165-1175 open_file_write()），
#    所以 `-a`（RUN_ALL 循环 23 个尺寸）跑完后，文件里**只剩最后一个尺寸**的结果。
#    ★ 正确做法：**不要**把 -a 和 --out_json 一起用，改为按尺寸循环、每个尺寸一个文件：
for S in 64 256 1024 4096 65536; do
    # server 侧同样循环（perftest 要求两端尺寸一致）
    ib_write_bw -d $DEV -i 1 -x $GID --report_gbits -F -s $S -n 5000 \
        --out_json --out_json_file=/tmp/bw-$STAMP-$S.json $PEER
done
# 之后逐文件提取（每份 JSON 都是单个对象，顶层 test_info + results）：
for f in /tmp/bw-$STAMP-*.json; do
    echo "$f $(jq -r '.results.BW_average' "$f") Gb/s"
done
# jq 提取示例（单个尺寸的文件）：jq -r '.results.BW_average' /tmp/bw-$STAMP-65536.json
```

**告警阈值建议**：任何尺寸的带宽低于基线的 **90%** 就告警。

---

## 13.7 【行业重点】不同场景的优化优先级

| 场景 | 第一优先级 | 第二优先级 | 第三优先级 | 可以忽略 |
|---|---|---|---|---|
| **AI 训练（大消息 AllReduce）** | NUMA + 大页 | 多 QP + ECMP | PCIe 检查 | 小消息 PPS |
| **AI 推理（KVCache 小消息）** | 轮询 + 绑核 | INLINE | 关 cq-mod | MTU（消息本来就小） |
| **存储（NVMe-oF）** | **消除 PFC/重传**（尾延迟） | 绑核 + 轮询 | 大页 | MTU 极致 |
| **数据库（混合）** | 尾延迟（PFC/ECN） | 延迟优化全套 | 多 QP | —— |
| **HPC（MPI）** | 消息率（PPS） | 多 QP | SRQ | MTU |
| **备份/迁移（大块顺序）** | MTU + 带宽 | 多 QP | 大页 | 延迟 |

> **【重要的反直觉结论】存储与数据库场景的首要任务是「消除抖动」而不是「提高平均带宽」。**
> 一个 200G 链路，如果 99.9% 分位延迟因为 PFC 从 15μs 跳到 2ms，数据库的 SLA 就已经破了 —— **平均带宽再高也没用**。
> **这就是为什么第 11 章的 PFC/ECN 调优对存储团队比对本教程其他任何内容都重要。**

---

## 13.8 优化工作流（避免常见陷阱）

```mermaid
flowchart TD
    A["① 定义目标<br/>（带宽? 延迟? PPS? 尾延迟?）"] --> B["② 测量当前值<br/>（多次，记录波动范围）"]
    B --> C["③ 判断瓶颈层<br/>（用第 12 章的分层法）"]
    C --> D["④ 只优化瓶颈层的一项"]
    D --> E["⑤ 重新测量"]
    E --> F{"有改善?"}
    F -->|是| G["记录并回到 ③<br/>（瓶颈可能转移了）"]
    F -->|否| H["回滚这一项<br/>（记录"无效"也是成果）"]
    H --> C
    G --> C
```

**五个常见陷阱**：

| 陷阱 | 表现 | 纠正 |
|---|---|---|
| **一次改多项** | 不知道哪项起了作用 | 一次一项 |
| **优化非瓶颈** | 花了大力气没效果 | 先测量找瓶颈 |
| **不记录基线** | 无法判断是否改善 | 每次改动前后都测 |
| **在脏环境测** | 数字不可复现 | 关变频、绑核、独占 |
| **忽略尾延迟** | 平均值好看但业务体验差 | 看 `t_99`、`t_999`、`t_max` |

> **【重要】「优化无效」也是重要成果。** 它排除了一个可能性，让你能聚焦到真正的瓶颈。**记录它，避免重复劳动。**

---

## 13.9 本章自检

1. 写出带宽的六个制约因素。优化的第一步应该是什么？
2. 延迟由哪几部分构成？为什么说延迟优化主要是「消除抖动」？
3. MTU 从 1024 提到 4096，带宽理论上提升多少（提示：约 4%，见 13.2.1 表）？为什么延迟敏感场景可能反而选小 MTU？
4. 为什么「只绑 CPU」不够，还要「绑内存」？跨 NUMA 的影响量级？
5. 大页的三个收益分别是什么？MR 注册能快多少？
6. `IBV_ACCESS_RELAXED_ORDERING` 为什么是「免费的带宽」？
7. 稀疏 `IBV_SEND_SIGNALED` 的收益与代价分别是什么？
8. 什么时候应该考虑上 DV？判断瓶颈在软件的方法是什么？
9. 列出延迟优化的前三项（按收益排序）。
10. 为什么存储场景的首要任务是消除抖动而不是提高平均带宽？
11. 建立性能基线的三个理由是什么？
12. 「优化无效」为什么值得记录？

**下一章**：RoCE 的安全模型 —— 一个与以太网截然不同的威胁模型。
