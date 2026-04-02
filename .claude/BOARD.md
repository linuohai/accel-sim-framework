# Session Board

> Last cleanup: 2026-03-30

## Active Sessions

| Session ID | Started | Focus | Editing | Status |
|------------|---------|-------|---------|--------|

## Notes

<!-- 最新在前，>24h 由下个 session 清理 -->
- **2026-04-02** Speculative stride 实现（默认 OFF）+ per-chain stride_hint CSV 列（SASS 分析）+ debug 方法学文档 + DSE 文档。CLAUDE.md 已注册 3 项新能力。chain CSV 新增 stride_hint 列。回归: BFS+3.6%, SSSP+3.2%, SpMV+6.8%, BC-8.6%。
- **2026-04-02** INDEX.md 已更新 (~260 行)：CAPS baseline 完成 + 输出规范 + 06/07 目录更新
- **2026-04-02** 新增实验输出规范 `06_evaluation_plan/output_specification.md`（展示/调试指标分级 + Index/Data/Total 三版本规则 + 报告模板）。后续实验报告须遵循。CLAUDE.md 已添加引用。
- **2026-04-01** CAPS baseline 已实现（`baseline_caps.{h,cc}`, `--baseline-caps`）+ IMA demand tracking 移植到 `exp/sota_stride` worktree（`last_probe_status()` fix）。Snake/CAPS v3 评估完成（12 logs in `result/log/*_v3.log`）。结果在 `sota_baseline/README.md`。
- **2026-03-31** INDEX.md 已更新 (~252 行)：新增 stride fix 里程碑 + E4 问题条目
- **2026-03-31** Stride 学习 bug 修复（3 处）：grasp_tables.cc stride freeze + grasp_prefetcher.cc warp exit cleanup + trace_driven.cc hook 补漏。experiment_progress §7f 已记录。回归测试待运行。
- **2026-03-31** `analyze_grasp_iterations_v2.py` 新增 `--iteration-mode bfs`：BFS 循环级 iteration 检测（boundary={0x01d0, 0x0640}, merge_window=300）。用法见 `grasp_real_diag/README.md` §4。

## Completed Today

| Session ID | Duration | Summary |
|------------|----------|---------|
| spec-stride-debug | ~6h | Speculative stride (default OFF, -grasp_speculative_stride) + per-chain stride_hint CSV + debug 方法学 (debug/README.md) + DSE 文档 + BFS 1SM root cause 分析 + CT reset 发现 + SASS stride 分析 |
| output-spec | ~1h | 审计全部 GRASP 指标 + 创建 output_specification.md（展示/调试分级 + 三版本规则 + 适用矩阵 + 报告模板）+ CLAUDE.md 注册 |
| caps-snake-eval | ~8h | CAPS 复现 (baseline_caps.{h,cc}, CAP+PAS+DIST persistence+self-CTA+kernel-transition-detect) + IMA demand tracking 移植到 worktree (last_probe_status fix) + Snake/CAPS 4-workload 评估 (v3 final: Snake BFS+0.17%~BC+2.96%, CAPS SpMV+14.3%) |
