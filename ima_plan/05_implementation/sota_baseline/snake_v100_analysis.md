> 最近更新: 2026-03-30

# Snake V100 Validation Analysis

## 实验配置

- **Config**: SM7_V100_SNAKE (匹配论文 Table 1: 80SM, 1530MHz, 128KB L1D, 512 MSHR, GTO)
- **Traces**: Accel-Sim 官方 V100 Rodinia 3.1 (CUDA 11.0)
- **实现**: s-Snake (IaW + IeW, IT chain 禁用)

## 结果对比

| Benchmark | 我们 IPC | 论文 IPC | 我们 Acc | 论文 Acc | 我们 Cov | 论文 Cov |
|-----------|---------|---------|---------|---------|---------|---------|
| backprop  | -0.75%  | +1%     | 5.9%    | ~90%    | 1.3%    | ~80%    |
| hotspot   | +0.29%  | +10%    | 0.4%    | ~90%    | 0.1%    | ~85%    |
| srad      | +0.05%  | +29%    | 17%     | ~95%    | 8%      | ~90%    |
| lud       | +0.01%  | +10%    | 0.7%    | ~80%    | 0.1%    | ~70%    |
| nw        | 0%      | +5%     | 0%      | ~70%    | 0%      | ~40%    |

## 13 轮迭代发现的根因

### 1. IeW timeliness 问题（致命）

**现象**: IeW stride 正确（backprop PC_0090: stride=8, PC_0180: stride=136）但 prefetch 全部 useless。

**根因**: GTO scheduler 下，同一 CTA 的相邻 warp 仅间隔 1-2 cycles。L2 round-trip ~160 cycles。Prefetch 永远来不及。

**trace 验证**:
```
PC_0090: IeW stride = 8 bytes (warp 间隔)
  → 但 128B cache line 包含 16 个 stride=8 的地址
  → 所有 warp 命中同一 cache line, 无 miss 可覆盖

PC_0180: IeW stride = 136 bytes
  → 8 warps/CTA, 相邻 warp 1-2 cycle 间隔
  → Prefetch addr+136 需 160 cycle 到达, 下一个 warp 2 cycle 后就 demand
```

### 2. IaW cross-CTA 污染（严重）

**现象**: IaW stride 学到 43776 而不是期望的 64。

**根因**: Backprop kernel-1 每 CTA 只有 ~8 iterations，8 warps 分配后每 warp **只执行 1 次 loop**。第二次看到同一 PC 时，是不同 CTA 复用同一 warp slot → 学到 cross-CTA address 差异。

**验证**:
```
SNAKE_LEARN SM0: IaW warp=3 pc=0x90 old_addr=0x7f064170001c
                 new_addr=0x7f064170ab1c delta=43776  (cross-CTA!)
```

### 3. IT stride 跨 warp 不稳定（严重）

**现象**: IT stride 在同一 warp 不同迭代间稳定（=1000），但不同 warp 间不一致。

**根因**: 两个 PC 的 IeW stride 不同（PC_0090: 8, PC_0180: 136）。IT stride = addr_B - addr_A 随 warp 不同而变化（差 128 = 136-8）。

**验证**:
```
IT(0090→0180):
  Warp 0: -441,450,428
  Warp 1: -441,450,300  (差 128)
  Warp 2: -441,450,172  (差 128)
→ 永远无法通过 2-observation 验证
```

### 4. IT chain 过度 prefetch（严重）

**现象**: Srad 发出 10 亿 IT prefetch, accuracy 仅 17%。

**根因**: IT stride 不稳定但偶尔 confirm → 大量错误 prefetch 填入 cache → 驱逐有用数据。

## 论文与复现的根本差异

| 维度 | 论文 | 我们 | 影响 |
|------|------|------|------|
| Accel-Sim 版本 | v1.2.0 | 修改版 fork | 调度、cache、MSHR 行为可能不同 |
| GTO 调度细节 | 原版 | 可能微调过 | Warp 交错模式影响 stride 稳定性 |
| Head Table 实现 | 硬件级 2-slot per-PC | 软件模拟 per-warp 2-slot | 不影响正确性但影响精确行为 |
| MSHR/Cache 替换 | 原版 LRU | 修改版（加了 snake prefetch flag） | Prefetch 驱逐逻辑可能不同 |

## 实现的架构改进（保留在代码中）

1. **2-slot per-warp Head Table**: 直接 IaW detection，不依赖 IT stride
2. **IaW IT stride accumulation**: 论文 case 2，支持多 PC 循环
3. **Per-PC 2-slot**: IeW detection with CTA filtering
4. **Decoupled storage**: Prefetch lines 标记 + 驱逐优先
5. **Throttling**: 50-cycle pause on 50% capacity / 70% MSHR
6. **Configurable parameters**: TT size, training warps, chain length, lookahead

## 后续方向

1. **对比 Accel-Sim v1.2.0**: 在原版 v1.2.0 上跑 baseline 和 Snake，确认调度行为差异
2. **联系论文作者**: 获取 Snake 实现的 patch 或验证数据
3. **调整 IeW lookahead**: 根据 per-benchmark CTA 大小动态设置
4. **CTA-Aware 整合**: 用 inter-CTA stride 替代 intra-CTA IeW
