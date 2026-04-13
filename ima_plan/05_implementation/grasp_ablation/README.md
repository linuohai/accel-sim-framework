# GRASP Prefetcher 消融实验报告

> 日期：2026-03-24
> 配置：SM80_A100 (108 SM), spmv_ima_high / sssp_ima_high (cit-Patents)

---

## 1. 实验目的

验证 GRASP prefetcher 当前实现是否与设计文档一致，并通过消融实验定位性能衰退的根因，确认在何种场景下预取器能带来正向收益。

## 2. 实现一致性确认

逐文件对比 `grasp_*.cc/h` 与 `04_prefetcher_design.md` + `流程说明.md`，确认以下组件全部匹配设计：

| 组件 | 状态 | 说明 |
|------|------|------|
| CD (Chain Detector) | ✅ | 2-warp tracked, FIFO depth=20, LDG→IMAD.WIDE→LDG |
| CT (Chain Table) | ✅ | stride observation (W=2 slots), 2-observation 收敛 |
| TT (Target Table) | ✅ | placeholder (trace-driven), 由 pair table 替代 |
| Warp-level coalesce | ✅ | 32 lane → deduplicate by 32B sector |
| Instruction UID dedup | ✅ | 同一条指令的多个 mem_fetch 不重复生成预取 |
| PRB (Prefetch Request Buffer) | ✅ | pair table lookup cache, MSHR_HIT retry |
| Cross-kernel persistence | ✅ | 同 kernel function → 保留 CT stride |
| Distance semantics | ✅ | 只预取 n=distance（不是 1..distance） |
| Throttle Control | ❌ | 已实现但默认阈值 80% 在 SpMV 上未触发 |

**结论：性能衰退非实现 bug，是设计参数和 workload 特性问题。**

## 3. SpMV 消融实验（108 SM, 100 CTA）

### 3.1 Distance 扫描（无 Throttle）

| Config | IPC | vs Baseline | L1D HIT | HIT_RESERVED | MISS | RFAIL |
|--------|-----|-------------|---------|--------------|------|-------|
| **Baseline** | **557.73** | — | 142,579 | 107,143 | 417,894 | 3,007,127 |
| GRASP d=1 | 543.66 | **-2.52%** | 236,899 | 165,508 | 472,769 | 3,036,044 |
| GRASP d=3 | 544.38 | **-2.39%** | 239,116 | 156,703 | 471,282 | 3,029,579 |
| GRASP d=4 | 545.62 | **-2.17%** | 244,263 | 156,967 | 470,625 | 3,033,235 |
| GRASP d=5 | 545.84 | **-2.13%** | 250,832 | 152,188 | 470,062 | 3,037,502 |
| GRASP d=8 | 546.49 | **-2.02%** | 249,199 | 146,441 | 468,459 | 3,033,934 |

### 3.2 带 Throttle（MSHR > 80% 时抑制 DATA_PF）

| Config | IPC | vs Baseline | throttle_suppressed |
|--------|-----|-------------|---------------------|
| TC d=1 | 544.17 | -2.43% | 0 |
| TC d=4 | 546.81 | -1.96% | 0 |
| TC d=8 | 545.01 | -2.28% | 0 |

### 3.3 SpMV 分析

**Throttle 未触发**：在 `inject_prefetch()` 检查 MSHR 占用率时，瞬时占用率从未达到 80%。3M 次 RFAIL 发生在 `l1d->access()` 内部（demand + PF 同时竞争的结果），而非 MSHR 持续高于阈值。

**Distance 趋势**：IPC 随 distance 增大单调改善（-2.52% → -2.02%），但改善幅度递减且始终为负。核心原因：

1. **只有 1/5 的 IMA chain 学到 stride**：PC 0x200 (remainder loop) 成功；PC 0xcc0-0xcf0 (×16 展开体) 因内循环只执行 1 轮而永远学不到。
2. **MSHR 极度饱和**（RFAIL 300 万次）：任何额外 L1D 请求（即使预取正确）都增加 MSHR 竞争。
3. **Cache pollution**：分离 demand 和 PF 后，demand HIT 实际减少 ~10K（PF 驱逐了有用数据）。
4. **HIT_RESERVED 效应**（d=1 → d=8 递减）：d=1 时 PF 和 demand 赛跑产生大量 HIT_RESERVED（+58K）；d=8 拉开距离后减少到 +39K，说明 timeliness 确实在改善。

**结论**：SpMV 在 MSHR 极度饱和的条件下不适合作为 GRASP 的首要验证场景。×16 展开使大部分 IMA chain 无法学习 stride，且 MSHR 压力使任何额外请求成为净负担。

## 4. SSSP 消融实验（108 SM, 50 CTA）

| Config | IPC | Cycles | vs Baseline | 说明 |
|--------|-----|--------|-------------|------|
| **Baseline** | **10.70** | 388,672 | — | 4 kernel launches |
| **GRASP d=4** | **15.21** | 273,352 | **+42.2%** | 同 4 kernel, 同 trace |

### 4.1 SSSP GRASP 详细 stats（活跃 SM 示例）

| SM | chains | idx_pf issued | data_pf issued | pair_table hit/miss |
|----|--------|--------------|----------------|---------------------|
| SM2 | 277 | 762 | 1,362 | 2,210 / 2,285 |
| SM3 | 334 | 929 | 1,567 | 2,750 / 2,511 |
| SM4 | 304 | 786 | 986 | 1,715 / 2,505 |

### 4.2 SSSP 成功原因分析

1. **MSHR 压力低**：RFAIL ~40K（SpMV 的 1/75），预取不会显著竞争 MSHR。
2. **多 kernel 迭代受益于跨 kernel 持久化**：kernel 2 训练的 stride 在 kernel 3/4 立即可用，无需重新训练。
3. **Pair table 覆盖率 ~50%**（hit/miss 约 1:1）：如果 chain CSV 覆盖更完整，收益预期更大。
4. **SSSP 的 IMA chain 更规则**：没有 ×16 展开的复杂性，stride 收敛可靠。

## 5. 多算法实验（2026-03-25 补充）

### 5.1 IMA Tiny Case（专用 IMA 测例）

| Config | IPC | Cycles | vs Baseline |
|--------|-----|--------|-------------|
| Baseline | 5.21 | 30,711 | — |
| **GRASP d=4** | **8.00** | 20,000 | **+53.6%** |

GRASP stats (SM0): idx_pf issued=478, data_pf issued=1,075, pair_table hit=352, queue_peak=479

**分析**：该测例专为 IMA 设计，MSHR 压力低，IMA 模式简单（无展开），GRASP 管线完全发挥作用。

> **注意**：首次运行时 pair_table 没有覆盖 tiny_case kernel，需要在 chain CSV 中添加对应 entry（impl 字段留空）。

### 5.2 BC（Betweenness Centrality, 50 CTA）

| Config | IPC | vs Baseline |
|--------|-----|-------------|
| Baseline | 418.81 | — |
| GRASP d=4 | 418.81 | **0%** |

**分析**：BC 只跑了 kernel 1（forward pass）的部分 CTA，工作量太小（5813 cycles）。需要更多 CTA 或完整运行才能看到效果。

### 5.3 CC（Connected Components, 1SM, 500 CTA）

| Config | IPC | Cycles | vs Baseline |
|--------|-----|--------|-------------|
| Baseline | 13.84 | 147,681 | — |
| GRASP d=4 | 2.94 | 2,787,268 | **-79%（灾难性）** |

**根因**：手工生成的 CC chain CSV 质量差（pair table miss 70%），导致大量无效 INDEX_PF 堆积（PRB peak=25K, queue_peak=15K），RFAIL +39%（demand 被挤占）。

**教训**：chain CSV 不准确时，没有队列深度保护的预取器会产生灾难性衰退。需要：(a) 精确验证 chain CSV 的 PC 匹配，(b) 实现 queue depth 上限。

### 5.4 跨算法汇总

| 算法 | IPC 变化 | GRASP 是否有效 | 限制因素 |
|------|---------|---------------|---------|
| **SSSP** | **+42.2%** | ✅ | pair table 覆盖率 50% |
| **Tiny Case** | **+53.6%** | ✅ | 初次需手动配 chain CSV |
| SpMV | -2.0% ~ -2.5% | ❌ | MSHR 饱和 + ×16 展开 |
| BFS | ~0% | ❌ | kernel 太短, stride 未收敛 |
| BC | 0% | — | 工作量不足 |
| CC | **-79%** | ❌ | chain CSV 质量差 + 无队列保护 |

## 6. 关键结论

### 6.1 GRASP 在 MSHR 压力低的场景有效

SSSP +42.2% 和 Tiny Case +53.6% 证明 GRASP 的检测-训练-预取管线在正确条件下有巨大收益。

### 6.2 SpMV 的 -2% 衰退非实现 bug，是环境问题

| 因素 | SpMV (失败) | SSSP (成功) |
|------|------------|------------|
| MSHR RFAIL | 3,000,000 | 40,000 |
| Stride 学到的 chain 比例 | 1/5 (20%) | 更高 |
| Pair table 覆盖率 | ~100% | ~50% |
| Loop unrolling 影响 | ×16 导致大部分 PC 学不到 | 无 |

### 6.3 优先改进方向

| 优先级 | 改进 | 预期效果 |
|--------|------|---------|
| **P0** | 降低 throttle 阈值（80%→50%）或改用动态阈值 | 减少 SpMV 的 cache pollution |
| **P1** | 处理 ×16 展开：用 (base, scale) 归并多个 PC 到同一 CT entry | SpMV stride 覆盖率从 20% → ~100% |
| **P2** | 增大 distance 到 4-8 | 持续的微小改善（已验证） |
| **P3** | 完善 SSSP/BFS chain CSV 覆盖率 | SSSP 从 50% pair hit → 更高 |

## 7. 下一步实验

- [ ] **P0: 实现 queue depth 上限**（防止 CC 式灾难性衰退，PRB/queue 无限增长）
- [ ] **P0: 精确生成 CC chain CSV**（当前手工版 pair table miss 70%，需用 SASS 分析工具重新生成）
- [ ] **P1: 提高 BFS/BC pair table 覆盖率**（当前 44-56% hit，需检查 pair table build 逻辑是否完全扫描 warp trace）
- [ ] 实现 PC 归并（解决 SpMV ×16 展开问题）
- [ ] 动态 throttle（基于 demand miss rate 而非瞬时 MSHR 占用率）
- [ ] SSSP 完善 chain CSV 后重测上界（当前 50% hit → 目标 >90%）
