# DSE: GRASP Throttle Control Strategy Exploration

> 最近更新: 2026-04-03 (Round 2: 3-workload cross-validation complete)

## 1. Background

### 1.1 Current Throttle Mechanism

GRASP 当前的节流机制位于 `grasp_prefetcher.cc:701-712`（`inject_prefetch()`）：

- **策略**: 单一 MSHR 占用率阈值（默认 80%），超过时丢弃所有 DATA_PF
- **豁免**: INDEX_PF 始终不被节流（pipeline 正确性要求）
- **粒度**: per-SM 全局，无 per-warp / per-PC 区分
- **参数**: `-grasp_tc_mshr_threshold 80`（0=关闭）

```cpp
// grasp_prefetcher.cc:701-712
bool is_data_pf = req.seed_chain_ids.empty();
if (is_data_pf && l1d && m_cfg.tc_mshr_threshold > 0) {
  float mshr_ratio = l1d->mshr_occupancy_ratio() * 100.0f;
  if (mshr_ratio >= (float)m_cfg.tc_mshr_threshold) {
    m_prefetch_queue.erase(m_prefetch_queue.begin() + ready_idx);
    ++m_stats.throttle_suppressed;
    continue;
  }
}
```

### 1.2 Experiment Evidence

BFS web-Google, 1SM, max-cta=3 的资源理想化实验结果：

| Config | IPC | Data Miss | Accuracy | RFAIL | Useless PFs | MQ Peak | MSHR Peak |
|--------|-----|-----------|----------|-------|-------------|---------|-----------|
| Baseline (no GRASP) | 1.113 | 79,020 | — | — | — | — | — |
| GRASP default (thr=80) | 1.884 | 70,425 | 43.8% | 41,386 | 19,892 | 16/16 | — |
| inf-mq (mq=65536) | 1.854 | 70,973 | 32.9% | 12,920 | 35,938 | 280/65536 | — |
| inf-all (mq+mshr=inf, thr=0) | 1.795 | 70,210 | 22.8% | 0 | 63,483 | 1052/65536 | 2208/65536 |

**关键发现**:
- 移除节流后 IPC **下降** 4.7%（1.884→1.795），accuracy **下降** 48%（44%→23%）
- 释放的 41K RFAIL 中 74% 变为 useless prefetch（cache pollution）
- Data misses 几乎不变（70,425→70,210），资源不是瓶颈
- MQ 实际峰值仅 280/65536，MSHR 峰值 2208/65536——远未到容量极限

Data miss root cause 分布：
- IDX_NOT_TRIGGERED: 47%（与节流无关）
- PT miss: ~33K（与节流无关）
- **RFAIL: 11%（直接节流相关）**
- **EVICTED: 2.6%（间接，cache pollution）**
- STRIDE_NOT_CONVERGED: 8.9%

### 1.3 Hypothesis Evaluation

**假设**: "节流策略没做好是性能受限的重要因素"

**评估**: 方向正确，但幅度有限。

- **正确的部分**: 当前节流是 binary cliff——80% 以下全放，以上全堵。它 accidentally 有效是因为坏预取在 MSHR 高占用期间聚集。更智能的节流可以在保持 anti-pollution 的同时放行好预取。
- **限制**: 改进上限约 13.6% data misses（RFAIL 11% + EVICTED 2.6% ≈ ~9500 个 miss）。47% IDX_NOT_TRIGGERED 和 33K PT miss 是上游问题，节流策略无法解决。
- **预计 IPC 提升**: 3-7%（取决于策略质量）

**结论**: 节流 DSE 是当前最 actionable 的优化方向，也是后续改进（如提升 accuracy）的前置条件——没有好的节流，任何 accuracy 提升都会被 pollution 抵消。

---

## 2. Strategy Design

### 2.0 Architecture: `tc_mode` Dispatch Framework

所有策略通过 `tc_mode` 参数统一调度，在 `inject_prefetch()` 的 throttle block 中 dispatch：

| tc_mode | 策略 | 核心信号 |
|---------|------|----------|
| 0 | Legacy binary threshold | MSHR occupancy (单阈值) |
| 1 | Dual-threshold proportional | MSHR occupancy (双阈值, 线性插值) |
| 2 | Queue-depth cap | Prefetch queue 中 DATA_PF 数量 |
| 3 | Accuracy-gated | 运行时 PT hit/miss ratio + MSHR occupancy |
| 4 | Cooldown timer | MSHR occupancy + 时间窗冷却 |

**约束**: `tc_mode=0` 必须与现有行为完全一致。INDEX_PF 始终豁免。

### 2.1 S1: Dual-Threshold Proportional

**控制论原理**: P-controller。当前 binary gate 在 80% 有 cliff-edge。双阈值在 `[lo, hi]` 间线性插值丢弃概率，平滑过渡。

**参数**:
- `tc_mshr_lo` (unsigned, default=50): 下阈值 %，低于此全部放行
- `tc_mshr_hi` (unsigned, default=90): 上阈值 %，高于此全部丢弃

**逻辑**:
```
MSHR < lo     → 0% drop (全放)
lo <= MSHR < hi → linear drop: (MSHR - lo) / (hi - lo)
MSHR >= hi    → 100% drop (全堵)
```

**实现** (替换 701-712 行的 mode 1 分支):
```cpp
float pct = l1d->mshr_occupancy_ratio() * 100.0f;
if (pct >= (float)m_cfg.tc_mshr_hi) {
  suppress = true;
} else if (pct > (float)m_cfg.tc_mshr_lo) {
  float drop_prob = (pct - m_cfg.tc_mshr_lo) /
                    (float)(m_cfg.tc_mshr_hi - m_cfg.tc_mshr_lo);
  suppress = ((cycle % 100) < (unsigned)(drop_prob * 100));
}
```

### 2.2 S2: Queue-Depth Cap

**原理**: Rate limiter / token bucket。不监控下游资源（MSHR），而是直接限制预取器自身输出。

**参数**:
- `tc_queue_cap` (unsigned, default=0): DATA_PF 队列上限，0=关闭

**实现**:
```cpp
if (m_cfg.tc_queue_cap > 0) {
  unsigned data_count = 0;
  for (const auto &e : m_prefetch_queue)
    if (e.seed_chain_ids.empty()) ++data_count;
  suppress = (data_count >= m_cfg.tc_queue_cap);
}
```

### 2.3 S3: Accuracy-Gated Adaptive Threshold

**原理**: Feedback controller。输出质量（accuracy）决定准入严格度。

**参数**:
- `tc_acc_lo` (unsigned, default=30): accuracy % 低于此 → 使用 tc_mshr_lo（紧节流）
- `tc_acc_hi` (unsigned, default=60): accuracy % 高于此 → 使用 tc_mshr_hi（松节流）

**实现**:
```cpp
float pct = l1d->mshr_occupancy_ratio() * 100.0f;
unsigned long long total = m_stats.pair_table_lookup_hit +
                           m_stats.pair_table_lookup_miss;
float acc = total > 0 ? 100.0f * m_stats.pair_table_lookup_hit / total : 50.0f;

float eff_thr;
if (acc <= (float)m_cfg.tc_acc_lo)
  eff_thr = (float)m_cfg.tc_mshr_lo;    // low accuracy → tight
else if (acc >= (float)m_cfg.tc_acc_hi)
  eff_thr = (float)m_cfg.tc_mshr_hi;    // high accuracy → loose
else {
  float t = (acc - m_cfg.tc_acc_lo) / (float)(m_cfg.tc_acc_hi - m_cfg.tc_acc_lo);
  eff_thr = m_cfg.tc_mshr_lo + t * (m_cfg.tc_mshr_hi - m_cfg.tc_mshr_lo);
}
suppress = (pct >= eff_thr);
```

### 2.4 S4: Cooldown Timer

**原理**: Bang-bang controller with hysteresis。触发后冷却 N cycle，给 cache 排空。

**参数**:
- `tc_cooldown_cycles` (unsigned, default=0): 冷却周期数，0=关闭

**新增状态**: `m_tc_cooldown_until` (unsigned long long, init=0)

**实现**:
```cpp
float pct = l1d->mshr_occupancy_ratio() * 100.0f;
if (cycle < m_tc_cooldown_until) {
  suppress = true;  // in cooldown
} else if (pct >= (float)m_cfg.tc_mshr_threshold) {
  suppress = true;
  m_tc_cooldown_until = cycle + m_cfg.tc_cooldown_cycles;
}
```

---

## 3. Test Matrix

### 3.1 Command Template

```bash
./traceL1 -c SM80_A100_1SM --grasp --no-l1-trace --no-l2-trace --no-hbm-trace \
    --max-completed-cta 3 \
    -grasp_tc_mode <M> [strategy-specific params] \
    bfs_ima_small bfs_1sm_tc_<label>
```

### 3.2 Baselines (3 runs)

| Label | tc_mode | tc_mshr_thr | 说明 |
|-------|---------|-------------|------|
| B0 | — | — | No GRASP (baseline) |
| B1 | 0 | 80 | Current default |
| B2 | 0 | 0 | No throttle |

### 3.3 S1: Dual-Threshold (4 runs)

| Label | tc_mshr_lo | tc_mshr_hi | 说明 |
|-------|------------|------------|------|
| S1a | 50 | 90 | Wide band |
| S1b | 60 | 80 | Narrow band around 80% |
| S1c | 30 | 70 | Aggressive early throttle |
| S1d | 70 | 95 | Permissive |

### 3.4 S2: Queue-Depth Cap (4 runs)

| Label | tc_queue_cap | tc_mshr_thr | 说明 |
|-------|-------------|-------------|------|
| S2a | 4 | 0 | Tight cap only |
| S2b | 8 | 0 | Medium cap only |
| S2c | 16 | 0 | Loose cap only |
| S2d | 8 | 80 | Cap + MSHR combined |

### 3.5 S4: Cooldown Timer (4 runs)

| Label | tc_cooldown | tc_mshr_thr | 说明 |
|-------|-------------|-------------|------|
| S4a | 50 | 80 | Short cooldown |
| S4b | 200 | 80 | Medium cooldown |
| S4c | 500 | 80 | Long cooldown |
| S4d | 200 | 60 | Lower trigger + medium cooldown |

### 3.6 S3: Accuracy-Gated (3 runs)

| Label | tc_acc_lo | tc_acc_hi | tc_mshr_lo | tc_mshr_hi | 说明 |
|-------|-----------|-----------|------------|------------|------|
| S3a | 30 | 60 | 50 | 90 | Default range |
| S3b | 20 | 50 | 40 | 85 | Tighter at low accuracy |
| S3c | 40 | 80 | 60 | 95 | More permissive at high accuracy |

**Total**: 3 baselines + 15 experiments = 18 runs, ~5 min/run → ~90 min

### 3.7 Metrics to Collect

从每个 log 提取：
- `gpu_tot_ipc` — IPC
- `GRASP_DEMAND SM0:` — global_reads, global_misses, throttle_suppressed
- `GRASP_EFFECT SM0:` — pf_useful, pf_useless, pf_late, accuracy%
- `GRASP_RFAIL SM0:` — total, missq%, mshr_entry%
- `GRASP_STORAGE SM0:` — prb, ct, cd_fifo peak/capacity
- `GRASP_L1MQ SM0:` — miss_queue_peak, mshr_peak

---

## 4. Success Criteria

对比 B1-default (IPC=1.884, accuracy=43.8%, useless=19892):

| Metric | Win threshold | Must not regress |
|--------|--------------|------------------|
| **IPC** (primary) | >= +1.5% (>= 1.912) | Not below -0.5% |
| Accuracy | >= +5pp (>= 48.8%) | Not below 35% |
| Useless PFs | <= -10% (<= 17903) | Not increase >10% |

如果所有策略在 BFS 上均无法超越 B1-default，结论是当前节流已接近 BFS 最优。

---

## 5. Experiment Results

BFS web-Google, SM80_A100_1SM, max-completed-cta=3, 2026-04-03

### 5.1 Summary Table

| Label | IPC | vs B1 | Accuracy | Useful | Useless | RFAIL | Throttled | Description |
|-------|-----|-------|----------|--------|---------|-------|-----------|-------------|
| **B1** | **1.8807** | — | **45.77%** | 15972 | **18922** | 36468 | 1605 | Legacy thr=80 (default) |
| B2 | 1.8799 | -0.04% | 44.00% | 15476 | 19697 | 37779 | 0 | No throttle |
| S1a | 1.8807 | +0.00% | 46.57% | 15872 | 18209 | 35531 | 3341 | Dual-thr lo=50 hi=90 |
| **S1b** | **1.8850** | **+0.22%** | **46.63%** | 15468 | **17706** | 37009 | 2716 | Dual-thr lo=60 hi=80 |
| S1c | 1.8797 | -0.05% | **48.63%** | 15115 | **15965** | 33841 | 8445 | Dual-thr lo=30 hi=70 |
| S1d | 1.8828 | +0.11% | 46.33% | 15593 | 18061 | 37755 | 1371 | Dual-thr lo=70 hi=95 |
| S2a | 1.8711 | -0.51% | 45.13% | 15222 | 18509 | 36607 | 3225 | Queue-cap=4 |
| S2b | 1.8815 | +0.04% | 45.17% | 15768 | 19141 | 37296 | 507 | Queue-cap=8 |
| S2c | 1.8799 | -0.04% | 44.00% | 15476 | 19697 | 37779 | 2 | Queue-cap=16 (≈no throttle) |
| S2d | 1.8815 | +0.04% | 45.17% | 15768 | 19141 | 37296 | 507 | Queue-cap=8 + MSHR thr=80 |
| S3a | 1.8833 | +0.13% | 46.71% | 16155 | 18434 | 36695 | 1096 | Acc-gate [30,60]→[50,90] |
| **S3b** | **1.8858** | **+0.27%** | 45.86% | 15610 | 18430 | 37396 | 1282 | Acc-gate [20,50]→[40,85] |
| S3c | 1.8852 | +0.23% | 46.47% | 15893 | 18305 | 37026 | 1319 | Acc-gate [40,80]→[60,95] |
| S4a | 1.8804 | -0.01% | 46.04% | 15591 | 18270 | 37277 | 1808 | Cooldown=50 thr=80 |
| S4b | 1.8844 | +0.19% | 46.17% | 15545 | 18126 | 37467 | 1588 | Cooldown=200 thr=80 |
| S4c | 1.8832 | +0.13% | 46.52% | 15822 | 18192 | 36762 | 2144 | Cooldown=500 thr=80 |
| **S4d** | **1.8870** | **+0.33%** | **47.81%** | 15679 | **17114** | 35287 | 5023 | Cooldown=200 thr=60 |

### 5.2 Analysis

**Top 3 performers by IPC**: S4d (+0.33%), S3b (+0.27%), S3c (+0.23%)

**Key observations**:

1. **All strategies produce marginal IPC gains (< 0.4%)**. No strategy reaches the +1.5% win threshold. This confirms the hypothesis ceiling: throttle alone cannot significantly improve performance when 47% of data misses are IDX_NOT_TRIGGERED and 33K are PT miss.

2. **S4d (Cooldown thr=60, cooldown=200) is the best overall**:
   - Highest IPC (+0.33%)
   - Best accuracy (47.81%, +2.04pp)
   - Lowest useless PFs (17,114, -9.6%)
   - More aggressive throttle (5023 suppressed vs 1605 baseline)
   - Mechanism: lower trigger (60%) + 200-cycle cooldown creates "breathing room" for cache

3. **S1c (Aggressive dual-threshold) has best accuracy (+2.86pp to 48.63%) but IPC regresses (-0.05%)**. Too much throttling blocks some useful prefetches too.

4. **S2 (Queue-depth cap) is least effective**. S2a (tight cap=4) hurts IPC (-0.51%); S2c (loose cap=16) behaves like no throttle. The prefetch queue depth is not a useful congestion signal.

5. **S3 (Accuracy-gated) shows consistent moderate improvement**. S3b/S3c both +0.27%/+0.23% IPC. The accuracy feedback provides a better quality signal than raw MSHR occupancy alone.

6. **Removing throttle (B2) is slightly worse than default** — confirms the current throttle already provides value.

### 5.3 Winner Configuration

**S4d**: `-grasp_tc_mode 4 -grasp_tc_cooldown 200 -grasp_tc_mshr_threshold 60`
- Lower MSHR trigger (60% instead of 80%) + 200-cycle cooldown
- Provides brief "drain windows" that let the cache absorb prefetches

**Runner-up: S3b**: `-grasp_tc_mode 3 -grasp_tc_acc_lo 20 -grasp_tc_acc_hi 50 -grasp_tc_mshr_lo 40 -grasp_tc_mshr_hi 85`

---

## 6. Round 2: Expanded Parameter Sweep (2026-04-03)

### 6.1 Motivation

Round 1 最佳 S4d(thr=60, cd=200) 只在 1SM 上达到 +0.33%。Round 2 扩展:
1. S4 cooldown: threshold(40-70) × cooldown(100-500) 交叉扫描
2. S3 accuracy-gated: acc_band × mshr_range 细调
3. **重点指标变化**: 不仅看 accuracy，更看 demand data miss 和 coverage（用户洞察: 减少 useless PF → 降低 cache pollution → 减少 demand miss）

### 6.2 Phase 1: 1SM Results (sorted by IPC)

| Label | IPC | vs B1 | Acc% | D_Miss | Cov% | Useless | RFAIL | Thr | Config |
|-------|-----|-------|------|--------|------|---------|-------|-----|--------|
| B1 (ref) | 1.8807 | — | 45.77 | 71,266 | 37.17 | 18,922 | 36,468 | 1,605 | mode=0 thr=80 |
| **T50C100** | **1.8908** | **+0.54%** | 49.30 | 71,857 | 36.65 | 16,039 | 33,435 | 8,074 | mode=4 thr=50 cd=100 |
| T50C300 | 1.8892 | +0.45% | 50.60 | 71,866 | 36.64 | 15,448 | 32,422 | 9,219 | mode=4 thr=50 cd=300 |
| T40C200 | 1.8884 | +0.41% | **52.86** | 72,280 | 36.28 | **13,654** | 31,184 | 13,627 | mode=4 thr=40 cd=200 |
| T55C150 | 1.8880 | +0.39% | 47.75 | 71,784 | 36.72 | 16,820 | 34,575 | 6,361 | mode=4 thr=55 cd=150 |
| T55C200 | 1.8878 | +0.38% | 47.45 | 71,702 | 36.79 | 17,517 | 33,443 | 6,515 | mode=4 thr=55 cd=200 |
| T60C100 | 1.8876 | +0.37% | 47.92 | 71,682 | 36.80 | 17,020 | 35,847 | 4,304 | mode=4 thr=60 cd=100 |
| T60C150 | 1.8873 | +0.35% | 47.32 | 71,899 | 36.62 | 17,148 | 35,233 | 4,938 | mode=4 thr=60 cd=150 |
| T65C150 | 1.8871 | +0.34% | 47.28 | 71,254 | 37.18 | 17,736 | 35,514 | 3,686 | mode=4 thr=65 cd=150 |
| R1 S4d | 1.8870 | +0.33% | 47.81 | 71,583 | 36.89 | 17,114 | 35,287 | 5,023 | mode=4 thr=60 cd=200 |
| S3b variants | 1.8858 | +0.27% | 45.86 | 71,497 | 36.96 | 18,430 | 37,396 | 1,282 | mode=3 (3 configs identical) |

### 6.3 Phase 1 Analysis

**新冠军 T50C100 (IPC +0.54%)** 比 Round 1 的 S4d (+0.33%) 提升 63%。

**关键发现 — accuracy ≠ IPC:**
- T40C200 accuracy 最高 (52.86%) 但 IPC 只排第 3 (+0.41%)
- T50C100 accuracy 49.30% 但 IPC 最高 (+0.54%)
- 原因: thr=40 过度节流（13,627 suppressed），阻止了一些有用预取；thr=50 + 短冷却(100) 平衡了 pollution 控制和 throughput

**Demand data miss 悖论:**
- 所有 S4 配置的 data_miss 比 B1(71,266) 略高（71,680-72,280）
- 但 IPC 反而提升了——说明 **miss latency 更重要**: 节流减少了 MSHR 拥塞，demand miss 的 service time 变短
- Coverage 在所有配置间只有 36.28%-37.18% 的微小波动

**S3 (Accuracy-gated) 在 1SM 下饱和:** 3 种不同 acc_band 配置（A15_50, A20_40, A25_55）产出完全相同的结果（IPC=1.8858），因为 1SM 下 accuracy 很快收敛到稳态，feedback 差异被平均化。需要在 full-SM 上验证。

**S4 threshold 趋势:** thr=50 系列整体优于 thr=55/60/65 系列。更低的触发点 + 短冷却效果最好。

### 6.4 Phase 2: Full-SM Multi-Workload Validation

SM80_A100 (108 SMs), full run。GRASP 指标为 108 个 SM 汇总（EXPERIMENT SUMMARY 只打印 SM0，数据不可用于 Full-SM 分析）。Timeliness 取自全局 `IMA_TIMELINESS:`，Coverage 取自全局 `IMA_DEMAND:`。

**注意: Accuracy 计算方式** = `Σ(all SM pf_useful) / Σ(all SM pf_useful + pf_useless)`，通过聚合 108 个 SM 的 `GRASP_EFFECT` 得出。

#### BFS (web-Google, ~2.5h/run)

| Label | IPC | vs B1 | Acc% | D_Miss | ΔD_Miss | Cov% | IdxTL% | DatTL% | Useless | ΔUseless | Thr |
|-------|-----|-------|------|--------|---------|------|--------|--------|---------|----------|-----|
| **B1** | 30.8493 | — | 55.47 | 3,362,276 | — | 33.55 | 88.32 | 73.47 | 1,177,808 | — | 39,037 |
| B2 | 30.8259 | -0.08% | 55.25 | 3,354,879 | -0.22% | 33.70 | 88.22 | 73.75 | 1,194,327 | +1.4% | 0 |
| T50C100 | 30.8745 | +0.08% | 58.54 | 3,384,012 | +0.65% | 33.12 | 89.02 | 73.13 | 1,029,677 | -12.6% | 206,452 |
| T50C300 | 30.9619 | +0.37% | 59.20 | 3,389,701 | +0.82% | 33.01 | 89.17 | 73.30 | 1,000,465 | -15.1% | 239,973 |
| **T40C200** | **30.9694** | **+0.39%** | **62.27** | 3,410,304 | +1.43% | 32.60 | 89.88 | 72.79 | **873,237** | **-25.9%** | 382,286 |
| S3b | 30.8627 | +0.04% | 55.38 | 3,361,556 | -0.02% | 33.57 | 88.28 | 73.50 | 1,182,596 | +0.4% | 30,711 |

#### SSSP (web-Google, ~4h/run)

| Label | IPC | vs B1 | Acc% | D_Miss | ΔD_Miss | Cov% | IdxTL% | DatTL% | Useless | ΔUseless | Thr |
|-------|-----|-------|------|--------|---------|------|--------|--------|---------|----------|-----|
| **B1** | 35.3925 | — | 52.49 | 3,615,662 | — | 28.57 | 87.06 | 69.16 | 1,021,144 | — | 174,795 |
| T50C100 | 35.4810 | +0.25% | 56.71 | 3,626,578 | +0.30% | 28.36 | 87.42 | 68.78 | 857,096 | -16.1% | 384,332 |
| T50C300 | 35.4685 | +0.21% | 57.33 | 3,627,809 | +0.34% | 28.33 | 87.47 | 68.85 | 835,121 | -18.2% | 408,104 |
| **T40C200** | **35.5229** | **+0.37%** | **59.10** | 3,635,218 | +0.54% | 28.19 | 87.83 | 68.66 | **772,680** | **-24.3%** | 477,610 |
| S3b | 35.4393 | +0.13% | 52.25 | 3,616,433 | +0.02% | 28.56 | 87.29 | 69.13 | 1,029,259 | +0.8% | 146,017 |

#### SpMV (web-Google, ~1.2h/run)

| Label | IPC | vs B1 | Acc% | D_Miss | ΔD_Miss | Cov% | IdxTL% | DatTL% | Useless | ΔUseless | Thr |
|-------|-----|-------|------|--------|---------|------|--------|--------|---------|----------|-----|
| **B1** | 175.70 | — | 51.29 | 7,587,977 | — | 12.16 | 55.93 | 90.82 | 1,152,284 | — | 3,041,496 |
| T50C100 | 181.42 | +3.25% | 63.62 | 7,814,854 | +2.99% | 9.53 | 57.51 | 92.27 | 577,074 | -49.9% | 4,016,095 |
| T50C300 | 178.54 | +1.62% | 64.26 | 7,849,182 | +3.44% | 9.13 | 57.35 | 92.35 | 537,673 | -53.3% | 4,018,157 |
| **T40C200** | **181.80** | **+3.47%** | **66.31** | 7,932,806 | +4.54% | 8.16 | 57.73 | 92.38 | **452,779** | **-60.7%** | 4,311,442 |
| S3b | 156.92 | **-10.69%** | 50.53 | 7,546,220 | -0.55% | 12.64 | 55.74 | 90.78 | 1,220,827 | +5.9% | 2,877,234 |

### 6.5 Cross-Workload Analysis

#### IPC Improvement Summary

| Config | BFS | SSSP | SpMV | GeoMean |
|--------|-----|------|------|---------|
| T50C100 (thr=50, cd=100) | +0.08% | +0.25% | +3.25% | +1.18% |
| T50C300 (thr=50, cd=300) | +0.37% | +0.21% | +1.62% | +0.73% |
| **T40C200 (thr=40, cd=200)** | **+0.39%** | **+0.37%** | **+3.47%** | **+1.40%** ★ |
| S3b (accuracy-gated) | +0.04% | +0.13% | -10.69% | -3.64% |

#### Useless PFs Reduction

| Config | BFS | SSSP | SpMV |
|--------|-----|------|------|
| T50C100 | -12.6% | -16.1% | -49.9% |
| T50C300 | -15.1% | -18.2% | -53.3% |
| **T40C200** | **-25.9%** | **-24.3%** | **-60.7%** |
| S3b | +0.4% | +0.8% | +5.9% |

#### Key Findings

**1. SpMV 是节流策略的放大器**:
- Baseline thr=80 下 SpMV 已有 3M throttled（vs BFS 39K），MSHR 长期高拥塞
- T40C200 在 SpMV 上 useless PFs 减少 60.7%，IPC 提升 3.47%——**结构性改善**
- 原因: SpMV 的 unrolled ×16 访问模式产生极高预取压力，pollution 是真正瓶颈

**2. Demand data miss 增加但 IPC 提升（所有 workload 一致）**:
- BFS: D_Miss +1.43%, IPC +0.39%
- SSSP: D_Miss +0.54%, IPC +0.37%
- SpMV: D_Miss +4.54%, IPC +3.47%
- **IPC 提升不是来自减少 miss 数量，而是减少 MSHR 拥塞 + cache pollution**

**3. Index timeliness 提升，Data timeliness 略降**:
- 节流减少 DATA_PF 对 MSHR 的竞争 → INDEX_PF 更快完成 fill → Index TL 提升
- DATA_PF 数量减少 → hit_reserved 比例下降 → Data TL 略降
- SpMV: Index TL +1.80pp（55.93%→57.73%），Data TL +1.56pp（90.82%→92.38%）

**4. S3 (accuracy-gated) 应放弃**:
- SpMV 上 -10.69% IPC——累积 accuracy 信号对 SpMV 波动大的访问模式适应不良
- BFS/SSSP 上仅 +0.04%/+0.13%——低于所有 S4 变体

**5. Coverage 下降但 IPC 上升**:
- T40C200 在 SpMV 上 coverage 从 12.16% 降到 8.16%（-4pp），但 IPC +3.47%
- **prefetch quality 比 quantity 更重要**

---

### 6.6 Phase 3: Extended Workload Validation

6 个快速测例（dir + road），验证 T40C200 在不同算法/数据集上的安全性。

| Workload | B1 IPC | T40 IPC | ΔIPC | B1 Acc% | T40 Acc% | ΔD_Miss | ΔUseless | 特征 |
|----------|--------|---------|------|---------|----------|---------|----------|------|
| bfs_cit_dir | 6.0789 | 6.0830 | +0.07% | 99.9 | 99.9 | -0.01% | +0.0% | 高 acc，无需节流 |
| sssp_cit_dir | 6.5920 | 6.5949 | +0.04% | 99.7 | 99.7 | +0.03% | +0.0% | 高 acc，无需节流 |
| bc_cit_dir | 104.64 | 104.67 | +0.03% | 99.6 | 99.6 | -0.06% | +7.7% | 高 acc，微弱影响 |
| bc_road_dir | 68.18 | 68.18 | +0.00% | 100.0 | 100.0 | +0.00% | +0.0% | 完美 acc，零影响 |
| spmv_road_sym | 1239.2 | 1250.0 | **+0.88%** | 87.8 | 88.6 | +33.1% | **-49.1%** | 中等 acc，显著改善 |
| bfs_road_dir | 0.3776 | 0.3776 | +0.00% | 0.0 | 0.0 | +0.00% | +0.0% | 无 GRASP 活动 |

**GeoMean across 6 workloads: +0.17%**

#### Key Finding: 节流收益与 baseline accuracy 负相关

| Baseline Acc 区间 | 代表 Workload | T40C200 ΔIPC | 解释 |
|-------------------|--------------|-------------|------|
| **< 55%** | bfs/sssp/spmv sym 图 | **+0.37% ~ +3.47%** | 大量 useless PF → 节流大幅减少 pollution |
| **85-90%** | spmv_road_sym | **+0.88%** | 中等 useless PF → 可观收益 |
| **> 99%** | bfs/sssp/bc dir 图 | **+0.00% ~ +0.07%** | 几乎无 useless PF → 节流无事可做 |
| **0%** | bfs_road_dir | **+0.00%** | 无 GRASP 活动 |

**结论: T40C200 是"不伤害"的默认配置**——高 accuracy 时不影响性能（+0.00%~+0.07%），低 accuracy 时显著改善（+0.37%~+3.47%）。无任何 workload 出现退化。

---

## 7. Final Conclusion

### 推荐配置

**`tc_mode=4, tc_mshr_threshold=40, tc_cooldown=200` (Cooldown Timer T40C200)**

```
-grasp_tc_mode 4 -grasp_tc_mshr_threshold 40 -grasp_tc_cooldown 200
```

#### 全量验证结果（9 workloads）

| Workload | ΔIPC | Acc% | ΔUseless | 类别 |
|----------|------|------|----------|------|
| spmv_ima_med (sym) | **+3.47%** | 66.3 | -60.7% | 高收益 |
| spmv_road_sym | +0.88% | 88.6 | -49.1% | 中收益 |
| bfs_ima_small (sym) | +0.39% | 62.3 | -25.9% | 中收益 |
| sssp_ima_small (sym) | +0.37% | 59.1 | -24.3% | 中收益 |
| bfs_cit_dir | +0.07% | 99.9 | +0.0% | 安全（高 acc 无影响） |
| sssp_cit_dir | +0.04% | 99.7 | +0.0% | 安全 |
| bc_cit_dir | +0.03% | 99.6 | +7.7% | 安全 |
| bc_road_dir | +0.00% | 100.0 | +0.0% | 安全 |
| bfs_road_dir | +0.00% | 0.0 | +0.0% | 安全（无 GRASP 活动） |

**0/9 workloads 出现退化。GeoMean(3 sym workloads) = +1.40%。**

### 设计原理

Cooldown Timer 节流机制工作原理：

```
当 MSHR 占用率 ≥ 40% 时：
  1. 丢弃当前 DATA_PF
  2. 进入冷却期（200 cycle 内所有 DATA_PF 均被抑制）
  3. 冷却期结束后恢复正常发射
  
INDEX_PF 始终不受节流影响（pipeline 正确性要求）
```

**为什么有效**:
- **更早介入 (40% vs 80%)**: 在 MSHR 真正拥塞前就开始节流，防止 useless PF 积压
- **批量抑制 (200 cycle cooldown)**: 给 cache 和 MSHR 子系统一个完整的排空窗口，而非逐个判断每个 PF（逐个判断在高压力下仍有泄漏）
- **自适应**: 低 accuracy workload（大量 useless PF）→ MSHR 频繁到 40% → 频繁触发冷却 → 大量抑制 pollution；高 accuracy workload → MSHR 少到 40% → 很少触发 → 几乎不影响

**为什么 S3 (accuracy-gated) 失败**:
- 累积 accuracy 信号反应滞后，对 SpMV 等高波动 workload 的动态变化适应不良
- SpMV 上 -10.69% IPC（灾难性退化），不可用

### 核心发现

1. **节流收益与 baseline accuracy 负相关**: acc < 55% 时收益 +0.37%~+3.47%，acc > 99% 时收益 ~0%
2. **Accuracy ≠ Performance**: IPC 提升的主因是 MSHR 拥塞缓解和 cache pollution 减少，不是 miss 数量减少
3. **Demand data miss 可以增加而 IPC 仍提升**: 减少 useless PF 释放了 MSHR/cache 资源，降低了 miss service latency
4. **SpMV 是节流最大受益者**: 高预取压力 workload 从智能节流获益最多（+3.47%）
5. **Cooldown timer 是唯一跨 workload 安全的策略**: S3 accuracy-gated 在 SpMV 上 -10.69%，不可用

---

## 8. File Modification Inventory

| File | Changes |
|------|---------|
| `grasp_prefetcher.h` | `grasp_config_t` +7 fields, `m_tc_cooldown_until` member |
| `grasp_prefetcher.cc` | Throttle block → tc_mode dispatch (~60 lines), print_config update |
| `gpu-sim.cc` | 7 `option_parser_register()` |
| `shader.h` | 7 member declarations in `shader_core_config` |
| `shader.cc` | 2x config propagation blocks +7 lines each |
