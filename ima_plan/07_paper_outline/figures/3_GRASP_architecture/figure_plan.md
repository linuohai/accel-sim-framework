# §3 GRASP Design — Figure Plan

> 最近更新: 2026-04-04
> 状态: 图 schema 草案，待逐图细化
> 依赖: `04_prefetcher_design.md`（架构源）, `writing_rules/§3_design.md`（写作规则）, `writing_rules/figure_design.md`（图表规则）

---

## 一、GRASP 架构概要（基于代码 + 04_prefetcher_design.md）

### 两条通路

**Training Path**（issue stage）:
指令流 → CD（FIFO 检测 LDG→IMAD.WIDE→LDG）→ 写入 CT/TT

**Prefetch Path**（demand load + L1 fill）:
demand index load → CT lookup → stride check → IPU 发 index PF → PRB 分配
→ index PF fill 返回 → DPU（base + value×scale）→ data PF → L1

### 组件清单

| 组件 | 源文件 | 触发时机 | 核心结构 |
|------|--------|---------|---------|
| CD (Chain Detector) | `grasp_chain_detector.{h,cc}` | issue stage, 2 tracked warps | 20-entry circular FIFO |
| CT (Chain Table) | `grasp_tables.{h,cc}` | CD 检测到链时写入 | 32 entries, key=index_PC, 含 stride_obs[16] |
| TT (Target Table) | `grasp_tables.{h,cc}` | CD 写入时同步 | 8 entries, key=(base_addr, scale) CAM |
| IST (Iteration Stride Tracker) | `grasp_prefetcher.{h,cc}` | demand load 时 | 64 entries IPT（独立类，与 CT stride 并行） |
| IPU (Index Prefetch Unit) | `on_demand_load()` | demand index load 且 stride_valid | current_addr + iter_stride → coalesce → L1 |
| DPU (Data Prefetch Unit) | `on_fill()` + `release_prb_sector_targets()` | index PF fill 返回 | 读 PRB tt_idx → TT (base,scale) → data_addr |
| PRB (Prefetch Request Buffer) | `grasp_prb_t` | IPU 分配, fill 释放 | 动态容量, per-sector dispatch |
| TC (Throttle Controller) | `inject_prefetch()` 内嵌 | data PF 发射前 | tc_mode=4: MSHR>40% → cooldown 200cy |
| Prefetch Queue | `m_prefetch_queue` (deque) | IPU/DPU enqueue | FIFO, 每 cycle drain 到 L1 |

### 代码 vs 设计文档的关键差异

1. **Stride learning 双轨**：代码中 `grasp_ist_t`（独立 64-entry IPT）和 CT 内 `stride_obs[]` 并行运行。实际起预取作用的是 CT 的 stride（IPU 检查 `ct_entry.stride_valid`）
2. **ACU/Coalescer/Response FIFO**：设计文档详细描述的硬件组件在代码中为软件逻辑（trace-driven 无需 cycle-accurate pipeline）
3. **TC 演进**：设计文档仅描述 stride_valid 门控 + MSHR 隐式节流；代码实现了 5 种 TC mode，推荐 tc_mode=4 T40C200（DSE 验证）
4. **Pair Table (trace-driven)**：通过 `chain_csv` 加载预计算链信息，CT/TT 的 (base,scale) 为 placeholder。论文需说明为 trace-driven simplification

---

## 二、§3 图清单（7 张）

### 总览

| # | 标题 | 尺寸 | §3 小节 | 功能类型 |
|---|------|------|---------|---------|
| Fig A | GRASP 总体架构框图 | 7.0" 双栏 | §3.1 Overview | Mental Model |
| Fig B | 两步 Pipeline 算法流程图 | 3.5" 单栏 | §3.1 Overview | Mental Model |
| Fig C | CD 检测：tracked-warp 链检测 vs multi-warp stride learning | 7.0" 双栏 | §3.2 CD + IST | Mechanism Detail |
| Fig D | CT/TT 表结构 + PC 归并实例 | 3.5" 或 7.0" | §3.3 CT/TT | Mechanism Detail |
| Fig E | Prefetch 运作：IPU→PRB→fill→DPU 时序 | 7.0" 双栏 | §3.5 IPU/DPU | Temporal Behavior |
| Fig F | Throttle Control cooldown 机制 | 3.5" 单栏 | §3.6 TC | Mechanism Detail |
| Fig G | Worked Example：BFS 端到端生命周期 | 7.0" 双栏 | §3.8 Example | Grounding |

密度：7 图 / 3.5 页 = 2.0 fig/page（与 DMP §III 一致）
布局：3 × 3.5" 单栏 + 4 × 7.0" 双栏

---

### Fig A — GRASP 总体架构框图

**目的**：回答 "GRASP 在 SM 中长什么样、数据怎么流"

**内容**：
- Per-SM 视角，展示所有组件在 SM pipeline 中的位置
- 区分 Training path（实线，issue stage → CD → CT/TT）和 Prefetch path（虚线，demand → IPU → L1 → DPU → L1）
- 标注每个组件的 entry 数量和总存储（~2.3 KB/SM）
- 用灰色背景标注 SM 既有组件（Warp Scheduler、L1 Cache、MSHR）
- 用颜色标注 GRASP 新增组件（蓝=index 相关, 橙=data 相关, 绿=IMAD.WIDE/CD）

**参考风格**：DMP Fig 10（hardware overview）+ Snake Fig 14
**颜色规范**：遵循 `figure_design.md` 的 CB10 颜色系统

**待确定**：
- [ ] 是否展示 Prefetch Queue 的位置（在 IPU/DPU 和 L1 之间）
- [ ] TC 在图中如何表示（独立模块 vs IPU/DPU 上的控制信号）

---

### Fig B — 两步 Pipeline 算法流程图

**目的**：回答 "GRASP 两步预取的逻辑流程是什么"

**内容**：
- Flowchart 风格（非硬件图）
- 从 "Instruction Issued" 开始分叉：
  - Training branch: 是否为 tracked warp? → CD FIFO 操作 → chain detected? → 写 CT/TT
  - Prefetch branch: 是否为 index load PC in CT? → stride_valid? → IPU 发 index PF → fill 返回 → DPU 发 data PF
- 用粗框标注 key decision points（stride_valid, MSHR full, throttle suppress）

**参考风格**：DMP Fig 5（3-step detection flow）
**尺寸**：3.5" 单栏，紧凑排列

**待确定**：
- [ ] 是否合并 training 和 prefetch 到一张 flowchart，还是上下分区

---

### Fig C — CD 检测：tracked-warp vs multi-warp

**目的**：展示 GPU 多 warp 执行环境下 GRASP 的两层训练机制

**内容**：
- 左半部分：**多 warp 指令时间线**
  - 纵轴 = warp ID（warp 0-3 示例），横轴 = 时间/cycle
  - 标注 warp 0, 1 为 tracked warps（蓝色高亮）
  - 展示指令交织：warp 0 LDG → warp 2 ALU → warp 0 IMAD.WIDE → warp 1 LDG → ...
  - 标注 CD 只看 tracked warp 的指令（其他 warp 指令灰色虚线）
- 右半部分：**CD FIFO 状态 + stride learning 对比**
  - 上方：FIFO 内容随时间变化（push/invalidate/match 标注）
  - 下方：stride learning 表格，展示多个 warp 的 demand load 如何贡献 stride 观测
  - 标注关键事件："chain detected"、"stride confirmed"

**参考风格**：需要自创（DMP 没有多 warp 追踪的概念，这是 GRASP 独有）
**实例数据**：BFS 的实际 SASS PC 和寄存器编号

**待确定**：
- [ ] 展示几个 warp（4? 更多太密）
- [ ] 是否在同一图中展示 FIFO invalidation 机制（write-inv / read-detection）
- [ ] stride learning 部分的详细程度（简化 vs 完整 per-warp obs 表）

---

### Fig D — CT/TT 表结构 + PC 归并

**目的**：展示 CT/TT 存了什么、多 PC 如何归并到同一 TT entry

**内容**：
- 上方：SpMV SASS 代码片段（3-4 条不同 PC 的 IMAD.WIDE，共享 `c[0x0][0x178]` 和 R16=4）
- 中间：CT 表格（3-4 行，展示不同 index_PC → 不同 CT entry，但 tt_idx[0] 全指向同一 TT entry）
- 下方：TT 表格（1-2 行，展示 (x_base, 4) 和可能的 BC reverse 多 target）
- 箭头：多个 CT entry 的 tt_idx → 汇聚到同一个 TT entry（视觉汇聚效果）

**额外展示**：one-to-many（BC reverse: 1 CT entry → 3 TT entries，用 3 条箭头）

**参考风格**：DMP Fig 9（table structures）+ F-1（真实数据填充）
**实例数据**：
- SpMV: PC 0x03d0, 0x03e0, 0x03f0 → tt_idx[0] 全 = 0 → TT[0] = (x_base, 4)
- BC reverse: PC 0xXXX → tt_idx = [0, 1, 2] → TT[0]=(depths_base,4), TT[1]=(path_counts_base,4), TT[2]=(deltas_base,8)

**待确定**：
- [ ] 单栏 3.5" 够不够（可能需要 7.0" 才能放下 SASS + 两个表 + 箭头）
- [ ] 是否在同一图中同时展示 SpMV 归并 + BC one-to-many，还是拆成两个子图

---

### Fig E — Prefetch 运作：IPU→PRB→fill→DPU 时序

**目的**：展示 GRASP 的核心价值——两步 pipeline 如何 overlap latency

**内容**：
- 双行时间线对比：
  - 上行：**Demand-only** 路径（无 prefetch）
    ```
    index miss → [~560cy wait] → index refill → data issue → [~560cy wait] → data refill
    总延迟 ≈ 1120 cycles
    ```
  - 下行：**GRASP** 路径（有 prefetch）
    ```
    prev iteration: IPU → index PF issued → [~560cy] → index PF fill
                                                         → DPU → data PF issued → [~560cy] → data PF fill
    current iteration: demand index load → L1 HIT       demand data load → L1 HIT
    ```
- 标注 PRB 的角色：分配时机（IPU 发 index PF 时）、快照 tt_idx[]、sector tracking、释放时机（all sectors filled）
- 用真实 cycle 数据（BFS small_1sm_cta5 p50: index_issue_to_refill ≈ 560cy）

**参考风格**：自创（DMP 无两步 pipeline；closest 是 Snake Fig 15 training/prefetching example）
**颜色**：蓝 = index path, 橙 = data path, 灰 = demand-only baseline

**待确定**：
- [ ] 是否展示 RFAIL 场景（sector 被放弃时 pipeline 如何 degrade）
- [ ] cycle 数据用 BFS 还是 geomean 代表值

---

### Fig F — Throttle Control Cooldown 机制

**目的**：展示 TC 如何通过 cooldown timer 抑制无效 data PF

**内容**：
- MSHR 占用率时间线（x 轴 = cycles, y 轴 = MSHR occupancy %）
- 水平虚线标注 threshold = 40%
- 标注事件序列：
  1. MSHR 占用率超过 40% → 触发 cooldown
  2. Cooldown 期间（200 cycles）：DATA_PF 被 suppress（用红色叉标注）
  3. INDEX_PF 始终豁免（蓝色箭头仍在发射）
  4. Cooldown 结束 → DATA_PF 恢复
- 下方小框：效果指标（useless PFs 减少 25-61%, SpMV +3.47%）

**参考风格**：类似 CAPS 的 throttling 示意图
**尺寸**：3.5" 单栏

**待确定**：
- [ ] 是否展示多次 cooldown 触发（连续波形）还是单次
- [ ] 是否标注 "为什么 INDEX_PF 豁免"（因为 index PF 是 data PF 的前置依赖）

---

### Fig G — Worked Example：BFS 端到端生命周期

**目的**：用一个具体 BFS iteration 串联所有组件，reader 可在纸上 trace 全流程

**内容**：
- 用 BFS 的实际 SASS（`.L_x_20` 展开 ×4 的 copy 1）
- 时间线从左到右，6 个阶段：

  (a) **SASS 代码片段**（3 行）
  ```
  PC 0x0640: LDG.E R5, [R24]           // index load: column_indices[offset]
  PC 0x0670: IMAD.WIDE R2, R5, R11, c[0x0][0x178]  // addr compute
  PC 0x0690: LDG.E R3, [R2]            // data load: dists[col_idx]
  ```

  (b) **CD 检测**
  - FIFO: push {R5, LOAD_RESULT, PC=0x0640}
  - IMAD.WIDE: lookup R5 → match → push {R2, IMA_ADDR_COMPUTE, index_PC=0x0640}
  - LDG R3: lookup R2 → match IMA_ADDR_COMPUTE → **chain confirmed**

  (c) **CT/TT 写入**
  - CT[0x0640] = {data_PC=0x0690, tt_idx=[0], num_targets=1}
  - TT[0] = (c[0x0][0x178], scale=4)

  (d) **Stride learning**
  - Warp 0 第 2 次执行 PC 0x0640: addr=0x1040 (prev=0x1030)
  - iter_stride = 0x1040 - 0x1030 = 16 (×4 展开 × 4B element)
  - stride_valid = true

  (e) **IPU → PRB → Index PF**
  - Warp 1 执行 PC 0x0640, addr=0x2080
  - IPU: prefetch addr = 0x2080 + 16 = 0x2090
  - PRB alloc: {tt_idx=[0], num_targets=1, remaining_sectors=1}
  - L1 request: INDEX_PF @ sector 0x2090

  (f) **DPU → Data PF → Hit**
  - Index PF fill: sector data 返回, value = 0x00001A3F (col_idx)
  - DPU: data_addr = 0x178_base + 0x1A3F × 4 = 0x...
  - Data PF issued → L1 fill
  - Warp 1 later: demand LDG dists[0x1A3F] → **L1 HIT**

**参考风格**：DMP Fig 4（BFS 五子图复合）+ F-1（全部用真实 hex 值）
**颜色**：蓝=index, 橙=data, 绿=IMAD.WIDE, 灰=FIFO 操作

**待确定**：
- [ ] 实际 hex 值需要从 BFS trace 中提取真实数据
- [ ] 6 个阶段排列方式：水平时间线 vs 垂直瀑布流
- [ ] 是否标注失败路径（如 RFAIL 时怎样）

---

## 三、颜色系统（全文统一）

来源：`writing_rules/figure_design.md` F-2

| 概念 | 颜色 | CB10 索引 | 用途 |
|------|------|----------|------|
| Index load/prefetch | 蓝 | CB10[0] | CD 的 index LDG、IST、IPU |
| Data load/prefetch | 橙 | CB10[1] | CT/TT、DPU |
| IMAD.WIDE | 绿 | CB10[2] | CD 中的地址计算 |
| Demand/Baseline | 灰 | CB10[7] | 对比基准、非 tracked 指令 |
| GRASP (our work) | 红 | CB10[3] | 性能图中 GRASP 方案 |

箭头样式：
- 实线 = 数据流
- 虚线 = 控制信号/触发
- 粗箭头 = 主数据通路
- 细箭头 = 辅助/反馈

---

## 四、开放问题（待逐图讨论时敲定）

1. Fig A: TC 在架构图中如何表示
2. Fig B: training 和 prefetch 是否合并到一张 flowchart
3. Fig C: 展示几个 warp、FIFO invalidation 的详细程度
4. Fig D: 单栏 vs 双栏、SpMV 归并和 BC one-to-many 是否拆成子图
5. Fig E: RFAIL 场景是否展示、cycle 数据来源
6. Fig F: 单次 vs 多次 cooldown 触发
7. Fig G: 排列方式（水平 vs 垂直）、实际 hex 值需从 trace 提取
8. 全局：7 张图在 3.5 页中的具体版面排布

---

## 五、参考资料

- 架构源: `ima_plan/04_prefetcher_design.md` §3-§4
- 代码: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_*.{h,cc}`
- 写作规则: `ima_plan/07_paper_outline/writing_rules/§3_design.md` (D-1 ~ D-13)
- 图表规则: `ima_plan/07_paper_outline/writing_rules/figure_design.md` (F-1 ~ F-15)
- DMP 参考: `ima_plan/02_related_work/ima_hw/Fu et al. 2024` Fig 4-10
- 实验数据: `ima_plan/04_prefetcher_design/extra_pattern/small_1sm_cta5/` (cycle 数据)
- TC DSE: `ima_plan/05_implementation/dse_throttle_control/README.md` §7
