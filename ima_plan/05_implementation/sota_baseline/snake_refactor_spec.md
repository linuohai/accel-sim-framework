# Snake Prefetcher 重构规格

> 日期：2026-03-25
> 目标：将 Snake 实现从当前状态（accuracy 0.1-5.3%, IPC -7%）提升到论文水平（accuracy ~75%, IPC ~17%）
> 工作区：`/workspace/prefetch/worktrees/sota_stride/` (分支 `exp/sota_stride`)
> 源论文：Mostofi et al., "Snake: A Variable-length Chain-based Prefetching for GPUs", MICRO'23

---

## 1. 性能差距分析

| 指标 | 论文 | 当前实现 | 差距根因 |
|------|------|---------|---------|
| Accuracy | 75% | 0.1-5.3% | 无 decoupled storage → L1 pollution |
| Coverage | 80% | 1-2.4% | Training bug → pattern 未激活 |
| IPC GMEAN | +17% | -1.9% ~ -7.4% | 以上两者叠加 |

论文 §5.7 消融实验 (Figure 25) 显示：
- Snake (full) = +17%
- Snake-DT (无 decoupling+throttling) = +10%（accuracy 降 50%）
- Snake-T (无 throttling) = +13%
- s-Snake (仅 intra/inter-warp, 无 inter-thread) = +7%

## 2. 分层实现计划

### Phase 1: Training 逻辑修复 + WarpID Vector

**文件**: `baseline_snake.h`, `baseline_snake.cc`

#### 2.1.1 TT Entry 添加 WarpID Bitmap

```cpp
// baseline_snake.h — tt_entry_t 修改
struct tt_entry_t {
    // ... existing fields ...
    uint64_t warp_confirmed_mask = 0;  // 64-bit bitmap, bit i = warp i confirmed
    unsigned training_warp_count() const {
        return __builtin_popcountll(warp_confirmed_mask);
    }
};
```

#### 2.1.2 Training Gate 修复

```cpp
// baseline_snake.cc — update_training() 修改
// 当前 (buggy):
//   if (entry.iaw_last_warp_id != warp_id && entry.iew_last_warp_id != warp_id)
//     entry.training_warp_count++;
// 修复为:
if (!(entry.warp_confirmed_mask & (1ULL << warp_id))) {
    entry.warp_confirmed_mask |= (1ULL << warp_id);
    if (entry.training_warp_count() >= m_cfg.training_warps) {
        entry.training_done = true;
    }
}
```

#### 2.1.3 Eviction 策略改进

```cpp
// 驱逐优先级：popcnt 最小 → LRU
// 先从 LRU 候选中选 warp_confirmed_mask popcnt 最小的
unsigned best_victim = lru_victim;
unsigned best_popcnt = 64;
for (auto &candidate : lru_candidates) {
    unsigned pc = __builtin_popcountll(candidate.warp_confirmed_mask);
    if (pc < best_popcnt) {
        best_popcnt = pc;
        best_victim = candidate.idx;
    }
}
```

**验证**: 编译 → 跑 backprop → 检查 `training_done` 的 TT entry 数量是否增加。

---

### Phase 2: Decoupled Storage

**文件**: `gpu-cache.h`, `gpu-cache.cc`, `baseline_snake.h`, `baseline_snake.cc`, `shader.cc`, `mem_fetch.h`

#### 2.2.1 Cache Block Metadata

```cpp
// gpu-cache.h — cache_block_t 添加
class cache_block_t {
    // ... existing ...
    bool m_is_snake_prefetch = false;  // 仅 Snake 模式使用
public:
    void set_snake_prefetch(bool v) { m_is_snake_prefetch = v; }
    bool is_snake_prefetch() const { return m_is_snake_prefetch; }
};
```

#### 2.2.2 Prefetch 请求标记

```cpp
// mem_fetch.h — 添加 Snake prefetch 标记
class mem_fetch {
    // ... existing ...
    bool m_is_snake_prefetch = false;
public:
    void set_snake_prefetch(bool v) { m_is_snake_prefetch = v; }
    bool is_snake_prefetch() const { return m_is_snake_prefetch; }
};
```

在 `baseline_snake_t::inject_prefetch()` 生成的 `mem_fetch` 上设置此 flag。

#### 2.2.3 Fill 路径分流

```cpp
// gpu-cache.cc — baseline_cache::fill() 修改
void baseline_cache::fill(mem_fetch *mf, unsigned time) {
    // ... existing fill logic ...
    // 找到 fill 的 cache block 后:
    cache_block_t *block = ...;
    block->set_snake_prefetch(mf->is_snake_prefetch());
    // 如果是 demand fill，且命中了一个 prefetch block → promotion
    // (这发生在 access() 中，不是 fill() 中)
}
```

#### 2.2.4 Demand Hit on Prefetch Line (Promotion)

```cpp
// gpu-cache.cc — baseline_cache::access() 修改
// 在 HIT 路径中:
if (status == HIT || status == HIT_RESERVED) {
    cache_block_t *block = m_tag_array->get_block(cache_index);
    if (block->is_snake_prefetch()) {
        block->set_snake_prefetch(false);  // promote to normal
        // (可选) 记录 promotion 统计
    }
}
```

#### 2.2.5 容量管理与 Eviction

```cpp
// gpu-cache.cc — 在 Snake 模式下修改 eviction 策略
// 新增 helper:
unsigned baseline_cache::count_snake_prefetch_lines() const {
    unsigned count = 0;
    for (unsigned i = 0; i < m_config.get_num_lines(); i++) {
        if (m_tag_array->get_block_const(i)->is_snake_prefetch() &&
            m_tag_array->get_block_const(i)->is_valid())
            count++;
    }
    return count;
}

// Eviction 策略修改 (在 find_victim 逻辑中):
// 1. 如果 normal 区域需要空间:
//    优先驱逐 is_snake_prefetch == true 的 LRU line
// 2. 如果 prefetch 区域需要空间:
//    驱逐最老的 prefetch line
// 3. 初始阶段限制 prefetch 占比 ≤50%
```

#### 2.2.6 Snake Prefetch 50% 容量限制

```cpp
// baseline_snake.cc — generate_prefetches() 修改
// 在发出 prefetch 前检查:
bool baseline_snake_t::can_issue_prefetch() const {
    if (!m_l1d_cache) return true;  // 无法查询时放行
    unsigned pf_lines = m_l1d_cache->count_snake_prefetch_lines();
    unsigned total_lines = m_l1d_cache->get_num_lines();
    // 论文: "restricts L1 cache to utilize only up to 50% of the available decoupled space"
    return pf_lines < total_lines / 2;
}
```

**验证**: 编译 → 跑 backprop → 检查 accuracy 是否从 2-5% 提升到 30%+。

---

### Phase 3: Throttling

**文件**: `baseline_snake.h`, `baseline_snake.cc`

#### 2.3.1 Free Space Throttle

```cpp
// baseline_snake.h
unsigned long long m_throttle_until = 0;
static constexpr unsigned THROTTLE_PAUSE_CYCLES = 50;

// baseline_snake.cc — generate_prefetches() 入口
void baseline_snake_t::generate_prefetches(unsigned warp_id, ..., unsigned long long cycle) {
    if (cycle < m_throttle_until) return;  // throttled

    if (!can_issue_prefetch()) {
        m_throttle_until = cycle + THROTTLE_PAUSE_CYCLES;
        return;
    }
    // ... existing prefetch generation ...
}
```

#### 2.3.2 Bandwidth Throttle（简化版）

```cpp
// 论文: 当 bandwidth >= 70% peak 时暂停，降到 50% 后恢复
// 简化: 用 L1 MSHR 占用率近似 bandwidth pressure
bool baseline_snake_t::bandwidth_throttled() const {
    if (!m_l1d_cache) return false;
    // 如果 MSHR 占用 > 70% → throttle
    unsigned mshr_used = m_l1d_cache->get_mshr_used();
    unsigned mshr_total = m_l1d_cache->get_mshr_entries();
    return (mshr_used * 100 / mshr_total) > 70;
}
```

**验证**: 编译 → 跑全套 Rodinia 4 个 benchmark → 对比论文 Figure 18。

---

## 3. 接口需求

### 3.1 baseline_snake_t 需要访问 L1D cache

当前 `baseline_snake_t` 没有 L1D cache 的引用。需要在构造时传入：

```cpp
// shader.cc 创建 Snake 时传入 L1D 指针
m_baseline = new baseline_snake_t(m_sid, snake_cfg, m_L1D);
```

### 3.2 mem_fetch 需要 Snake prefetch 标记

在 `baseline_prefetcher_t::inject_prefetch()` 创建 `mem_fetch` 时设置 `m_is_snake_prefetch = true`。这需要在 `inject_prefetch()` 中区分 Snake vs 其他 baseline 的 prefetch。

### 3.3 gpu-cache 新增查询接口

```cpp
// gpu-cache.h — baseline_cache 新增 public 方法
unsigned count_snake_prefetch_lines() const;
unsigned get_num_lines() const;
unsigned get_mshr_used() const;
unsigned get_mshr_entries() const;
```

---

## 4. 不修改的内容

- **Inter-thread / intra-warp / inter-warp stride 检测逻辑**: 当前已正确实现
- **Chain following**: 当前部分实现，Phase 1-3 不涉及
- **Head Table 结构**: 保持不变
- **Prefetch address 生成**: 保持不变

---

## 5. 验证标准

| Phase | 验证指标 | 目标 |
|-------|---------|------|
| Phase 1 | TT training_done entry count | 增加 2x+ |
| Phase 2 | Accuracy on backprop | 从 2% → 30%+ |
| Phase 3 | IPC on backprop | 从 -2.5% → +0% 以上 |
| Final | Rodinia 4 benchmark geomean | 方向与论文一致（Snake > INTRA） |

## 6. 论文数据对照（目标）

| Benchmark | 论文 Snake | 目标范围 (±50%) |
|-----------|----------|---------------|
| Backprop | ~8% | +4% ~ +12% |
| Hotspot | ~10% | +5% ~ +15% |
| Srad | ~29% | +15% ~ +43% |
| lud | ~3% | +1% ~ +5% |
| nw | ~1% | ≥0% |

注：由于 Ampere vs Volta 架构差异，绝对值可能有偏差，但**方向和排序必须一致**。
