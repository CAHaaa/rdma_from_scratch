# RoCE 软件架构与网络编程：从入门到专家

> 一套**基于真实源码**的中文 RoCE（RDMA over Converged Ethernet）教程。
> 所有结论都能在你本地这三个代码仓里验证 —— 这正是本教程与其他资料最大的区别。

---

## 这是什么

这是一套**完整的 RoCE 学习体系**，覆盖从「第一次跑通 perftest」到「能设计并运维千节点 RoCE 网络」的全部内容。它的三条设计原则：

| 原则 | 具体做法 |
|---|---|
| **源码是唯一权威** | 每个结论都给出精确到行的源码引用（`kernel:path:line`、`rdma-core:path`、`perftest:path`）。**不要相信任何二手资料，包括本教程 —— 去核对源码。** |
| **准确优先于通俗** | 编写过程中纠正了大量业界流传但已过时的说法（见下文「本教程纠正的常见错误」）。**宁可难懂，不可说错。** |
| **过程可复现** | 每个机制都配可运行的命令与实验，给出**预期输出特征**和**不合格时的排查方向**。 |

---

## 基于哪些源码

| 组件 | 本地目录 | 版本 |
|---|---|---|
| **Linux 内核** | `linux-7.2.8/linux-7.2.8` | 7.2.8 |
| **rdma-core**（用户态驱动与库） | `rdma-core-master` | 66.0（`IBVERBS_PABI_VERSION 65`） |
| **perftest**（性能测试套件） | `perftest-master/perftest-master` | 6.30 |

> **⚠️ 版本很重要。** RDMA 的用户态 ABI 与内核 ABI 是向后兼容演进的，行为差异往往源于版本不匹配。详见 [`docs/reference/versions-and-abi.md`](docs/reference/versions-and-abi.md)。

---

## 从哪开始

### 📍 三条阅读路径

**路径 A：零基础 → 能跑起来（1 周）**

```
README（本文件）
  → docs/01-rdma-basics.md            # RDMA 的本质与 RoCE 定位
  → docs/labs/lab01-environment-and-first-test.md   # ★ 搭环境 + 跑通第一个测试
  → docs/06-perftest.md               # 会用最常用的工具
  → docs/03-software-stack.md         # 建立四层架构心智模型
```

**路径 B：会跑 → 会写代码（1–3 个月）**

```
docs/02-rocev2-protocol.md            # 协议（含抓包实验）
  → docs/04-verbs-model.md            # ★ 对象模型与编程模型（核心章节）
  → docs/05-hands-on-code.md          # ★ 从零写出可运行程序
  → docs/labs/lab02-verbs-programming.md
  → docs/10-ecosystem.md              # 知道谁在真正用 RoCE
```

**路径 C：会写 → 懂内部/专家（6–12 个月）**

```
docs/07-kernel-rdma-core.md           # ★ 内核 uverbs 机制
  → docs/08-mlx5-provider.md          # ★ 硬件驱动解剖
  → docs/09-libibverbs-internals.md   # 用户态驱动与插件机制
  → docs/11-lossless-tuning.md        # ★ PFC/ECN/DCQCN 实战
  → docs/12-troubleshooting.md        # ★ 排障方法论
  → docs/13-performance.md            # 性能工程
  → docs/14-security.md               # 安全模型
  → docs/15-virtualization.md         # 虚拟化与多租户
  → docs/16-tools.md                  # 工具链与自动化
  → docs/17-expert-roadmap.md         # ★ 能力模型与成长路线
```

### 🗺️ 完整目录

| 章节 | 主题 | 对应源码重点 |
|---|---|---|
| [第 1 章](docs/01-rdma-basics.md) | RDMA 的本质与 RoCE 的定位 | —— |
| [第 2 章](docs/02-rocev2-protocol.md) | **RoCEv2 协议与无损以太网**（逐字节报文） | `rxe_hdr.h`、`rxe_net.c`、`rxe_icrc.c`、`ib_pack.h` |
| [第 3 章](docs/03-software-stack.md) | RoCE 软件栈全景与组件职责 | 各 `Makefile`、`CMakeLists.txt` |
| [第 4 章](docs/04-verbs-model.md) | **Verbs 对象模型与编程模型** | `libibverbs/verbs.h`、`rc_pingpong.c` |
| [第 5 章](docs/05-hands-on-code.md) | 从零写出可运行的 RoCE 程序 | `rc_pingpong.c`、`rdma_client.c` |
| [第 6 章](docs/06-perftest.md) | perftest 深入：从命令行到数据路径 | `perftest:src/*` |
| [第 7 章](docs/07-kernel-rdma-core.md) | **内核 RDMA 子系统与 uverbs 机制** | `drivers/infiniband/core/` |
| [第 8 章](docs/08-mlx5-provider.md) | **硬件驱动解剖：mlx5 RoCE** | `hw/mlx5/`、`mlx5/core/` |
| [第 9 章](docs/09-libibverbs-internals.md) | 用户态驱动：libibverbs 与 libmlx5 | `libibverbs/`、`providers/mlx5/` |
| [第 10 章](docs/10-ecosystem.md) | 上层生态：谁在真正用 RoCE | `ulp/`、`librdmacm/rsocket.c` |
| [第 11 章](docs/11-lossless-tuning.md) | **无损网络部署：PFC、ECN、DCQCN 实战** | `core/port.c`、`hw/mlx5/cong.c` |
| [第 12 章](docs/12-troubleshooting.md) | **性能调优与故障排查方法论** | —— |
| [第 13 章](docs/13-performance.md) | 性能工程：从「能跑」到「跑满」 | —— |
| [第 14 章](docs/14-security.md) | **RoCE 安全模型**（`rkey` 威胁模型） | `core/cgroup.c`、`hw/mlx5/macsec.c` |
| [第 15 章](docs/15-virtualization.md) | 虚拟化、容器与多租户 RoCE | `sriov.c`、`eswitch*.c`、`ib_rep.c`、`mlx5_vfio.c` |
| [第 16 章](docs/16-tools.md) | 工具链与自动化运维 | `infiniband-diags/`、`tests/`、`pyverbs/` |
| [第 17 章](docs/17-expert-roadmap.md) | **成为 RoCE 专家：能力模型与成长路线** | —— |

### 🧪 动手实验

| 实验 | 内容 | 前置 |
|---|---|---|
| [实验 1](docs/labs/lab01-environment-and-first-test.md) | 搭环境（含 Soft-RoCE 仿真）、跑通第一个测试、第一次抓包 | 无 |
| [实验 2](docs/labs/lab02-verbs-programming.md) | verbs 编程实战、strace 追踪、故意注入错误 | 实验 1 |
| [实验 3](docs/labs/lab03-tuning-and-troubleshooting.md) | 建立基线、A/B 实验、ECMP 验证、故障注入、巡检脚本 | 实验 1 |
| [实验 4](docs/labs/lab04-soft-roce-and-protocol-analysis.md) | Soft-RoCE、逐字节解码 RoCEv2 报文、验证 ICRC | 实验 1 |
| [实验 5](docs/labs/lab05-security-and-observability.md) | PD 隔离验证、权限验证、`rkey` 生命周期、安全审计 | 实验 2 |

### 📚 参考手册

| 文件 | 内容 |
|---|---|
| [`docs/reference/repo-map.md`](docs/reference/repo-map.md) | **代码导航总图** —— 三个仓库每个文件的角色 + 「按问题找位置」速查 |
| [`docs/reference/glossary.md`](docs/reference/glossary.md) | 核心术语与概念对照表（带章节交叉引用） |
| [`docs/reference/glossary-quickref.md`](docs/reference/glossary-quickref.md) | **按主题速查取值** —— QP 状态迁移掩码、异步事件、WC 状态码、opcode、AETH syndrome、CM 事件、MTU 算式 |
| [`docs/reference/versions-and-abi.md`](docs/reference/versions-and-abi.md) | 版本、ABI 与兼容性矩阵 |
| [`docs/reference/faq.md`](docs/reference/faq.md) | 高频问题 60 问 |
| [`docs/reference/00-conventions.md`](docs/reference/00-conventions.md) | 本书的写作与引用约定（**读之前建议先看**） |

---

## 快速开始：5 分钟跑通 RoCE

```bash
# ① 安装工具（Debian/Ubuntu）
sudo apt install -y rdma-core ibverbs-utils perftest infiniband-diags tcpdump

# ② 确认设备与 netdev 的对应关系（★ 最可靠的一条命令）
rdma link show
# 输出示例：link mlx5_0/1 state ACTIVE physical_state LINK_UP netdev enp1s0f0

# ③ 找出该用哪个 GID（★ RoCE 新手第一号故障点）
show_gids
# ★ 选 VER=v2 且 IPv4 列 = 你业务 IP 的那一行的 INDEX
#   注：show_gids 是 OFED/发行版附带的脚本，**不在本教程的三个源码仓里**；等价做法是读
#   `ibv_devinfo -d <dev> -v` 的 GID 表，或直接看 /sys/class/infiniband/<dev>/ports/N/gid_attrs/

# ④ 确认端口是以太网模式
ibv_devinfo -d mlx5_0 -v | grep -E 'link_layer|state|active_mtu'

# ⑤ 跑带宽测试（hostA 先起，hostB 后起）
# hostA:
ib_write_bw -d mlx5_0 -i 1 -x <INDEX> --report_gbits -F
# hostB:
ib_write_bw -d mlx5_0 -i 1 -x <INDEX> --report_gbits -F <hostA_ip>
```

**没有 RDMA 网卡？** 用 Soft-RoCE 也能学（跑的是真正的 RoCEv2 报文）：

```bash
sudo modprobe rdma_rxe
sudo rdma link add rxe0 type rxe netdev <你的网卡名>
show_gids | grep rxe0
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F        # 服务端
ib_write_bw -d rxe0 -i 1 -x <INDEX> --report_gbits -F 127.0.0.1   # 客户端（本机回环）
```

> 详细的实验步骤与故障排查见 [`实验 1`](docs/labs/lab01-environment-and-first-test.md)。

---

## 本教程纠正的常见错误

这部分本身就是本教程价值的体现。**下列说法在中文技术资料里广泛流传，但在本教程对应的源码版本中都是错的**：

| 常见说法 | 源码中的事实 | 详见 |
|---|---|---|
| `ibv_post_send` 由 libibverbs 的弱符号 `__ibv_post_send` 提供默认实现，provider 覆盖它 | rdma-core v66 中**没有这些弱符号**。`ibv_post_send` 是 `verbs.h` 里的 `static inline`，只做一次函数指针调用（`qp->context->ops.post_send`） | [第 9 章](docs/09-libibverbs-internals.md) |
| 内核有 `UVERBS_IOCTL_VERSION` 这个 ABI 版本号 | **该符号在本内核中不存在**。**传统 `write()` uverbs 通道**的 ABI 版本常量是 `IB_USER_VERBS_ABI_VERSION 6`（`ib_user_verbs.h:46`）——它不是全树唯一的版本常量（CM ABI 另有 `RDMA_USER_CM_ABI_VERSION 4`，mlx5 厂商 ABI 另有 `MLX5_IB_UVERBS_ABI_VERSION 1`） | [第 7 章](docs/07-kernel-rdma-core.md) |
| 内存注册用 `ib_umem_get()` | **该函数在本内核中已被重构删除**。现在是 `ib_umem_get_desc/attr/attr_or_va/cq_buf/cq_buf_or_va`，输入类型是 `struct ib_uverbs_buffer_desc` | [第 7 章](docs/07-kernel-rdma-core.md) |
| `struct ibv_ah_attr` 里有 `dmac` 字段，RoCE 的 UD 必须手工填目的 MAC | **`ibv_ah_attr` 没有 `dmac` 成员**。内核在 **`rdma_create_user_ah()`** 里通过 `ib_resolve_eth_dmac()` 自动解析（`verbs.c:670`）——这才是 `ibv_create_ah` 走的那条路径（内核侧的 `rdma_create_ah()`，`verbs.c:619`，**不做** dmac 解析），用户只需给 `port_num`/`sgid_index`/`dgid` | [第 5 章](docs/05-hands-on-code.md)、[第 9 章](docs/09-libibverbs-internals.md) |
| QP 的固件命令在 `mlx5_core`（`mlx5_core_create_qp()`） | **两者都不存在**。QP 固件命令在 `drivers/infiniband/hw/mlx5/qpc.c`（`mlx5_qpc_create_qp`） | [第 8 章](docs/08-mlx5-provider.md) |
| mlx5 有 verbs 级的 DCQCN 配置接口 | **没有**。`cong.c` 只提供 **debugfs** 旋钮（`/sys/kernel/debug/mlx5/<PCI>/cc_params/`） | [第 8 章](docs/08-mlx5-provider.md)、[第 11 章](docs/11-lossless-tuning.md) |
| 有 `ibv_get_device_abi_version()` 这个公开函数 | **不存在**。ABI 版本只在 libibverbs 内部路径被检查 | [第 9 章](docs/09-libibverbs-internals.md) |
| perftest 用 `--outstanding` 设置未完成 READ 数 | 真实选项是 **`-o`/`--outs`**。`--outstanding` 是未知选项 | [第 6 章](docs/06-perftest.md) |
| perftest 的 `-g` 是 `--gid-index` | **`-x` 才是 `--gid-index`**；`-g` 是 `--mcg`（且不带参数） | [第 6 章](docs/06-perftest.md) |
| perftest 的 `-D` 是 `--duplicates` | 现在是 **`--duration`** | [第 6 章](docs/06-perftest.md) |
| RoCE 设备名是 `roceP1p1s0f0` | 本版本内核注册的是 **`mlx5_%d`** 或 LAG 时的 `mlx5_bond_%d`。`roceP...` 是发行版 udev 规则产生的 | [第 3 章](docs/03-software-stack.md)、[第 8 章](docs/08-mlx5-provider.md) |
| 用 `iblinkinfo` / `saquery` / `sminfo` 排查 RoCE | 这些工具基于 **SM/SMP**，**纯 RoCE 环境全部不适用**（RoCE 没有子网管理器）。应改用 `show_gids`、`ibv_devinfo`、`ethtool -S`、`rdma res` | [第 16 章](docs/16-tools.md) |

> **【方法论】这些纠正全部来自同一个动作：打开源码看。**
> 这也是本教程希望你带走的最重要能力 —— 详见 [第 17.7 节](docs/17-expert-roadmap.md)。

---

## 代码引用约定

正文中的代码位置一律写成 `<项目>:<相对路径>:<行号>`，例如：

- `kernel:drivers/infiniband/hw/mlx5/wr.c:1027` —— `mlx5r_ring_db()`（门铃）
- `rdma-core:libibverbs/verbs.h:3630` —— `ibv_post_send` 的 `static inline` 实现
- `perftest:src/perftest_resources.c:3500` —— `ctx_modify_qp_to_rtr()`（RoCE 地址向量）

> 行号基于本地快照统计，上游 master 可能有 ±几行漂移。**请以函数名/符号名为主要锚点，行号只作快速定位辅助。**
>
> 完整的引用规范见 [`docs/reference/00-conventions.md`](docs/reference/00-conventions.md)。

---

## 本教程的知识主线

如果你只记住四句话，就是这四句：

```
①  控制平面走内核，数据平面在用户态。
       → 理解了 mmap + doorbell，就理解了 RDMA 一半的性能优势

②  可靠性靠硬件（PSN/ACK/重传），性能靠网络（PFC/ECN/ECMP）。
       → 理解了这句话，就知道为什么 RoCE 部署难在「网络」而不是「网卡」

③  安全边界是 rkey，运维关键是 PFC/ECN。
       → 前者是 RDMA 与 TCP 最本质的安全差异；后者是现场 90% 问题的所在

④  权威永远是源码与规范，不是任何二手资料。
       → 本教程自己也应该被核验
```

---

## 反馈与勘误

本教程基于本地源码快照编写，**如果你在更新的内核 / rdma-core / perftest 上发现结论不成立，那很可能是版本演进导致的 —— 请以你手上的源码为准，并核对 [`versions-and-abi.md`](docs/reference/versions-and-abi.md)。**

发现错误时，正确的处理方式是：

1. 用 `grep`/`read` 确认源码事实；
2. 找到本教程中对应的 `path:line` 引用；
3. 修正并记录「为什么旧说法错了、新事实是什么、从哪个版本开始变的」。

**这个过程本身就是专家能力的体现。**

> **本教程接受过一轮独立的源码级审查。** 那次审查发现的 37 处事实错误已全部修正（例如 MTU 换算用的是内核的 96 字节而非线缆帧开销的 58 字节、`ibv_query_gid_type()` 其实存在、RDMA cgroup 的 `rdma.max` 只接受 `hca_handle=`/`hca_object=`）。**如果你发现仍有错误，欢迎提 issue —— 请附上源码证据。**

---

## 许可与引用

| 内容 | 许可 |
|---|---|
| **正文与文档**（README、`docs/**/*.md`、图表） | **CC BY 4.0** —— 可自由使用、修改、商用，需署名 |
| **代码示例**（C 程序、shell 脚本、命令片段） | **MIT**（也可选 CC BY 4.0）—— 适合直接嵌入你的项目 |

详见 [`LICENSE`](LICENSE)。

**关于上游代码引用**：本教程为教学目的摘录了 Linux 内核（GPL-2.0）、rdma-core（GPL-2.0 或 OpenIB-BSD 双许可）、perftest（同为双许可）的代码片段，每处均以 `项目:路径:行号` 标注出处。**这些片段的版权归各上游项目所有，不受本仓库许可覆盖**，你再分发时需遵守上游许可。完整清单见 [`NOTICE`](NOTICE)。

> **本教程与 NVIDIA / Mellanox / Intel / Broadcom 等任何厂商均无关联**；文中提及的商标归其各自所有者。

**安全提示**：本教程包含会修改系统配置的命令（网络配置、PFC/ECN 参数、模块加载/卸载、sysfs/debugfs 写入）。**在生产环境执行可能导致业务中断，请先在测试环境验证。**
