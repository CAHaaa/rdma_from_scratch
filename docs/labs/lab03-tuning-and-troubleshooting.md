# 实验 3：性能调优与排障实战

> **目标**：把第 6、11、12、13 章的方法论变成**手上的肌肉记忆**。做完这个实验，你将拥有一套**自己的**基线、一套 A/B 实验纪律、和一个能自动跑的健康检查脚本。
>
> **前置**：完成 [实验 1](lab01-environment-and-first-test.md)（有可用的 RoCE 环境）与 [实验 2](lab02-verbs-programming.md)（理解 verbs 语义）。
> **耗时**：3–5 小时（建议分 2–3 次做完）。
> **需要**：两台机器（或一台 + Soft-RoCE；但**性能类实验必须用真卡两台机器**）。

---

## 实验 A：建立你的性能基线（必做，30 分钟）

**没有基线的调优等于盲调。** 这一步的产出是你后面所有对比的参照物。

### A1. 环境冻结（先让环境变干净）

```bash
# root，两台机器都做

# ① 关掉 CPU 变频（否则延迟数字不可信）
#    ★ 需 root。回滚：把 performance 换回原来的 governor（如 ondemand / schedutil / powersave）：
#      for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo schedutil > $g; done
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance > $g 2>/dev/null
done
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # 应输出 performance

# ② 解锁内存（否则 ibv_reg_mr 会 ENOMEM）
ulimit -l unlimited
ulimit -l                    # 应输出 unlimited

# ③ 确认没有其他大流量任务在跑
uptime
ps aux --sort=-%cpu | head -8

# ④ 记录 NUMA 位置（后面绑核要用）
NODE=$(cat /sys/class/infiniband/mlx5_0/device/numa_node)
echo "NIC on NUMA node $NODE ; CPUs: $(cat /sys/devices/system/node/node$NODE/cpulist)"
```

> **【重要】把这些设置记在你的基线表里。** 「在关变频+绑核的条件下」和「默认条件下」的数字**不可比**。

### A2. 采集基线（按顺序跑，记录数字）

```bash
# 变量约定（按你的环境改）
DEV=mlx5_0
PORT=1
GID=<你的 RoCEv2 GID index>     # 用 ibv_devinfo -v 的 GID[  N] 行（或 show_gids，若提供）查
PEER=<对端 IP>

# ① 带宽：单 QP，大消息，最标准的一条
# server:
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 -n 5000
# client:
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 -n 5000 $PEER

# ② 带宽：全尺寸扫描（画曲线，看各尺寸表现）
#   ★ 加 -N 关掉 peak 计算，否则数组会很大
# server:
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -a -N
# client:
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -a -N $PEER
# ★ `-a`（RUN_ALL）会循环 23 个消息尺寸（perftest:src/write_bw.c:348-352 的 `for (i = 1; i < 24; ++i)`）。
#   默认每尺寸 5 秒；如果给它配上 `-D 60`，一条命令就要跑约 23 × 60s ≈ 23 分钟 ——
#   基线扫描请给足时间（或先不加 `-D`，只在定位到关键尺寸后再用长 duration 复测）。

# ③ 带宽：双向（更接近 AI/存储的真实负载）
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -b -s 65536
# （client 同样加 -b）

# ④ 带宽：多 QP（验证 ECMP）
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -q 4 -s 65536
# （client 同样加 -q 4）

# ⑤ 消息率：小消息 PPS
ib_send_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 64 -t 128
# （client 同样参数）
# ★ 这里不要加 -l：`-l N` 是 `--post_list`（每批 post N 个 WR），不是消息大小
#   （perftest:src/perftest_parameters.c:3175）。测 64 字节消息率用 `-s 64` 即可；
#   批量投递是 B3 单独的实验，两个变量不要混在一次测试里。

# ⑥ 延迟：WRITE（小消息、绑核、关 cq-mod）
ib_write_lat -d $DEV -i $PORT -x $GID -F --pin_cores=2,3 -s 2 -n 10000
# （client 同样参数）

# ⑦ 延迟：READ（受 -o 影响）
ib_read_lat -d $DEV -i $PORT -x $GID -F --pin_cores=2,3 -o 16

# ⑧ 正确性（先证明对，再谈快）
ib_write_bw -d $DEV -i $PORT -x $GID --data_validation -t 128
# （client 同样加 --data_validation -t 128）
```

### A3. 填写你的基线表（**把这张表存起来长期维护**）

| 项 | 值 |
|---|---|
| 网卡型号 | |
| 固件版本（`cat /sys/class/infiniband/$DEV/fw_ver`） | |
| 驱动栈（inbox / MLNX_OFED 版本，`ofed_info -s`） | |
| 内核版本（`uname -r`） | |
| rdma-core 版本 | |
| perftest 版本（`ib_write_bw --version`） | |
| PCIe（`lspci -vv -s <PCI> \| grep LnkSta`） | |
| RoCE MTU / netdev MTU | |
| NUMA 节点 / 绑定的核 | |
| CPU governor | |
| 拓扑（直连 / 单跳 / 几层 Clash，ECMP 路径数） | |

| 测试 | 参数 | 基线值 | 日期 |
|---|---|---|---|
| 带宽 单 QP | `ib_write_bw -s 65536` | Gb/s | |
| 带宽 多 QP | `-q 4` | Gb/s | |
| 带宽 双向 | `-b -q 4` | Gb/s | |
| 消息率 | `ib_send_bw -s 64` | Mpps | |
| 延迟 WRITE | `ib_write_lat --pin_cores=2,3` | t_avg / t_99 μs | |
| 延迟 READ | `ib_read_lat -o 16` | t_avg μs | |
| 正确性 | `--data_validation` | PASSED | |

> **【易错】基线表里的「消息率」不要写成 `ib_send_bw -s 64 -l 64`**：`-l N` 是 `--post_list`（每批 post N 个 WR，`perftest:src/perftest_parameters.c:3175`），不是消息大小。加了它测的是「每批 64 个 WR」条件下的吞吐，与 `-s 64` 的纯消息率**语义不同、数字不可比**。post_list 的影响请单独用 B3 实验测量。

> **【经验公式】先算一下你的理论上限**：
> - 单 QP 带宽上限 ≈ **链路速率 ÷ ECMP 路径数**（第 12.6.3 节）
> - 有效载荷带宽上限 ≈ **线速 × MTU/(MTU + 每包帧开销)**（第 2.1 节）
>   - **WRITE 系**（`ib_write_bw`）：每包带 16 字节 RETH，开销 = 14+20+8+12+**16**+4 = **74**；
>   - **SEND 系**（`ib_send_bw`）：无 RETH，开销 = 14+20+8+12+4 = **58**。
> 例如 200G + MTU 4096 + 4 条 ECMP 路径（WRITE）：单 QP 上限 ≈ 50 Gb/s；有效载荷上限 ≈ 200G × 4096/4170 ≈ 196 Gb/s，`-q 4` 才可能接近它。
> **算出这个数，你就能立刻判断「测得对不对」而不是「感觉慢」。**

---

## 实验 B：A/B 实验纪律（1 小时，最重要的习惯）

**一次只改一个变量。** 下面每项都是独立实验：改参数 → 测 → 填表 → 恢复。

### B1. MTU 的影响（验证每包帧开销：WRITE 74 字节）

```bash
# 注意：改 --mtu 前确认两端 netdev MTU 足够
# RoCE MTU 4096 需要 netdev MTU >= 4192（= RoCE MTU 4096 + 96；IPv4 无 VLAN）
#   内核 iboe_get_mtu() 按最坏情况扣 96 字节：GRH40 + UDP8 + BTH12 + XRC4 + AtomicETH28 + ICRC4
#   （kernel:include/rdma/ib_addr.h:179-181）；mlx5 的 active_mtu = min(fw_max_mtu, iboe_get_mtu(netdev->mtu))
#   （kernel:drivers/infiniband/hw/mlx5/main.c:630/634）。
#   4154 只是线缆帧长（IB MTU + 58），按它配置只会得到 IB_MTU_2048。实践建议 4200。
# ★ 改 netdev MTU 会瞬断该口链路（丢包/连接重置）：只在测试环境做，改完确认链路恢复。
ip link show <netdev> | grep mtu
# 需要调大时：sudo ip link set <netdev> mtu 4200

for M in 256 512 1024 2048 4096; do
    echo "=== MTU $M ==="
    # server 侧需同时用相同 --mtu
    # client:
    ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 -n 3000 --mtu=$M $PEER
done
```

**结果表（自己填）**：

| RoCE MTU | 理论有效载荷占比 | BW average[Gb/s] | 与理论是否吻合 |
|---|---|---|---|
| 256 | 77.6% | | |
| 512 | 87.4% | | |
| 1024 | 93.3% | | |
| 2048 | 96.5% | | |
| 4096 | 98.2% | | |

> **占比怎么来的**：`MTU / (MTU + 每包帧开销)`。本节跑的是 **`ib_write_bw`（WRITE）**，每包多带 16 字节 RETH，开销 = 14(以太) + 20(IPv4) + 8(UDP) + 12(BTH) + **16(RETH)** + 4(ICRC) = **74**，所以 256 → 256/330 = 77.6%、1024 → 1024/1098 = 93.3%（与实验 4 的逐字节算式一致）。
> 若换成 SEND 系（`ib_send_bw`，无 RETH），开销是 **58**：256 → 256/314 = 81.5%、1024 → 1024/1082 = 94.6%。**两组数不要混用。**

> **思考**：如果 MTU 4096 时带宽**没有**比 1024 明显提升，说明瓶颈不在包头开销 —— 可能是 PCIe、NUMA、或 ECMP 单路径。**先别继续调 MTU。**

### B2. tx-depth 的影响

```bash
for T in 32 64 128 256 512; do
    echo "=== tx-depth $T ==="
    ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 -n 3000 -t $T $PEER
done
```

**要点**：深度太小 → 管道填不满（带宽低）；太大 → 收益递减且占内存。**找拐点**。

### B3. post_list 的影响（小消息场景才明显）

```bash
for L in 1 8 32 64; do
    echo "=== post_list $L ==="
    ib_send_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 64 -t 128 -l $L $PEER
done
```

**要点**：`-l` 把 N 个 WR 串成一条链一次提交，**突破软件 `post_send` 调用速率上限**。观察 Mpps 是否提升。

### B4. inline_size 的影响（延迟场景）

```bash
for I in 0 64 128 220; do
    echo "=== inline $I ==="
    ib_write_lat -d $DEV -i $PORT -x $GID -F --pin_cores=2,3 -s 64 -I $I -n 10000 $PEER
done
```

**要点**：`-I` ≤ `max_inline_data` 时数据随 WQE 一起发给网卡，**省一次 DMA 读**。观察 `t_avg`。

### B5. pin_cores / NUMA 的影响（延迟场景收益最大）

```bash
# ① 不绑核
ib_write_lat -d $DEV -i $PORT -x $GID -F -n 10000 $PEER
# ② 绑到网卡所在 NUMA 节点的核（推荐）
NODE=$(cat /sys/class/infiniband/$DEV/device/numa_node)
CORES=$(cat /sys/devices/system/node/node$NODE/cpulist)
echo "binding to: $CORES"
ib_write_lat -d $DEV -i $PORT -x $GID -F --pin_cores=$CORES -n 10000 $PEER
# ③ 用 numactl 同时绑 CPU 与内存（更彻底）
numactl --cpunodebind=$NODE --membind=$NODE \
    ib_write_lat -d $DEV -i $PORT -x $GID -F -n 10000 $PEER
```

**结果表**：

| 配置 | t_avg [μs] | t_99 [μs] | t_max [μs] |
|---|---|---|---|
| 不绑核 | | | |
| 绑核（同 NUMA） | | | |
| `numactl --membind` | | | |

> **【预期】跨 NUMA 可能导致延迟恶化数倍、带宽下降 20–50%。** 如果你测出来差异很小，说明网卡的 NUMA 亲和本来就不错。

### B6. 事件模式 vs 轮询（延迟场景，差异最大的单项）

```bash
# ① 事件模式（perftest 默认是轮询，加 -e 才是事件）
ib_write_lat -d $DEV -i $PORT -x $GID -F --pin_cores=2,3 -e -n 5000 $PEER
# ② 轮询（默认）
ib_write_lat -d $DEV -i $PORT -x $GID -F --pin_cores=2,3 -n 5000 $PEER
```

**预期差异：1–3 μs。** 这就是第 4.3.4 节讲的「轮询 vs 事件」的量化结果。

---

## 实验 C：ECMP 实验（30 分钟，最高频的带宽问题）

### C1. 测量多 QP 的扩展性

```bash
for Q in 1 2 4 8; do
    echo "=== qp $Q ==="
    ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 -n 3000 -q $Q $PEER
done
```

**结果表（自己填）**：

| QP 数 | BW average[Gb/s] | 相对 -q 1 的倍数 | 说明 |
|---|---|---|---|
| 1 | | 1.0× | 基准 |
| 2 | | ? | |
| 4 | | ? | |
| 8 | | ? | |

**判读**：

| 现象 | 结论 |
|---|---|
| `-q 4` ≈ 4× `-q 1` | **典型的 ECMP 单路径问题**（一条 QP 走一条路径） |
| `-q 4` ≈ `-q 1` | 不是 ECMP 问题；瓶颈在别处（PCIe/NUMA/网卡本身/对端） |
| `-q 4` 到 2× 就饱和 | ECMP 路径数可能是 2；或已到链路/PCIe 上限 |

### C2. 抓包验证 UDP 源端口熵（确认机制在工作）

```bash
# 在 server 侧抓包
tcpdump -i <netdev> -nn -s 0 -w /tmp/ecmp.pcap 'udp port 4791' &
TCPDUMP_PID=$!

# 跑单 QP 测试
ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 -n 2000 $PEER
sleep 1; kill $TCPDUMP_PID

# 提取 UDP 源端口分布
tcpdump -nn -r /tmp/ecmp.pcap 'udp port 4791' 2>/dev/null \
  | awk '{print $3}' | sed 's/.*\.\([0-9]*\)$/\1/' | sort -n | uniq -c | sort -rn | head -20
```

**判读**：

| 观察 | 结论 |
|---|---|
| 源端口**集中在一个值**（或极少数） | **flow_label 被写死了** → 该 QP 固定走一条路径 |
| 源端口**在 `49152–65535`（0xC000–0xFFFF）范围内分散** | 熵机制工作正常（第 2.7 节） |
| 源端口**不在 0xC000 以上** | 异常 → 检查是否真的是 RoCEv2、是否走了 Soft-RoCE |

```bash
# 精确检查端口范围（0xC000 = 49152）
tcpdump -nn -r /tmp/ecmp.pcap 'udp port 4791' 2>/dev/null \
  | awk '{print $3}' | sed 's/.*\.\([0-9]*\)$/\1/' \
  | awk '{ if ($1 >= 49152) ok++; else bad++ } END { print "in-range:", ok+0, " out-of-range:", bad+0 }'
```

### C3. 网络侧确认（如果你能访问交换机）

```bash
# 在交换机上查看 ECMP 哈希配置（以 NVIDIA/Cumulus 为例）
# net show configuration 或 nv show
# 关键：哈希字段是否包含 L4 源端口（source-port）
#
# 查看某条链路的流量分布（确认是否只走一条）
# show interface counters  → 对比各上行端口的 tx 字节数
```

> **【结论模板】把这一段写进你的排查笔记**：
> ```
> 现象：单 QP 带宽 = 96 Gb/s（链路 200G）
> 分层定位：
>   第 0-3 层全部通过（版本一致、无丢包、无重传）
>   第 4 层发现：-q 4 时带宽 = 191 Gb/s（翻倍）
> 根因：ECMP 哈希把单 QP（单一 5 元组）哈希到同一条上行链路
> 验证：抓包确认该 QP 的 UDP 源端口集中；交换机 ECMP 哈希未含 L4 源端口
> 解决：① 应用侧用多 QP（立即可用）；② 网络侧修改哈希配置（根本解）
> ```

---

## 实验 D：负载下采样计数器（40 分钟）

### D1. 准备采样脚本

```bash
#!/bin/bash
# roce_sample.sh <netdev> <dev> <seconds> —— 持续采样 RoCE 关键计数器
NETDEV=$1; DEV=${2:-mlx5_0}; DUR=${3:-60}
PCI=$(basename $(readlink /sys/class/infiniband/$DEV/device) 2>/dev/null)
PORT_DIR=/sys/class/infiniband/$DEV/ports/1
END=$((SECONDS + DUR))

printf "%-10s %-12s %-12s %-14s %-12s %-12s %-12s\n" \
       TIME PFC_RX PFC_TX ECN_MARKED SLOW_RESTART RETRANS OUT_OF_BUF

while [ $SECONDS -lt $END ]; do
    pfc_rx=$(ethtool -S $NETDEV 2>/dev/null | awk -F: '/rx_prio3_pause:/{gsub(/ /,"",$2);print $2}')
    pfc_tx=$(ethtool -S $NETDEV 2>/dev/null | awk -F: '/tx_prio3_pause:/{gsub(/ /,"",$2);print $2}')
    ecn=$(cat $PORT_DIR/hw_counters/np_ecn_marked_roce_packets 2>/dev/null || echo 0)
    slow=$(cat $PORT_DIR/hw_counters/roce_slow_restart_cnps 2>/dev/null || echo 0)
    retr=$(cat $PORT_DIR/hw_counters/roce_adp_retrans 2>/dev/null || echo 0)
    oob=$(cat $PORT_DIR/hw_counters/out_of_buffer 2>/dev/null || echo 0)
    printf "%-10s %-12s %-12s %-14s %-12s %-12s %-12s\n" \
           "$(date +%T)" "${pfc_rx:-NA}" "${pfc_tx:-NA}" "$ecn" "$slow" "$retr" "$oob"
    sleep 3
done
```

```bash
chmod +x roce_sample.sh
# 终端 3（在 server 机器上）：
./roce_sample.sh <netdev> $DEV 90
# 终端 1（server）：ib_write_bw ... -D 90
# 终端 2（client）：ib_write_bw ... -D 90 $PEER
```

### D2. 判读矩阵（第 11.6.3 节，填空练习）

故意制造三种网络状态，各跑一次长稳测试（`-D 30`），把采样结果与带宽填进表里：

| # | 网络配置 | ECN 标记 | CNP | PFC PAUSE | 重传 | 带宽 | 结论 |
|---|---|---|---|---|---|---|---|
| 1 | 正常（PFC+ECN 都配好） | | | | | | |
| 2 | **只配 PFC，不配 ECN** | | | | | | |
| 3 | **ECN 阈值调小（模拟过度降速）** | | | | | | |

**判读口诀（背下来）**：

| ECN | PFC | 重传 | 带宽 | 诊断 |
|---|---|---|---|---|
| 有 | 少 | **0** | 接近满 | ✅ 理想 |
| **无** | 无 | **有** | 低 | **ECN 完全没工作**（查 DSCP 与交换机阈值） |
| 无 | 有（多） | 0 | 低 | **只靠 PFC 兜底**（配 ECN） |
| 有（很高） | 有（多） | 0 | **低** | **过度降速**（调大 Kmin / 调小 `rp_min_dec_fac`） |
| 少 | 少 | 有 | 低 | **ECN 阈值太大**（调小 Kmin） |
| 有 | 少 | 0 | 高但抖动 | 正常但接近临界（留余量/扩容） |

> **【两条铁律】**
> 1. **`roce_adp_retrans` 与 `roce_adp_retrans_to` 应恒为 0。** 不为 0 就说明网络在丢包，**任何性能分析都失去意义**。
> 2. **PFC PAUSE 计数不应持续快速增长。** 持续增长说明 ECN 没在起作用。

### D3. 查看并记录 DCQCN 参数（只读，不改）

```bash
PCI=$(basename $(readlink /sys/class/infiniband/$DEV/device))
if [ -d /sys/kernel/debug/mlx5/$PCI/cc_params ]; then
    for f in /sys/kernel/debug/mlx5/$PCI/cc_params/*; do
        printf "%-42s %s\n" "$(basename $f)" "$(cat $f)"
    done > /tmp/dcqcn-$(date +%F).txt
    echo "saved to /tmp/dcqcn-$(date +%F).txt"
else
    echo "cc_params 不存在 —— 需要 debugfs 挂载 + 固件 cc_query_allowed 能力"
    mount | grep -q debugfs || echo "  提示：mount -t debugfs none /sys/kernel/debug"
fi
```

> **【注意】这些参数重启即失**（第 11.7.2 节）。**把上面的输出纳入你的配置快照**，否则「重启后性能变差」时你无法对比。

---

## 实验 E：故障注入与定位（1–2 小时，最有价值的部分）

**在测试环境里故意制造故障，练习定位。** 每个故障做完要填「定位记录」。

> **前置**：这些实验会**破坏连通性**，**只能在测试环境做**。每个故障记下修改前的值，做完立即恢复。

### E1. MTU 不匹配

```bash
# 注入：只在一端用 --mtu=1024，另一端用 --mtu=4096（或让 netdev MTU 不一致）
# server: ib_write_bw ... --mtu=4096
# client: ib_write_bw ... --mtu=1024
# 观察：perftest 启动阶段的行为（check_mtu() 会交换并取较小值？还是报错？）
```

| 项 | 你的记录 |
|---|---|
| 现象 | |
| 定位命令 | |
| 根因 | |
| 修复 | |

### E2. DSCP 配错（PFC/ECN 完全失效）

```bash
# 注入：用错误的 --tclass（例如想用 DSCP 26 却写了 --tclass=26）
# client/server: ib_write_bw ... --tclass=26
# 观察：抓包看实际 DSCP；压测时看 ECN/PFC 计数器是否有变化
tcpdump -i <netdev> -nn -c 3 -v 'udp port 4791' | grep -i tos
# ★ tos 0x68（=26<<2，DSCP 26）才是对的；tos 0x1a（=26，DSCP 6、ECN 2）说明你踩了这个坑
```

| 项 | 你的记录 |
|---|---|
| 现象 | |
| 定位命令 | |
| 根因 | |
| 修复 | |

> **【这是现场最高频的配置错误】** 第 11.2.2 节的换算：`--tclass` 填的是 **TOS 值（DSCP << 2）**，不是 DSCP 值本身。

### E3. GID index 选错

```bash
# 注入：-x 指向一个 IPv6 link-local 的 v1 GID（或一个不存在的 index）
# 观察：perftest 在哪一步失败（create QP / modify QP to RTR / connect）
# 交叉验证：用 -R（RDMA_CM）是否还能通
```

| 项 | 你的记录 |
|---|---|
| 现象（失败在哪一步） | |
| 定位命令 | |
| 根因 | |
| 修复 | |
| 为什么 `-R` 能交叉验证 | |

### E4. 只在一端配 PFC

```bash
# 注入：只在 server 的网卡上开 PFC，client 不开（或交换机某一跳不开）
# 观察：压测时哪一端的 PFC 计数在涨；带宽与延迟如何变化
```

| 项 | 你的记录 |
|---|---|
| 现象 | |
| 定位命令 | |
| 根因 | |
| 修复 | |

### E5. NUMA 跨节点（模拟跨 die 的开销）

```bash
# 注入：把内存与 CPU 都绑到网卡所在的**远端** NUMA 节点
NIC_NODE=$(cat /sys/class/infiniband/$DEV/device/numa_node)
# 先确认本机有几个 NUMA 节点 —— 单节点机器没有"远端"可测
NODES=$(ls /sys/devices/system/node 2>/dev/null | grep -c '^node[0-9]')
if [ "$NODES" -lt 2 ]; then
    echo "本机只有 $NODES 个 NUMA 节点 —— 没有远端节点，跳过 E5"
else
    # 找一个不是 NIC_NODE 的节点（两节点机器上就是另一个）
    OTHER=0; [ "$NIC_NODE" = "0" ] && OTHER=1
    numactl --cpunodebind=$OTHER --membind=$OTHER \
        ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 $PEER
fi
# 对比：绑到 NIC_NODE
numactl --cpunodebind=$NIC_NODE --membind=$NIC_NODE \
    ib_write_bw -d $DEV -i $PORT -x $GID --report_gbits -F -s 65536 $PEER
```

| 项 | 你的记录 |
|---|---|
| 跨节点 BW | |
| 同节点 BW | |
| 差异百分比 | |
| 结论 | |

### E6. PCIe 降速的检测（无法注入，只能识别）

```bash
# 检查（不修改硬件）
PCI=$(basename $(readlink /sys/class/infiniband/$DEV/device))
lspci -vv -s $PCI | grep -E 'LnkCap|LnkSta'
```

| 项 | 你的记录 |
|---|---|
| LnkCap | |
| LnkSta | |
| 是否一致 | |
| 若不一致，理论带宽损失 | |

### E7. 两个进程同时压测（资源争用）

```bash
# 注入：同时跑两个 ib_write_bw（同一个网卡）
# 终端1: ib_write_bw ... $PEER &
# 终端2: ib_write_bw ... $PEER &
# 观察：各自带宽 vs 单独跑；CPU 占用；CQ/QP 资源
```

| 项 | 你的记录 |
|---|---|
| 各自带宽之和 vs 单独 | |
| 结论（是否线性） | |

---

## 实验 F：把六层检查做成脚本（30 分钟）

把第 12.1.1 节的分层法变成一个能跑的脚本。

```bash
#!/bin/bash
# roce-healthcheck.sh —— RoCE 六层健康检查
# 用法: roce-healthcheck.sh [DEV] [NETDEV] [GID_INDEX]
DEV=${1:-mlx5_0}
NETDEV=${2:-$(ls /sys/class/infiniband/$DEV/device/net/ 2>/dev/null | head -1)}
GIDIDX=${3:-}
PASS=0; WARN=0; FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
warn() { echo "  [WARN] $1"; WARN=$((WARN+1)); }
bad()  { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "=== RoCE 六层健康检查 ==="
echo "DEV=$DEV  NETDEV=$NETDEV  GID_INDEX=${GIDIDX:-auto}"
echo

echo "【第 0 层】前提"
[ -d /sys/class/infiniband/$DEV ] && ok "ibdev $DEV 存在" || { bad "ibdev $DEV 不存在"; exit 1; }
[ -n "$NETDEV" ] && ok "绑定 netdev = $NETDEV" || bad "找不到绑定的 netdev"
ML=$(ulimit -l); [ "$ML" = "unlimited" ] && ok "memlock = unlimited" || warn "memlock = $ML（注册大内存可能失败）"
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
[ "$GOV" = "performance" ] && ok "CPU governor = performance" || warn "CPU governor = ${GOV:-N/A}（延迟数字可能不准）"
echo

echo "【第 1 层】设备与链路"
LL=$(cat /sys/class/infiniband/$DEV/ports/1/link_layer 2>/dev/null)
[ "$LL" = "Ethernet" ] && ok "link_layer = Ethernet（RoCE）" || bad "link_layer = $LL（不是 RoCE！）"
ST=$(cat /sys/class/infiniband/$DEV/ports/1/state 2>/dev/null)
[ "$ST" = "4" ] && ok "port state = ACTIVE" || bad "port state = $ST（非 ACTIVE）"
SPD=$(ethtool $NETDEV 2>/dev/null | awk -F': ' '/Speed/{print $2}')
[ -n "$SPD" ] && ok "netdev speed = $SPD" || warn "无法读取 netdev 速率"
PCI=$(basename $(readlink /sys/class/infiniband/$DEV/device) 2>/dev/null)
if [ -n "$PCI" ]; then
    CAP=$(lspci -vv -s $PCI 2>/dev/null | awk -F'[ ,]+' '/LnkCap/{for(i=1;i<=NF;i++) if($i=="Speed"||$i=="Width") printf "%s ",$(i+1); print ""}')
    STA=$(lspci -vv -s $PCI 2>/dev/null | awk -F'[ ,]+' '/LnkSta/{for(i=1;i<=NF;i++) if($i=="Speed"||$i=="Width") printf "%s ",$(i+1); print ""}')
    [ -n "$STA" ] && echo "  [INFO] PCIe LnkCap: $CAP / LnkSta: $STA"
fi
MTU_N=$(cat /sys/class/net/$NETDEV/mtu 2>/dev/null)
MTU_R=$(cat /sys/class/infiniband/$DEV/ports/1/rate 2>/dev/null)
ACT_MTU=$(ibv_devinfo -d $DEV -v 2>/dev/null | awk '/active_mtu/{print $2}')
[ -n "$ACT_MTU" ] && ok "RoCE active_mtu = $ACT_MTU, netdev mtu = $MTU_N"
echo

echo "【第 2 层】GID 与地址"
GIDN=$(ls /sys/class/infiniband/$DEV/ports/1/gids/ 2>/dev/null | wc -l)
[ "$GIDN" -gt 0 ] && ok "GID 表有 $GIDN 个条目" || bad "GID 表为空"
V2COUNT=0
for i in $(ls /sys/class/infiniband/$DEV/ports/1/gids/ 2>/dev/null); do
    T=$(cat /sys/class/infiniband/$DEV/ports/1/gid_attrs/types/$i 2>/dev/null)
    case "$T" in *v2*) V2COUNT=$((V2COUNT+1));; esac
done
[ "$V2COUNT" -gt 0 ] && ok "找到 $V2COUNT 个 RoCEv2 (v2) GID" || bad "没有 RoCEv2 GID —— RoCEv2 无法工作"
if [ -n "$GIDIDX" ]; then
    T=$(cat /sys/class/infiniband/$DEV/ports/1/gid_attrs/types/$GIDIDX 2>/dev/null)
    N=$(cat /sys/class/infiniband/$DEV/ports/1/gid_attrs/ndevs/$GIDIDX 2>/dev/null)
    case "$T" in
      *v2*) ok "指定的 GID[$GIDIDX] 类型 = $T, ndev = $N";;
      *)    bad "指定的 GID[$GIDIDX] 类型 = ${T:-无效}（应为 v2）";;
    esac
fi
echo

echo "【第 3 层】verbs 语义与计数器"
PD=/sys/class/infiniband/$DEV/ports/1
for c in port_rcv_errors port_xmit_discards; do
    V=$(cat $PD/counters/$c 2>/dev/null || echo NA)
    if [ "$V" = "0" ] || [ "$V" = "NA" ]; then ok "$c = $V"; else warn "$c = $V（非 0，需关注）"; fi
done
echo

echo "【第 4 层】网络与拥塞"
for c in roce_adp_retrans roce_adp_retrans_to out_of_buffer; do
    V=$(cat $PD/hw_counters/$c 2>/dev/null || echo NA)
    if [ "$V" = "0" ]; then ok "$c = 0"
    elif [ "$V" = "NA" ]; then echo "  [INFO] $c 不可用（驱动未暴露）"
    else bad "$c = $V（★ 说明在丢包/重传，性能分析无效）"; fi
done
for c in np_ecn_marked_roce_packets roce_slow_restart_cnps; do
    V=$(cat $PD/hw_counters/$c 2>/dev/null)
    [ -n "$V" ] && echo "  [INFO] $c = $V（压测时观察其增长）"
done
PFC=$(ethtool -S $NETDEV 2>/dev/null | grep -cE '(rx|tx)_prio[0-7]_pause:')
[ "$PFC" -gt 0 ] && echo "  [INFO] 发现 $PFC 个 PFC PAUSE 计数器（可观察）"
if command -v mlnx_qos >/dev/null 2>&1; then
    echo "  --- mlnx_qos 摘要 ---"
    mlnx_qos -i $NETDEV 2>/dev/null | grep -iE 'pfc|trust|prio' | head -12 | sed 's/^/    /'
else
    warn "mlnx_qos 未安装 —— 无法检查 PFC/trust 配置（建议安装 MLNX_OFED 工具）"
fi
echo

echo "【第 5 层】主机侧"
NIC_NODE=$(cat /sys/class/infiniband/$DEV/device/numa_node 2>/dev/null)
[ -n "$NIC_NODE" ] && [ "$NIC_NODE" != "-1" ] && \
    ok "网卡在 NUMA node $NIC_NODE，CPUs: $(cat /sys/devices/system/node/node$NIC_NODE/cpulist 2>/dev/null)" || \
    echo "  [INFO] NUMA 信息不可用"
echo

echo "【第 6 层】资源与审计"
if command -v rdma >/dev/null 2>&1; then
    QP=$(rdma res show qp 2>/dev/null | tail -n +2 | wc -l)
    MR=$(rdma res show mr 2>/dev/null | tail -n +2 | wc -l)
    echo "  [INFO] 当前 QP 数 = $QP, MR 数 = $MR（已去掉表头行）"
fi
[ -d /sys/fs/cgroup/rdma ] && ok "RDMA cgroup 已启用（可限制容器资源）" || \
    warn "RDMA cgroup 不存在（CONFIG_CGROUP_RDMA 未开启；容器场景有风险）"
echo

echo "=== 汇总: PASS=$PASS  WARN=$WARN  FAIL=$FAIL ==="
[ $FAIL -eq 0 ] && echo "结论：基础健康。" || echo "结论：存在 FAIL 项，请按第 12 章分层定位。"
exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)
```

```bash
chmod +x roce-healthcheck.sh
./roce-healthcheck.sh mlx5_0 <netdev> <gid_index>
```

**练习**：把脚本跑一遍，对照输出确认每一条的含义。**然后故意制造一个 FAIL**（例如 `-x` 指向 v1 的 GID），确认脚本能报出来。

> **【把它变成常规巡检】** 放进 systemd timer，每 5 分钟跑一次（第 16.5.2 节给了 unit 文件模板）。**但注意：不要在高频巡检里跑性能测试**，那不是健康检查而是负载。

---

## 故障速查（本实验最可能遇到的问题）

| 症状 | 最可能原因 | 处理 |
|---|---|---|
| perftest 报 `Can't produce a report` | CPU 频率取不到（变频或容器限制） | 关变频；或用 `-F` 允许无频点出报告 |
| 延迟数字波动极大 | 没绑核 / 有其他负载 / 变频 | `--pin_cores` + performance governor + 独占环境 |
| `-D` 模式结果与 `-n` 差异大 | `-D` 会剔除首尾 margin（默认 `duration/4`） | 理解差异，或显式设 `-f` |
| 两端报 `mismatch` 退出 | 参数不一致（`size`/`iters`/`tx_depth`/`verb`…） | `negotiate_params()` 会逐项比对；统一参数 |
| `--data_validation` 报错退出 | 约束不满足（须 RC、WRITE/READ、BW、`-t≥32`、`-n≥32`；且与 `-a`、`--post_list>1`、`--run_infinitely`、`--mr_per_qp`、`--payload_file_path`（payload 修改）、`--use-null-mr`、`--gpu_touch` 互斥） | 按第 6.2.7 节的约束表调整（源码：`perftest:src/perftest_parameters.c:1549-1616`） |
| `cc_params` 目录不存在 | debugfs 未挂载 / 固件无 `cc_query_allowed` | `mount -t debugfs none /sys/kernel/debug`；确认固件能力 |
| 计数器文件不存在 | 驱动未暴露该计数器（能力依赖） | 用 `ethtool -S` 替代；或确认网卡/固件支持 |
| `-q 4` 没有提升 | 不是 ECMP 问题（或路径数本来就少） | 按实验 C 的判读表继续查 PCIe/NUMA/对端 |
| 脚本报 `bad interpreter` | 行尾符是 CRLF（在 Windows 上编辑过） | `dos2unix roce-healthcheck.sh` |

---

## 本实验的「完成标准」

- [ ] 建立了自己的**基线表**（含环境冻结条件与全部测试项）
- [ ] 完成了 MTU / tx-depth / post_list / inline / 绑核 / 事件模式 **六组 A/B 实验**并填表
- [ ] 完成 ECMP 实验，能说出「`-q 4` 是否翻倍」说明了什么
- [ ] 抓包验证了 UDP 源端口落在 `0xC000–0xFFFF`
- [ ] 完成负载下计数器采样，能独立完成**判读矩阵**的填空
- [ ] 完成**至少 5 个故障注入**并写下定位记录
- [ ] `roce-healthcheck.sh` 能跑通，且故意制造 FAIL 时能被检出
- [ ] 记录了一份 DCQCN 参数快照（`/tmp/dcqcn-*.txt`）

> **【最重要的交付物不是数字，而是「记录」。】**
> 把上面所有表格填完并存到一个长期维护的文件里（例如 `~/roce-baseline.md`）。**半年后你会感谢现在的自己。**

---

## 下一步

- 想做**协议层**的深入实验（逐字节解码报文、验证 ICRC 不变式）→ [实验 4](lab04-soft-roce-and-protocol-analysis.md)
- 想做**安全与可观测性**实验（PD 隔离、权限验证、资源审计）→ [实验 5](lab05-security-and-observability.md)
- 想系统学习排障方法论 → [第 12 章](../12-troubleshooting.md)
- 想系统学习 PFC/ECN 配置 → [第 11 章](../11-lossless-tuning.md)
