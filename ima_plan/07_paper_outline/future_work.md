> 最近更新: 2026-03-28

# Future Work 与当前局限性

> 本文件梳理 GRASP 当前方案的已知局限和开放问题，用于论文 Discussion / Future Work / Limitations 部分。
> 每个条目标注来源、影响范围和可能的解决方向。

---

## 1. IMAD.WIDE 检测的泛化性：32-bit vs 64-bit Index Type

**来源**: cuGraph 24.6.0 SASS 分析（`01_ima_characterization/sass_analysis/cugraph/`）

### 现象

GRASP 的 Chain Detector (CD) 以 `IMAD.WIDE` 作为 IMA 链的检测签名。在 Gardenia benchmark（32-bit `int` index）上，这一签名覆盖率为 88–99%（Insight 7）。但对 NVIDIA cuGraph 的 sm_80 编译产物进行 SASS 分析发现：

| Index Type | 典型来源 | IMAD.WIDE 链 | variant 链 | IMAD.WIDE 占比 |
|------------|---------|-------------|-----------|---------------|
| `int` (32-bit) | Gardenia, Gunrock, GAPBS | 654/711 | 57/711 | **92%** |
| `int` (32-bit) | cuGraph `graph_view_t<int,int>` | 0/112 | 112/112 | **0%** |
| `long long` (64-bit) | cuGraph `graph_view_t<long,long>` | 36/527 | 491/527 | **7%** |

### 根因分析

`IMAD.WIDE.U32` 的乘法操作数限制为 32-bit，地址扩展到 64-bit 指针由指令内部完成（32×32+64→64）。这在简单 kernel（Gardenia 的直接数组访问 `A[B[i]]`）中完美适用。

但 cuGraph 的深度模板元编程（CUB `for_each` + transform_iterator + zip_iterator + 多层 functor inlining）产生了更复杂的寄存器分配压力，即使在 32-bit index 场景下，nvcc 也倾向于将地址计算拆分为：

```
LDG.E  R_idx, [R_addr1.64]         ; index load
IMAD.SHL.U32 R_lo, R_idx, scale, RZ ; low 32-bit of index*scale
SHF.L.U64.HI R_hi, R_idx, shift, R_carry ; high 32-bit
IADD3 R_addr2_lo, R_base_lo, R_lo, RZ    ; add base (low)
IMAD.X R_addr2_hi, ..., R_base_hi, P     ; add base (high) + carry
LDG.E  R_data, [R_addr2.64]        ; data load
```

这与 `IMAD.WIDE` 在语义上完全等价，但使用了 4–5 条指令。

对 64-bit index（`long long`），`IMAD.WIDE` 无法处理 64×64 乘法，编译器**必须**拆分，因此 variant 比例更高。

### 关键澄清

- **学术 benchmark 主流是 32-bit index**：Gardenia, Gunrock, GAPBS, Ligra 等均默认 `int`。2^31 = 21 亿顶点足以覆盖几乎所有标准图数据集
- 在简单 kernel + 32-bit index 场景下（即本文评估设定），`IMAD.WIDE` 检测有效且高覆盖
- cuGraph 的 0% IMAD.WIDE 是**模板元编程深度**和 **iterator 抽象层级**的产物，不是优化级别（两者都是 -O3）或数据类型的直接结果
- 但不能断言所有 production 代码都会保持 IMAD.WIDE——这是一个 **generalizability limitation**

### 手动验证的反例

cuGraph `transform_reduce_by_src_dst_key_hypersparse<graph_view_t<int,int>>` 中：
- CSR offset 查询：`LEA R16, P0, R15, c[...], 0x2` + `LDG.E R14, [R16.64]` — LEA 变体
- 但同一函数更深处的 bitmap 查询仍使用：`IMAD.WIDE R16, R16, R17, c[...]` + `LDG.E R17, [R16.64]` — canonical IMAD.WIDE

说明**同一个 kernel 内部两种模式可以共存**。

### Future Work 方向

1. **扩展 CD 模式匹配**：增加 `IMAD.SHL.U32 → IADD3` 和 `LEA` 变体的检测路径，hardware cost 增加有限（额外 2-3 个操作码比较器）
2. **编译器协同**：在 PTX → SASS lowering 阶段标记 IMA 地址计算指令（类似 `prefetch.global` hint），消除对特定指令模式的依赖
3. **通用寄存器依赖图方法**：以更高硬件代价（全指令 Rd/Rs 追踪）实现 ~100% 覆盖

**论文适用段落**: Discussion（检测泛化性）, Future Work（扩展方向）

---

## 2. SpMV 的大规模循环展开使 Stride 学习失效

**来源**: `05_implementation/grasp_ablation/README.md` §3, INDEX.md 待解决问题

### 现象

SpMV kernel 被编译器 ×16 展开，导致同一源码 IMA load 产生 16 个不同 PC 的 LDG。GRASP 的 IST (Iteration Stride Tracker) 基于同一 PC 的连续两次执行来学习 stride，但 ×16 展开后：

- 16 个 PC 中只有第 1 和第 16 个（间隔 15 个 unroll 步）执行间的地址差是 `stride × 16`
- 中间 14 个 PC 各只执行一次就切到下一个，IST 看到的是不同 PC 的交替执行，**无法学到 stride**
- 结果：16 个 chain 中只有 4-5 个学到 stride，其余 pipeline 空转
- SpMV 消融实验：**-2%**（略有下降），3M RFAIL 表明 MSHR 饱和

### 影响范围

仅影响 SpMV 类 Pattern I（线性 gather）的大展开场景。BFS/SSSP（×4 展开）不受影响。

### Future Work 方向

1. **Unroll-aware stride normalization**：检测同一 `(base, scale)` 下多个 PC 的地址序列，在 TT 层面归并后学习归一化 stride
2. **Compiler-assisted unroll factor annotation**：在 SASS metadata 中标注展开因子，IST 用 `stride / unroll_factor` 作为学习目标
3. **Adaptive prefetch distance**：在 MSHR 压力高时自动增大 throttle（当前 80% 阈值未触发）

**论文适用段落**: Evaluation（SpMV 负面结果分析）, Future Work

---

## 3. Pattern III/IV 的覆盖空白

**来源**: Insight 8（四类 IMA Pattern Prefetchability）

### 现状

GRASP 有效覆盖 Pattern I（SpMV 线性 gather）和 Pattern II（BFS/SSSP/BC frontier-driven），但：

- **Pattern III（Data-Dependent, e.g., CC hook）**: 第一层 index 可预取，但第二层 data 地址依赖第一层 data 值，timeliness ≈ 0。GRASP 只能预取 index，data 仍需 demand fetch
- **Pattern IV（Pointer Chasing, e.g., CC shortcut）**: 纯数据依赖链，MLP ≈ 0，GRASP 的 stride-based 方法完全无效

### Future Work 方向

1. **Runahead execution for Pattern III**：在 index prefetch 命中后，speculative 执行地址计算并发起 data prefetch（类似 CPU runahead，但 per-warp）
2. **Value prediction for Pattern IV**：对 pointer chase 目标的数据值进行简单预测（last-value / stride），以推测性发起下一跳 prefetch
3. **Compiler 标注 IMA 层级**：在代码中标注 IMA 深度（1-hop / 2-hop / chain），prefetcher 据此选择策略

**论文适用段落**: Discussion（declared limitations）, Future Work

---

## 4. Data Prefetch 的 Lane Coalescing 缺失

**来源**: 设计问题 P6, INDEX.md

### 现象

当前 GRASP 的 DPU (Data Prefetch Unit) 为每个 lane 独立发起 data prefetch request。在 32 个 lane 的 warp 中，如果多个 lane 的 data 地址落在同一 cache line，会产生冗余的 prefetch request，浪费 MSHR 和 L1 带宽。

### 影响

- 在 MSHR 已经接近饱和的场景（如 SpMV）可能加剧 RFAIL
- 冗余 request 浪费 NoC 带宽

### Future Work 方向

实现轻量级 coalescer（类似 L1 cache 的 sector-based coalescing），将同一 cache line 的多个 prefetch request 合并为一个。硬件代价：一个 128-byte aligned tag 比较器 + 合并逻辑。

**论文适用段落**: Design（noted limitation）, Future Work

---

## 5. 评估覆盖面的局限

**来源**: `06_evaluation_plan/benchmark_suite.md`

### 当前评估范围

- **算法**: BFS, SSSP, BC, CC, SpMV（5 个核心 + TC, PR 待评估）
- **图数据集**: 主要使用 roadNet, USA, web graph（ima_high 级别）
- **GPU 配置**: SM80_A100（单一配置）
- **仿真模式**: trace-driven（GPGPU-Sim）

### 已知盲区

| 维度 | 未覆盖 | 影响 |
|------|-------|------|
| **图规模** | ima_med / ima_small 的 ideal L1D 数据未补全 | 无法量化 GRASP 在不同 IMA 密度下的表现梯度 |
| **多 GPU 配置** | 仅 SM80_A100 | 无法论证跨架构有效性（sm70/sm90 的 cache hierarchy 不同） |
| **Real silicon** | trace-driven 仿真 vs 真实硬件 | 仿真器简化了 MSHR/NoC/scheduler 行为 |
| **Non-graph IMA** | 未涵盖 hash table lookup, tree traversal 等非图 IMA | GRASP 的 stride-based IST 对非图 IMA 的有效性未知 |

### Future Work 方向

1. 补全 ima_med/ima_small 评估，量化 IMA 密度与 GRASP 收益的关系
2. 扩展到 sm70/sm90 配置验证跨架构稳定性
3. 探索 hash table / B-tree 等非图数据结构的 IMA prefetching

**论文适用段落**: Evaluation（threats to validity）, Future Work

---

## 6. Throttle Control 策略不足

**来源**: 实验问题 E3, SpMV 分析

### 现象

当前 throttle 策略基于 MSHR 占用率 80% 阈值暂停 prefetch 发射。但在 SpMV 上：

- MSHR 饱和是**瞬时**的（burst access），80% 阈值在采样周期内被跳过
- 累计 3M RFAIL（prefetch request 被 MSHR 拒绝）

### Future Work 方向

1. **Rate-based throttle**: 不基于瞬时 MSHR 占用，而是限制每 N cycle 的 prefetch 发射速率
2. **Accuracy-aware throttle**: 跟踪 prefetch accuracy（useful / total），accuracy 低时主动降速
3. **Per-chain throttle**: 对不同 chain 独立节流，避免高精度 chain 被低精度 chain 拖累

**论文适用段落**: Design（throttle 机制）, Future Work

---

## 总结：Future Work 优先级

| 优先级 | 主题 | 论文价值 | 技术难度 |
|--------|------|---------|---------|
| **高** | §1 IMAD.WIDE 检测泛化（32/64-bit + 编译器变体） | 直接回应 reviewer 可能的 generalizability 质疑 | 中 |
| **高** | §2 SpMV 展开问题 | 解释当前唯一的负面实验结果 | 高 |
| 中 | §3 Pattern III/IV 覆盖 | 完善 coverage claim，坦诚 declared limitation | 高 |
| 中 | §6 Throttle 策略 | 改善 MSHR 饱和场景 | 中 |
| 低 | §4 Lane coalescing | 工程优化，非核心贡献 | 低 |
| 低 | §5 评估覆盖面 | 常规 threats to validity | 低 |
