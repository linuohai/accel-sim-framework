# Benchmark Suite — IMA Prefetcher 评估测例

> 后续所有实验（baseline / ideal L1D / prefetcher / ablation）均须覆盖本文件定义的全部 trace key。
> 各 trace key 定义于 `traceL1` 脚本的 `TRACE_MAP`。

---

## 图输入与 IMA 强度分级

| 级别 | 图 | 特征 |
|------|-----|------|
| high | cit-Patents (symmetrized) | 高度数、大邻接表 → 高 IMA 压力 |
| med | web-Google (symmetrized) | 中等度数 → 中等 IMA 压力 |
| small | web-Google (not symmetrized) / roadNet-CA | 低度数或稀疏 → 低 IMA 压力 |

---

## 完整测例矩阵（7 算法，19 trace keys）

| 算法 | `_ima_high` | `_ima_med` | `_ima_small` | 备注 |
|------|-------------|------------|--------------|------|
| BFS | `bfs_ima_high` | `bfs_ima_med` | `bfs_ima_small` | |
| SSSP | `sssp_ima_high` | `sssp_ima_med` | `sssp_ima_small` | |
| BC | `bc_ima_high` | `bc_ima_med` | `bc_ima_small` | |
| CC | `cc_ima_high` | `cc_ima_med` | `cc_ima_small` | |
| SpMV | `spmv_ima_high` | `spmv_ima_med` | — | SpMV 要求对称输入，无 nosym tier |
| PR | `pr_ima_high` | `pr_ima_med` | `pr_ima_small` | |
| VC | `vc_ima_high` | `vc_ima_med` | `vc_ima_small` | small 用 roadNet-CA |

### 快速引用（用于批量脚本）

```bash
# 全部 high IMA（7 个，用于 SOTA 对比 / ablation）
IMA_HIGH="bfs_ima_high sssp_ima_high bc_ima_high cc_ima_high spmv_ima_high pr_ima_high vc_ima_high"

# 全部 med IMA（7 个）
IMA_MED="bfs_ima_med sssp_ima_med bc_ima_med cc_ima_med spmv_ima_med pr_ima_med vc_ima_med"

# 全部 small IMA（5 个，SpMV 无 small tier，VC 用 roadNet-CA）
IMA_SMALL="bfs_ima_small sssp_ima_small bc_ima_small cc_ima_small pr_ima_small vc_ima_small"

# 全部 19 个
ALL_IMA="$IMA_HIGH $IMA_MED $IMA_SMALL"
```

---

## 各实验类型须覆盖的测例

| 实验类型 | 覆盖范围 | trace keys 数量 | 说明 |
|----------|---------|-----------------|------|
| Baseline (no prefetch) | `ALL_IMA` | 19 | 基准 IPC / miss rate / stall |
| Ideal L1D 上界 | `ALL_IMA` | 19 | 性能天花板（`--ideal-l1d`） |
| IMA Prefetcher | `ALL_IMA` | 19 | 主实验 |
| SOTA 对比 (GRASP 等) | `IMA_HIGH` | 7 | 高 IMA 下与已有方案对比 |
| Ablation Study | `IMA_HIGH` | 7 | 消融实验用代表性测例 |
| Sensitivity Study | 选 3-4 个代表 | 3-4 | 参数扫描（建议 bfs/bc/spmv/pr） |

---

## 入选依据

| 算法 | SASS chain 符合率 | L1 miss rate (high) | Ideal L1D 加速 (high) | IMA miss share |
|------|-------------------|--------------------|-----------------------|----------------|
| BFS | 100% | 77.2% | 1.75× | 99.1% |
| SSSP | 100% | 76.7% | 2.46× | 51.1% |
| BC | 100% | 70.3% | 3.04× | 70.5% |
| CC | 100% | — | 2.22× | 83.6% |
| SpMV | 100% | — | 2.31× | 66.9% |
| PR | 100% | 64.0% | 待测 | 待测 |
| VC | 97% | 待测 | 待测 | 待测 |

> 筛选标准：SASS chain 符合率 ≥ 95% 且 ideal L1D 加速 > 10%（PR/VC 待补充数据）。

---

## 未入选但可扩展的算法

| 算法 | 原因 | 条件 |
|------|------|------|
| SCC | 71% instances 用 LEA 而非 IMAD.WIDE，prefetcher 检测困难 | 扩展检测器后可加入 |
| SymGS | 未做 SASS 分析，IMA 模式未确认 | 完成 SASS 分析后可加入 |
| TC | 瓶颈是 set intersection 而非 IMA | 排除 |
