# Session Board

> Last cleanup: 2026-03-30

## Active Sessions

| Session ID | Started | Focus | Editing | Status |
|------------|---------|-------|---------|--------|

## Notes

<!-- 最新在前，>24h 由下个 session 清理 -->
- **2026-04-03** INDEX.md 已更新 (~249 行)：Throttle DSE 完成 (T40C200 推荐) + PR 移除 (7->6 算法) + E3 已修复 + tc_mode=0 legacy 声明 + dse_throttle_control/ 完整记录
- **2026-04-03** **Throttle Control DSE 完成**: tc_mode=4 (Cooldown Timer) 框架实现 + 9-workload 验证。推荐 T40C200 (thr=40, cd=200)：SpMV +3.47%, BFS/SSSP +0.37-0.39%, 0/9 退化。新增: `dse_throttle_control/` 文档+CSV、traceL1 `--sim-args` passthrough、dse_ct_reset_policy.md §3。CLAUDE.md 已注册 Throttle Cooldown + Sim Args。回归测试未跑（代码改动未提交）。
- **2026-04-03** Accuracy 修正为 108-SM 聚合值（experiment_results.md 32 条 + traceL1 EXPERIMENT SUMMARY 全部指标从 SM0→All SMs）。CLAUDE.md 已同步更新。
- **2026-04-03** INDEX.md 已更新 (~250 行)：paper_structure.md 权威大纲 + throttle DSE 启动 + Phase 07 状态更新
- **2026-04-02** INDEX.md 已更新 (~246 行)：7h L1 MQ/MSHR 容量探索结论（不是瓶颈）+ E7 排除 + accuracy/PT miss 作为下一步方向 + GRASP_L1MQ 输出 + infmq legacy 声明 + EVICT 事件处理
- **2026-04-02** **数据集选择 + 大规模评估**：4 类图（cit-Patents/web-Google/flickr/roadNet-CA）+ soc-LJ1 扩展。7 算法（移除 SymGS）× 双变体。生成 28 NVBit traces。跑 ~140 实验（baseline+GRASP+ideal）。ideal L1D 改 load-only。新文档: experiment_results.md（唯一数据源）、experiment_timing.md（耗时参考）。CLAUDE.md 已注册。traceL1 统一命名 `{algo}_{dataset}_{dir|sym}`。
- **2026-04-02** fix(grasp): CT kernel reset 用 name 比较代替 pointer 比较（trace-driven 下 same_kernel 永远 false）+ CD FIFO push 回收 invalid slot + DEMAND_CT_MISS trace + L1 evict trace。回归: BFS+3.6%, SSSP+3.2%, SpMV+6.8%（BC-8.6% 是 spec_stride 配置不一致，非本次引入）。debug/README.md 新增结构性 miss 分类 + 归因陷阱说明。
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
