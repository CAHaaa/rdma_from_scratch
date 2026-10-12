# 写作与引用约定（全书统一）

本文件是这套教程的「元规则」。所有章节都遵守同一套术语、代码引用与图示约定，这样你在阅读时不需要反复切换心智模型。

---

## 1. 本教程基于的源码版本

| 组件 | 本地目录 | 版本 | 说明 |
|---|---|---|---|
| Linux 内核 | `linux-7.2.8/linux-7.2.8` | **7.2.8**（`Makefile`: `VERSION=7 PATCHLEVEL=2 SUBLEVEL=8`） | RDMA 子系统：`drivers/infiniband/`、`include/rdma/` |
| rdma-core | `rdma-core-master` | **66.0**（`CMakeLists.txt`: `PACKAGE_VERSION "66.0"`，`IBVERBS_PABI_VERSION "65"`） | 用户态 verbs / CM / 诊断工具 |
| perftest | `perftest-master/perftest-master` | **6.30**（`configure.ac`: `AC_INIT([perftest],[6.30],...)`） | 性能与正确性测试套件 |

> 版本很重要。RDMA 的用户态 ABI（`IBVERBS_PABI_VERSION`）与内核 uverbs ABI 是**向后兼容**演进的：新库可以跑老内核，但用了新特性的程序在老内核上会失败。遇到行为差异时，第一件事是核对这三者的版本。

## 2. 代码引用格式

正文中的代码位置一律写成：

```
<项目>:<相对路径>:<行号>
```

例如 `rdma-core:libibverbs/verbs.c:1234`、`kernel:drivers/infiniband/core/uverbs_ioctl.c:567`、`perftest:src/perftest_parameters.c:89`。

对应的可点击链接约定：

| 前缀 | 链接模板 |
|---|---|
| `kernel:` | `https://github.com/torvalds/linux/blob/v7.2/drivers/...` |
| `rdma-core:` | `https://github.com/linux-rdma/rdma-core/blob/master/...` |
| `perftest:` | `https://github.com/linux-rdma/perftest/blob/master/...` |

> 说明：行号是基于本地快照统计的，**上游 master 上可能已经有 ±几行的漂移**。请以「函数名 / 符号名」为主要锚点，行号只作为快速定位的辅助。

## 3. 术语与语言

- 正文用中文；**所有 ABI 名称、结构体、函数、命令行选项、协议字段一律保留英文原文**（例如 `ibv_post_send`、`IBV_QPT_RC`、`--tx-depth`、`BTH`、`rkey`），不做意译。
- **命令行选项必须逐一核对源码，不能照抄 README。** 本教程的所有 perftest 选项都以 `perftest:src/perftest_parameters.c` 的 `long_options[]` 为准（`README` 中有若干过时项，例如 `--mcg=<num>` 实际不带参数、`-r` 被重复列出、`-D` 已从 `--duplicates` 改为 `--duration`）。
- 首次出现的关键术语给出「中文（English）」，之后仅用 English。
- 术语的完整对照表见 [`glossary.md`](glossary.md)（字母序术语条目）；**按主题查具体取值**（状态迁移掩码、opcode、AETH syndrome、WC 状态码、CM 事件、MTU 算式）见 [`glossary-quickref.md`](glossary-quickref.md)。

### 本教程中最容易被混淆的 6 组概念（务必先分清）

| 容易混淆 | 正确区分 |
|---|---|
| `ibv_*` vs `ib_uverbs` / `uverbs` | 前者是**用户态库函数**（librdmacm/libibverbs），后者是**内核 uverbs 字符设备与 ABI** |
| Verbs API vs RDMA_CM API | Verbs 是「QP 级」原语；RDMA_CM 是「连接级」封装，负责地址/路由解析与建连 |
| `lkey` vs `rkey` | `lkey` 只在本端 WQE 中使用（本地校验）；`rkey` 交给对端用于远端访问校验 |
| QP 状态 vs TCP 状态 | QP 状态是 `RESET→INIT→RTR→RTS` 的硬件状态机；TCP 状态机与它没有一一对应关系 |
| RoCEv1 vs RoCEv2 | v1 是以太网类型 `0x8915` 的二层封装；**v2 是 UDP/IP 封装（目的端口 4791），可路由** |
| `rxe`/`siw` vs `mlx5_ib` | 前者是**软件实现**（无 RDMA 网卡也能学 verbs），后者是真实硬件驱动 |

## 4. 图示约定

- 分层/流程/时序图使用 **Mermaid**（GitHub、VS Code、Typora 均可直接渲染）。
- 报文格式/寄存器位域图使用 **ASCII 位域表**（保证任何终端可读）。
- 需要精确到「哪个字段在哪个字节」的地方，一律给出字节偏移与宽度。
- **本教程不使用位图/SVG 资源**：全部图示都由 Mermaid 或 ASCII 就地生成，因此仓库里没有图片二进制文件（便于 diff 与版本管理）。
- 若将来需要引入 SVG 等矢量图，放在 `docs/assets/`，正文用 `![说明](assets/xxx.svg)` 引用。

## 5. 可复现性约定

- 所有实验命令都以「两台主机 + 一块 RoCE 网卡」为基准模型，用 `hostA` / `hostB` 表示。
- 涉及特权操作的命令前面标注 `# root`。
- 每个实验给出**预期输出特征**（不是死数字），并说明「结果不符合预期时先看哪一章」。
- 环境变量、内核模块参数等一律给出完整可粘贴的命令行。

## 6. 阅读层级标记

章节中会出现三种标记，用来区分「必须掌握」与「按需深入」：

- **【必会】**：RoCE 工程师日常必须能脱口而出的内容。
- **【进阶】**：调优、排障、二开时需要的深层机制。
- **【源码】**：需要读代码才能完全理解的部分，会给出精确路径。

## 7. 安全与合规提醒

- RDMA 是**零拷贝、可远端直接读写内存**的技术，`rkey` 泄露等价于内存泄露。所有涉及 `rkey` 的日志、抓包、示例都必须按敏感信息对待。
- 生产环境修改 PFC/ECN/DCQCN 参数前，必须先在隔离的测试网段验证，并准备好回滚命令（见第 11 章）。
