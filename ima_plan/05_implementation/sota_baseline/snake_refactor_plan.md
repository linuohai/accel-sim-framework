# Snake Prefetcher Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Snake prefetcher to match MICRO'23 paper performance (accuracy 75%, IPC +17%) by adding decoupled storage, throttling, and fixing training logic.

**Architecture:** Three-phase incremental refactoring of `baseline_snake.{h,cc}` with additions to `gpu-cache.{h,cc}`, `mem_fetch.h`, `shader.cc`, and `baseline_prefetcher.cc`. Each phase compiles and validates independently. All work in worktree `/workspace/prefetch/worktrees/sota_stride/` (branch `exp/sota_stride`).

**Tech Stack:** C++ in GPGPU-Sim/Accel-Sim, make build system, traceL1 test harness.

---

## File Map

### Modified files
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.h` — TT entry warpID bitmap, L1D cache pointer, throttle state
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.cc` — Training fix, prefetch gating, throttle logic
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.h` — `cache_block_t::m_is_snake_prefetch`, `baseline_cache` query methods
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc` — Fill path snake flag, eviction preference
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/mem_fetch.h` — `m_is_snake_prefetch` flag
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.cc` — Set snake flag on prefetch mem_fetch
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.h` — `virtual bool is_snake()` method
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc` — Pass L1D pointer to Snake constructor

### Reference (read-only)
- `ima_plan/05_implementation/sota_baseline/snake_refactor_spec.md`
- `ima_plan/02_related_work/gpu/Mostofi 等 - 2023 - Snake*.pdf` (§3.1-3.3, §5)

---

## Task 1: Phase 1 — Fix Training Logic + WarpID Bitmap

**Files:**
- Modify: `baseline_snake.h:29-33` (tt_entry_t) and `baseline_snake.h:54-56` (ht_entry_t training fields)
- Modify: `baseline_snake.cc:235-253` (training gate in on_demand_load)

- [ ] **Step 1: Add warpID bitmap to ht_entry_t**

In `baseline_snake.h`, replace the `training_warp_count` field in `ht_entry_t`:

```cpp
// ht_entry_t — replace lines 55-56:
// OLD:
//   unsigned training_warp_count = 0;
//   bool training_done = false;
// NEW:
uint64_t warp_confirmed_mask = 0;
bool training_done = false;

unsigned training_warp_count() const {
    return static_cast<unsigned>(__builtin_popcountll(warp_confirmed_mask));
}
```

- [ ] **Step 2: Fix training gate in on_demand_load**

In `baseline_snake.cc`, replace lines 235-252:

```cpp
// OLD (buggy AND logic):
//   if (!entry.training_done) {
//     if (entry.iaw_last_warp_id != warp_id &&
//         entry.iew_last_warp_id != warp_id) {
//       entry.training_warp_count++;
//     }
//     ...
//     if (entry.training_warp_count >= m_cfg.training_warps) {
//       entry.training_done = true;
//     }
//   }

// NEW (warpID bitmap):
if (!entry.training_done) {
    // Record this warp in the confirmation bitmap
    if (warp_id < 64 &&
        !(entry.warp_confirmed_mask & (1ULL << warp_id))) {
        entry.warp_confirmed_mask |= (1ULL << warp_id);
        if (entry.training_warp_count() >= m_cfg.training_warps) {
            entry.training_done = true;
        }
    }

    // IT chain: if this warp just accessed a different PC, try to extend
    if (tracker != nullptr && tracker->valid && tracker->last_pc != pc) {
        int prev_ht = find_ht_entry(tracker->last_pc);
        if (prev_ht >= 0) {
            try_extend_chain(m_ht[prev_ht], tracker->last_pc,
                             tracker->last_addr, pc, addr);
        }
    }
}
```

- [ ] **Step 3: Update HT eviction to prefer low warp_confirmed_mask**

In `baseline_snake.cc` `alloc_ht_entry()`, replace lines 57-67:

```cpp
// Eviction: prefer non-trained entries, then lowest warp count, then LRU
unsigned victim = 0;
for (unsigned i = 1; i < m_ht.size(); ++i) {
    const ht_entry_t &vi = m_ht[victim];
    const ht_entry_t &ci = m_ht[i];
    // Non-trained beats trained
    if (!ci.training_done && vi.training_done) { victim = i; continue; }
    if (ci.training_done != vi.training_done) continue;
    // Fewer confirmed warps = less useful
    if (ci.training_warp_count() < vi.training_warp_count()) {
        victim = i; continue;
    }
    if (ci.training_warp_count() != vi.training_warp_count()) continue;
    // LRU tiebreak
    if (ci.last_access_cycle < vi.last_access_cycle) { victim = i; }
}
```

- [ ] **Step 4: Reset warp_confirmed_mask on kernel launch**

In `on_kernel_launch()`, the existing `e = ht_entry_t()` already zero-initializes `warp_confirmed_mask`. No change needed — verify this is the case.

- [ ] **Step 5: Compile and smoke test**

```bash
cd /workspace/prefetch/worktrees/sota_stride
source ./gpu-simulator/setup_environment.sh
make -j64 -C ./gpu-simulator/ 2>&1 | tail -5
```

Expected: compiles without errors.

- [ ] **Step 6: Run backprop baseline validation**

```bash
EVAL="--no-l1-trace --no-l2-trace --no-hbm-trace --no-stall-reason-pc-stats --no-issue-trace"
./traceL1 --baseline-snake $EVAL backprop backprop_phase1_snake
```

Check: `grep BASELINE_SNAKE result/log/backprop_phase1_snake.log | tail -3`

Expected: `training_done` entries visible in HT, prefetch_issued > 0.

- [ ] **Step 7: Commit Phase 1**

```bash
cd /workspace/prefetch/worktrees/sota_stride
git add gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.h \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.cc
git commit -m "fix(snake): replace buggy AND training gate with warpID bitmap

Training now uses a 64-bit warp_confirmed_mask instead of broken
iaw/iew_last_warp_id AND check. Eviction prefers lowest warp count."
```

---

## Task 2: Phase 2a — Infrastructure for Decoupled Storage

**Files:**
- Modify: `gpu-cache.h:125-170` (cache_block_t)
- Modify: `gpu-cache.h:1280+` (baseline_cache)
- Modify: `mem_fetch.h` (add snake prefetch flag)
- Modify: `baseline_prefetcher.h` (add virtual is_snake)
- Modify: `baseline_snake.h` (override is_snake, add L1D pointer)

- [ ] **Step 1: Add m_is_snake_prefetch to cache_block_t**

In `gpu-cache.h`, add to `struct cache_block_t` after `m_block_addr` (line ~169):

```cpp
  new_addr_type m_tag;
  new_addr_type m_block_addr;
  bool m_is_snake_prefetch = false;
```

- [ ] **Step 2: Add snake prefetch flag to mem_fetch**

In `mem_fetch.h`, add private member and accessors (near the other `m_is_*` flags):

```cpp
  bool m_is_snake_prefetch = false;
public:
  void set_snake_prefetch(bool v) { m_is_snake_prefetch = v; }
  bool is_snake_prefetch() const { return m_is_snake_prefetch; }
```

- [ ] **Step 3: Add is_snake() virtual to baseline_prefetcher_t**

In `baseline_prefetcher.h`, add to public section:

```cpp
  virtual bool is_snake() const { return false; }
```

In `baseline_snake.h`, add override:

```cpp
  bool is_snake() const override { return true; }
```

- [ ] **Step 4: Set snake flag on prefetch mem_fetch in inject_prefetch**

In `baseline_prefetcher.cc` line ~111, after creating `pf_mf`:

```cpp
  mem_fetch *pf_mf =
      mf_alloc->alloc(req.addr, GLOBAL_ACC_R, active_mask, byte_mask,
                      sector_mask, kBaselineSectorSize, false, cycle,
                      req.warp_id, sid, tpc, nullptr, 0);
  if (is_snake()) pf_mf->set_snake_prefetch(true);
  result.requests.push_back(pf_mf);
```

- [ ] **Step 5: Add L1D pointer to baseline_snake_t**

In `baseline_snake.h`, add constructor parameter and member:

```cpp
class baseline_snake_prefetcher_t : public baseline_prefetcher_t {
 public:
  baseline_snake_prefetcher_t(unsigned sm_id,
                              const baseline_snake_config_t &cfg,
                              class baseline_cache *l1d);
  // ...
 private:
  // ...
  baseline_cache *m_l1d_cache;  // for decoupled storage queries
```

In `baseline_snake.cc` constructor:

```cpp
baseline_snake_prefetcher_t::baseline_snake_prefetcher_t(
    unsigned sm_id, const baseline_snake_config_t &cfg,
    baseline_cache *l1d)
    : baseline_prefetcher_t(sm_id),
      m_cfg(cfg),
      m_ht(cfg.ht_size),
      m_tt(cfg.tt_size),
      m_tt_free_head(0),
      m_warp_trackers(kMaxWarps),
      m_l1d_cache(l1d) {}
```

- [ ] **Step 6: Pass L1D to Snake in shader.cc**

In `shader.cc` where Snake is constructed (~line 3874), change:

```cpp
// OLD:
// m_baseline = new baseline_snake_prefetcher_t(m_sid, snake_cfg);
// NEW:
m_baseline = new baseline_snake_prefetcher_t(m_sid, snake_cfg, m_L1D);
```

- [ ] **Step 7: Add query methods to baseline_cache**

In `gpu-cache.h`, add to `baseline_cache` public section:

```cpp
  unsigned count_snake_prefetch_lines() const;
  unsigned get_total_lines() const { return m_config.get_num_lines(); }
  unsigned get_mshr_used() const { return m_mshrs.get_count(); }
  unsigned get_mshr_entries() const { return m_config.m_mshr_entries; }
```

Check if `mshr_table::get_count()` exists. If not, add to `mshr_table`:

```cpp
  unsigned get_count() const { return m_data.size(); }
```

In `gpu-cache.cc`, implement `count_snake_prefetch_lines()`:

```cpp
unsigned baseline_cache::count_snake_prefetch_lines() const {
    unsigned count = 0;
    for (unsigned i = 0; i < m_config.get_num_lines(); i++) {
        cache_block_t *blk = m_tag_array->get_block(i);
        if (blk->is_valid_line() && blk->m_is_snake_prefetch)
            count++;
    }
    return count;
}
```

- [ ] **Step 8: Compile**

```bash
make -j64 -C ./gpu-simulator/ 2>&1 | tail -5
```

Expected: compiles. No behavioral change yet — flags are set but not acted upon.

- [ ] **Step 9: Commit Phase 2a**

```bash
git add gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.h \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/mem_fetch.h \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.h \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.cc \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.h \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.cc \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc
git commit -m "feat(snake): add decoupled storage infrastructure

Add is_snake_prefetch flag to cache_block_t and mem_fetch.
Pass L1D pointer to Snake constructor.
Add cache query methods for prefetch line counting."
```

---

## Task 3: Phase 2b — Activate Decoupled Storage Behavior

**Files:**
- Modify: `gpu-cache.cc` (fill path + eviction)
- Modify: `baseline_snake.cc` (prefetch capacity check)

- [ ] **Step 1: Mark prefetch lines on fill**

In `gpu-cache.cc` `baseline_cache::fill()`, after the `m_tag_array->fill()` call (line ~1258-1261), add:

```cpp
  // Mark snake prefetch lines
  if (mf->is_snake_prefetch()) {
      cache_block_t *blk = m_tag_array->get_block(e->second.m_cache_index);
      blk->m_is_snake_prefetch = true;
  }
```

Note: for ON_FILL policy, need to handle differently — the block is allocated during fill. For ON_MISS, the block was allocated during access. Check which policy the SM80_A100 L1D uses and handle accordingly.

- [ ] **Step 2: Promote prefetch line on demand hit**

In `gpu-cache.cc`, in the L1D access path where HIT is returned. Find the `data_cache::access()` or `l1_cache::access()` method. After confirming HIT status:

```cpp
  // In the HIT path of data_cache::access() or equivalent:
  if (status == HIT || status == HIT_RESERVED) {
      cache_block_t *blk = m_tag_array->get_block(cache_index);
      if (blk->m_is_snake_prefetch) {
          blk->m_is_snake_prefetch = false;  // promote to normal
      }
  }
```

This requires identifying the exact HIT path in the L1D cache hierarchy. Locate `data_cache::access()` or `l1_cache::access()`.

- [ ] **Step 3: Eviction prefers prefetch lines for demand requests**

In the eviction/victim selection path of the L1D tag array, when evicting for a demand request, prefer `m_is_snake_prefetch == true` lines:

Locate `tag_array::probe()` or the victim selection logic. Add preference:

```cpp
// In victim selection: if a snake prefetch line exists in the set, prefer it
for (each way in set) {
    if (block[way].m_is_snake_prefetch && block[way].is_valid_line()) {
        return way;  // evict prefetch line first
    }
}
// fallback to normal LRU
```

- [ ] **Step 4: Add 50% capacity check in Snake**

In `baseline_snake.cc`, add capacity gating to `generate_prefetches()`:

```cpp
void baseline_snake_prefetcher_t::generate_prefetches(
    const ht_entry_t &entry, new_addr_type addr, unsigned warp_id,
    unsigned long long cycle) {
  // 50% capacity limit (paper §3.2)
  if (m_l1d_cache) {
      unsigned pf_count = m_l1d_cache->count_snake_prefetch_lines();
      unsigned total = m_l1d_cache->get_total_lines();
      if (pf_count >= total / 2) return;  // throttled
  }

  // ... existing prefetch generation unchanged ...
```

- [ ] **Step 5: Clear snake prefetch flag on kernel launch**

In `baseline_cache` or wherever L1D is reset on kernel launch, clear all `m_is_snake_prefetch` flags. Or rely on the fact that `cache_block_t` is re-initialized to `false` when a new block is allocated (default init).

Verify: when a cache line is evicted and re-allocated, `m_is_snake_prefetch` is reset to false. Check `line_cache_block::allocate()`.

- [ ] **Step 6: Compile and validate**

```bash
make -j64 -C ./gpu-simulator/ 2>&1 | tail -5

EVAL="--no-l1-trace --no-l2-trace --no-hbm-trace --no-stall-reason-pc-stats --no-issue-trace"
./traceL1 --baseline-snake $EVAL backprop backprop_phase2_snake &
./traceL1 $EVAL backprop backprop_phase2_np &
wait
```

Compare:
```bash
echo "NP:"; grep gpu_tot_ipc result/log/backprop_phase2_np.log | tail -1
echo "Snake:"; grep gpu_tot_ipc result/log/backprop_phase2_snake.log | tail -1
echo "Stats:"; grep BASELINE_SNAKE result/log/backprop_phase2_snake.log | tail -1
```

Expected: accuracy significantly improved (target >30%).

- [ ] **Step 7: Commit Phase 2b**

```bash
git add gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.cc
git commit -m "feat(snake): activate decoupled storage

Prefetch fills marked as snake_prefetch in cache blocks.
Demand hits promote prefetch lines to normal.
Eviction prefers prefetch lines for demand misses.
50% capacity limit on prefetch lines."
```

---

## Task 4: Phase 3 — Throttling

**Files:**
- Modify: `baseline_snake.h` (throttle state)
- Modify: `baseline_snake.cc` (throttle logic in generate_prefetches)

- [ ] **Step 1: Add throttle state to Snake**

In `baseline_snake.h`, add members:

```cpp
  unsigned long long m_throttle_until = 0;
  static constexpr unsigned kThrottlePauseCycles = 50;
```

- [ ] **Step 2: Add throttle check to generate_prefetches**

In `baseline_snake.cc` `generate_prefetches()`, expand the capacity check:

```cpp
void baseline_snake_prefetcher_t::generate_prefetches(
    const ht_entry_t &entry, new_addr_type addr, unsigned warp_id,
    unsigned long long cycle) {
  // Throttle: pause for kThrottlePauseCycles after hitting limit
  if (cycle < m_throttle_until) return;

  if (m_l1d_cache) {
      // Free space throttle (paper §3.3 condition 1)
      unsigned pf_count = m_l1d_cache->count_snake_prefetch_lines();
      unsigned total = m_l1d_cache->get_total_lines();
      if (pf_count >= total / 2) {
          m_throttle_until = cycle + kThrottlePauseCycles;
          return;
      }

      // Bandwidth throttle (paper §3.3 condition 2, simplified via MSHR)
      unsigned mshr_used = m_l1d_cache->get_mshr_used();
      unsigned mshr_total = m_l1d_cache->get_mshr_entries();
      if (mshr_total > 0 && (mshr_used * 100 / mshr_total) > 70) {
          m_throttle_until = cycle + kThrottlePauseCycles;
          return;
      }
  }

  // ... existing prefetch generation unchanged ...
```

- [ ] **Step 3: Reset throttle on kernel launch**

In `baseline_snake.cc` `on_kernel_launch()`, add:

```cpp
  m_throttle_until = 0;
```

- [ ] **Step 4: Compile and full validation**

```bash
make -j64 -C ./gpu-simulator/ 2>&1 | tail -5

EVAL="--no-l1-trace --no-l2-trace --no-hbm-trace --no-stall-reason-pc-stats --no-issue-trace"
for bench in backprop hotspot lud nw; do
    ./traceL1 $EVAL "$bench" "${bench}_final_np" &
    ./traceL1 --baseline-snake $EVAL "$bench" "${bench}_final_snake" &
    ./traceL1 --baseline-intra $EVAL "$bench" "${bench}_final_intra" &
done
wait
```

- [ ] **Step 5: Collect and compare results**

```bash
echo "=== Final Snake Validation ==="
for bench in backprop hotspot lud nw; do
    np=$(grep gpu_tot_ipc result/log/${bench}_final_np.log | tail -1 | awk -F= '{print $2}')
    snake=$(grep gpu_tot_ipc result/log/${bench}_final_snake.log | tail -1 | awk -F= '{print $2}')
    intra=$(grep gpu_tot_ipc result/log/${bench}_final_intra.log | tail -1 | awk -F= '{print $2}')
    echo "$bench: NP=$np  Snake=$snake  INTRA=$intra"
done
```

Success criteria:
- Snake IPC > NP IPC on at least 2/4 benchmarks
- Snake > INTRA on at least 3/4 benchmarks
- Accuracy > 30% on backprop

- [ ] **Step 6: Commit Phase 3**

```bash
git add gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.h \
        gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_snake.cc
git commit -m "feat(snake): add throttling mechanism

Free space throttle (50 cycle pause when prefetch lines >= 50%).
Bandwidth throttle (MSHR utilization > 70%).
Matches Snake paper §3.3."
```

---

## Task 5: Validation and Documentation

- [ ] **Step 1: Run full Rodinia suite with stats**

```bash
for bench in backprop hotspot lud nw; do
    echo "=== $bench ==="
    grep BASELINE_SNAKE result/log/${bench}_final_snake.log | tail -1
done
```

- [ ] **Step 2: Update paper_validation.md with new results**

Fill in the §3.4 table with new Snake results. Compare with paper Figure 18 data.

- [ ] **Step 3: Final commit with docs**

```bash
git add ima_plan/05_implementation/sota_baseline/paper_validation.md
git commit -m "docs: update Snake paper validation with refactored results"
```
