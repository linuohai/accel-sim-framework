# Spare Register Aware Prefetching — Implementation Design

> **论文**: Lakshminarayana & Kim, "Spare Register Aware Prefetching for Graph Algorithms on GPUs", HPCA 2014
>
> **状态**: 2026-03-25，准备实现
>
> **位置**: worktree `worktrees/sota_stride`, 分支 `exp/sota_stride`

---

## 1. 目标

在已有的 `baseline_prefetcher_t` 框架上实现 Spare Register baseline，重点忠实复现论文的**两步预取逻辑**（index prefetch → fill → data prefetch），用于与 GRASP 对比。

## 2. 与论文的对应关系

### 忠实复现的部分

| 论文机制 | 实现方式 |
|----------|----------|
| Load-pair 检测 | 用预构建 chain CSV（pair table）替代 Value Tag（trace-driven 限制） |
| Head stride 学习 | stride table on IMA index PC，confidence threshold=2 |
| 两步预取 | Step 1: index prefetch; Step 2: on_fill 时通过 pair table 查 data 地址并 prefetch |
| Prefetch distance | 可配置 1-4，默认 1 |

### 简化的部分

| 论文机制 | 简化方式 | 理由 |
|----------|----------|------|
| Value Tag（运行时 load-pair 检测） | 用预构建 pair table | trace-driven 模式无 load 返回值 |
| Spare register 存储 | 存入 L1D | 模拟空闲寄存器需改 operand collector，代价过高 |
| Shadow iteration counter | 固定 distance 参数 | 简化实现，可配置 |

## 3. 核心数据结构

```cpp
struct baseline_spare_reg_config_t {
  unsigned value_tags = 16;      // 未使用（pair table 替代）
  unsigned load_pairs = 8;       // 未使用（pair table 替代）
  unsigned training_iter = 3;    // stride confidence threshold
  bool use_l1d = true;           // always true in simplified version
  unsigned distance = 1;         // prefetch distance (1-4)
};

// Per-PC stride entry (only for IMA index PCs)
struct pair_entry_t {
  bool valid = false;
  new_addr_type last_addr = 0;
  int64_t stride = 0;
  unsigned confidence = 0;
};

// Pending data prefetches waiting for index fill
struct pending_data_pf_t {
  unsigned warp_id;
  std::vector<new_addr_type> data_addrs;
  unsigned long long issue_cycle;
};

// m_pairs: PC → pair_entry_t (stride state per index PC)
// m_pending: sector_addr → pending_data_pf_t (awaiting fill)
```

## 4. 算法流程

### Step 1: on_demand_load

```
if PC is not IMA index PC (get_ima_seed_chain_ids empty): return

find or create stride entry for this PC
update stride (same as stride-INTRA logic)

if stride confirmed (confidence >= threshold, stride != 0):
  for d = 1 to distance:
    future_head_addr = addr + d * stride

    // Issue index prefetch
    queue_prefetch(future_head_addr, warp_id, cycle)

    // Pre-lookup data addresses via pair table
    candidates = warp->lookup_ima_prefetch_candidates(future_head_addr, chain_ids)

    // Store as pending, keyed by index prefetch sector address
    if candidates not empty:
      m_pending[sector(future_head_addr)] = {warp_id, [cand.data_addr...], cycle}
```

### Step 2: on_fill (override)

```
call base class on_fill (for stats tracking)

sector_addr = normalize(mf->get_addr())
if sector_addr in m_pending:
  for each data_addr in pending.data_addrs:
    queue_prefetch(data_addr, pending.warp_id, fill_cycle)
  remove from m_pending
```

### Cleanup: on_kernel_launch

```
clear m_pairs
clear m_pending
```

## 5. 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-baseline_spare_reg_enable` | 0 | 总开关 |
| `-baseline_spare_reg_training_iter` | 3 | stride confidence 阈值 |
| `-baseline_spare_reg_distance` | 1 | prefetch distance (1-4) |

注：`value_tags`, `load_pairs`, `use_l1d` 保留但当前不使用。

## 6. 文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `baseline_spare_reg.h` | 重写 | 新数据结构、override on_fill |
| `baseline_spare_reg.cc` | 重写 | 两步预取逻辑 |
| `gpu-sim.cc` | 可能修改 | 新增 distance 配置项注册 |
| `shader.h` | 可能修改 | 新增 distance 配置变量 |
| `traceL1` | 确认 | `--baseline-spare-reg` 入口 |

## 7. 验证计划

### Smoke test
```bash
./traceL1 -c SM80_A100_1SM --baseline-spare-reg --max-cycle 80000 \
    --no-issue-trace --no-l1-trace --no-l2-trace --no-hbm-trace \
    bfs_ima_small spare_reg_smoke_bfs
```

期望: prefetch_issued > 0，stats 正常输出

### 500k suite
```bash
./traceL1 --baseline-spare-reg --max-cycle 500000 bfs_ima_high spare_reg_bfs500
./traceL1 --baseline-spare-reg --max-cycle 500000 sssp_ima_high spare_reg_sssp500
./traceL1 --baseline-spare-reg --max-cycle 500000 cc_ima_high spare_reg_cc500
./traceL1 --baseline-spare-reg --max-cycle 500000 spmv_ima_high spare_reg_spmv500
```

### 对比基准
- No prefetch (已有)
- Stride-INTRA (blacklist, 已有)
- Snake Plan A (已有)
