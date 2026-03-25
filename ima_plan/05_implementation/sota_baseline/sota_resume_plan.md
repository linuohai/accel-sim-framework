# SOTA Baseline Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume SOTA baseline implementation from a cold start without relying on chat history, starting with `INTRA/INTER` plus the `traceL1` chain-CSV plumbing needed for baseline runs.

**Architecture:** Keep `/workspace/prefetch` as the reference area, write no simulator logic here, and execute real implementation in an isolated worktree. Phase 1 lands only the shared baseline framework needed by `INTRA/INTER`, plus the `traceL1` entry fix that lets baseline runs consume strict chain CSV input. Existing strict chain and `ima_pair_table` artifacts remain inputs, not targets of change.

**Tech Stack:** Bash (`traceL1`), C++ in GPGPU-Sim / Accel-Sim, existing trace-driven strict-chain loader, repo-local markdown handoff docs.

---

## File Map

### Documents created in this resume pass

- Create: `ima_plan/05_implementation/sota_resume_design.md`
- Create: `ima_plan/05_implementation/sota_resume_plan.md`

### Files expected for Phase 1 implementation

- Modify: `traceL1`
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.h`
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc`
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc`
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.h`
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.cc`
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_stride.h`
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_stride.cc`
- Modify: `gpu-simulator/CMakeLists.txt`

### Reference inputs only

- Read-only: `ima_plan/05_implementation/sota_impl_spec.md`
- Read-only: `ima_plan/05_implementation/ima_pair_table/agent_handoff_status.md`
- Read-only: `ima_plan/05_implementation/ima_pair_table/validation_status.md`
- Read-only: `gpu-simulator/trace-driven/trace_driven.cc`

## Task 1: Establish an Isolated Execution Workspace

**Files:**
- Modify: `.gitignore` only if needed to ignore `worktrees/`
- Create: `/workspace/prefetch/worktrees/sota_stride` via `git worktree`

- [ ] **Step 1: Verify the preferred worktree root**

Run: `ls -d /workspace/prefetch/worktrees 2>/dev/null || true`
Expected: if missing, still use `/workspace/prefetch/worktrees` because `sota_impl_spec.md` explicitly standardizes that path.

- [ ] **Step 2: Verify whether `worktrees/` is ignored**

Run: `git -C /workspace/prefetch check-ignore -q worktrees; echo $?`
Expected: `0` means ignored, `1` means not ignored yet.

- [ ] **Step 3: If needed, add `worktrees/` to ignore rules**

Implementation:
- Add a single `worktrees/` entry to the repository ignore file used by the project.
- Do not touch unrelated ignore patterns.

- [ ] **Step 4: Create the Phase 1 worktree**

Run:

```bash
git -C /workspace/prefetch worktree add /workspace/prefetch/worktrees/sota_stride -b exp/sota_stride
```

Expected: a clean isolated worktree on branch `exp/sota_stride`.

- [ ] **Step 5: Capture baseline status before coding**

Run in the new worktree:

```bash
git status --short
```

Expected: empty status in the worktree before edits start.

## Task 2: Fix `traceL1` Baseline Chain-CSV Plumbing

**Files:**
- Modify: `traceL1`

- [ ] **Step 1: Add a shared baseline/GRASP chain CSV variable**

Implementation:
- Introduce a single chain-CSV variable near the existing GRASP CLI state.
- Default it to `tmp/strict_chains/strict_selected_chain_instances.csv`.
- Keep `--grasp-chain-csv` as the external override until a baseline-specific option is actually needed.

- [ ] **Step 2: Apply chain CSV to baseline runs as well as GRASP**

Implementation:
- Preserve existing GRASP behavior.
- When any baseline prefetcher is enabled, write `-gpgpu_ima_prefetch_chain_csv "<path>"` into the generated temp config.
- Keep current one-hot checks between GRASP and baselines.

- [ ] **Step 3: Surface missing-file warnings consistently**

Implementation:
- If the configured chain CSV does not exist, print a warning for baseline runs just like GRASP runs.
- Do not fail hard at this stage.

- [ ] **Step 4: Verify generated config contains the option**

Run:

```bash
./traceL1 -c SM80_A100_1SM --baseline-intra --no-issue-trace --no-l1-trace --no-l2-trace --no-hbm-trace --max-cycle 1 bfs_ima_small trace_cfg_probe
```

Expected:
- The run may terminate almost immediately.
- The emitted config or log should show `-gpgpu_ima_prefetch_chain_csv` with the strict-chain CSV path.

## Task 3: Land the Shared Baseline Prefetcher Framework

**Files:**
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.h`
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_prefetcher.cc`
- Modify: `gpu-simulator/CMakeLists.txt`
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc`
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.h`
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc`

- [ ] **Step 1: Define a minimal base class for SOTA baselines**

Implementation:
- Add a small abstract base class with lifecycle hooks used by `INTRA/INTER`.
- Include only what Phase 1 needs: demand-load observation, prefetch injection queueing, stats printing, reset, and optional warp-exit cleanup.
- Do not pre-design all `Snake`/`Spare Register` complexity here.

- [ ] **Step 2: Register Phase 1 config flags**

Implementation:
- Add `-baseline_intra_enable`
- Add `-baseline_inter_enable`
- Add stride-table sizing and confidence parameters from `sota_impl_spec.md`
- Keep flags off by default

- [ ] **Step 3: Instantiate the baseline framework in the same hook neighborhood as GRASP**

Implementation:
- Reuse the hook locations documented in `sota_impl_spec.md`
- Avoid changing unrelated GRASP behavior
- Keep one-hot behavior between GRASP and baselines

- [ ] **Step 4: Add end-of-run stats printing**

Implementation:
- Print the baseline counters required by `sota_impl_spec.md`
- If a metric is not fully meaningful in Phase 1 yet, still define the field and print a conservative value rather than silently omitting it

## Task 4: Implement `baseline_stride` for `INTRA/INTER`

**Files:**
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_stride.h`
- Create: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/baseline_stride.cc`

- [ ] **Step 1: Implement the stride table and mode split**

Implementation:
- One class `baseline_stride_prefetcher_t`
- Two modes: `INTRA_WARP`, `INTER_WARP`
- Table shape and confidence behavior follow `sota_impl_spec.md`

- [ ] **Step 2: Implement demand-side observation**

Implementation:
- On eligible demand load arrival, update stride state
- When confidence reaches threshold, queue the predicted prefetch line
- Keep degree support, defaulting to 1

- [ ] **Step 3: Gate training/prediction with existing IMA seed information**

Implementation:
- Use the existing warp/trace-driven seed interface where available to filter out non-IMA PCs
- Treat this as project-level IMA scope control, not a new baseline optimization
- If no seed information is available for a warp/PC, fail closed rather than training on all loads

- [ ] **Step 4: Clear stale per-warp state on warp exit**

Implementation:
- Ensure recycled warp slots do not retain old intra-warp history
- Only clear the state that is actually warp-specific

- [ ] **Step 5: Reuse the existing L1 injection path**

Implementation:
- Follow the same or adjacent path already used by GRASP for fair timing placement
- Drop on `RESERVATION_FAIL`
- Do not add retry logic or adaptive throttling in Phase 1

## Task 5: Build and Smoke Test Phase 1

**Files:**
- No new source files beyond earlier tasks

- [ ] **Step 1: Rebuild in the worktree**

Run:

```bash
source ./gpu-simulator/setup_environment.sh release
make -j -C ./gpu-simulator/
```

Expected: successful build of `./gpu-simulator/bin/release/accel-sim.out`.

- [ ] **Step 2: Run no-prefetch smoke**

Run:

```bash
./traceL1 -c SM80_A100_1SM --no-issue-trace --no-l1-trace --no-l2-trace --no-hbm-trace --max-cycle 80000 bfs_ima_small smoke_np
```

Expected: completes without baseline stats enabled.

- [ ] **Step 3: Run `INTRA` smoke**

Run:

```bash
./traceL1 -c SM80_A100_1SM --baseline-intra --no-issue-trace --no-l1-trace --no-l2-trace --no-hbm-trace --max-cycle 80000 bfs_ima_small smoke_intra
```

Expected:
- completes successfully
- logs show `-gpgpu_ima_prefetch_chain_csv`
- baseline intra stats print at shutdown

- [ ] **Step 4: Run `INTER` smoke**

Run:

```bash
./traceL1 -c SM80_A100_1SM --baseline-inter --no-issue-trace --no-l1-trace --no-l2-trace --no-hbm-trace --max-cycle 80000 bfs_ima_small smoke_inter
```

Expected:
- completes successfully
- logs show `-gpgpu_ima_prefetch_chain_csv`
- baseline inter stats print at shutdown

- [ ] **Step 5: Check isolation behavior**

Run:

```bash
./traceL1 -c SM80_A100_1SM --baseline-intra --grasp bfs_ima_small should_fail
```

Expected: immediate one-hot configuration failure, not a silent mixed run.

## Task 6: Persist Phase 1 Results Back Into Handoff Docs

**Files:**
- Modify: `ima_plan/05_implementation/experiment_progress.md` if Phase 1 runs are meaningful
- Create or modify: `ima_plan/05_implementation/` handoff note for SOTA baseline progress

- [ ] **Step 1: Record what was actually implemented**

Implementation:
- list landed files
- list which `sota_impl_spec.md` requirements are done
- explicitly state that `Snake` and `Spare Register` are still pending

- [ ] **Step 2: Record smoke-test evidence**

Implementation:
- store commands used
- store whether prefetches were observed
- separate “plumbing works” from “performance useful”

- [ ] **Step 3: Record the next blocker**

Implementation:
- if `INTRA/INTER` remain at `prefetch_issued=0`, document whether the blocker is timeliness, seed filtering, workload window, or hook placement
- make the next action explicit so a future session does not need to reconstruct it

## Exit Criteria for This Plan

- `traceL1` baseline runs consume strict chain CSV input
- `INTRA/INTER` compile and run through smoke tests
- required Phase 1 stats print at shutdown
- GRASP/baseline one-hot checks remain enforced
- Phase 1 outcome is written back into repo documentation so the next session does not depend on chat history
