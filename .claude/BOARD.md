# Session Board

> Last cleanup: 2026-03-30

## Active Sessions

| Session ID | Started | Focus | Editing | Status |
|------------|---------|-------|---------|--------|

## Notes

<!-- 最新在前，>24h 由下个 session 清理 -->
- **2026-04-08** **§4 Methodology LaTeX 写入**：根据 `.claude_global/plans/replicated-chasing-pizza.md` 把 4 个 block (Simulation / Benchmarks / Comparison Points / Metrics) 写到 main.tex 1106 行的占位符。新增 Table 7 (Algorithms 9 行) 到 table_templates.tex，复用 Template 3 (Datasets)。新增 Khairy ISPASS'20 + Che IISWC'13 bib。基线列表收紧到 4 个：No Prefetch / Snake / CAPS / Spare Register（**Ideal L1D 不进 baseline，作为 §5 reference**）。Metrics 显式分开 Accuracy 和 Timeliness（counter-Snake）。
- **2026-04-08** 正在更新 INDEX.md (session: 敏感性分析补充)
- **2026-04-07** **⚠️ POE API 格式更新 + paper-illustration SKILL.md 修正**: SKILL.md 的 API 请求模板过时了（`image_only`/`aspect_ratio`/`image_size` 直接作为顶层字段）——这会返回 `SSL_read: unexpected eof`（curl exit 35/56），容易被误判为 rate limiting。**正确格式**：POE OpenAI-兼容 API 要求所有自定义参数放在 `extra_body: {aspect, size}` 内。另发现：**`nano-banana-pro` 原生固定 1408×768，静默忽略 `size` 参数**；要 4K 必须用 `nano-banana-2`（有时限流）或 PIL LANCZOS 本地升采样。SKILL.md 已更新：新增 API Error Diagnostics 表 + 三模型分工策略 + Step 4b LANCZOS fallback。参考：https://creator.poe.com/docs/external-applications/openai-compatible-api
- **2026-04-07** **§5.5 Effectiveness Prototypes (5 figs)**: `eval_prototypes/proto_r2_e[1-5]_*.py` 完成。E1 IMA miss reduction（配对堆叠条），E2 pipeline funnel（横向 6-bucket 堆叠条），E3 CT reuse（log x 横向条，CT-size 着色），E4 stall reduction（配对堆叠条 MEM_WAIT vs Other），E5 IMA→speedup correlation（散点 + 回归 r=+0.642 R²=0.41）。数据源 effectiveness_data.json。视觉迭代修复 4 类问题（title/legend overlap、白文字溢出、y_lim 不足、outlier label 重叠）。详见 experiment_progress §7l。
- **2026-04-05** **Bug-Fix & Spec Stride 大规模评估完成**：76 实验（38 G1 bug-fix + 38 G2 spec-stride）全部完成。Chain CSV 更新（CC 5 + VC 29 条 stride_hint）。traceL1 新增 `--grasp-speculative-stride N`。关键发现: bug-fix 在 road_sym +2.5~5.0% 但 CC flickr -19.4%/SpMV 全线 -0.9~-3.3%（accuracy 暴跌）; spec stride 在 cc_flickr +23.6% 补偿但 cc_web -4.1%。详见 `experiment_bugfix_specstride.md`。
- **2026-04-04** **新 Benchmark 测例扩展 (Pannotia + LonestarGPU)**：新增 5 个算法（MIS, Color, SP, DMR, MST）。SNAP 数据集格式转换（MTX→METIS+Galois .gr）。SM80 编译完成。14 个 NVBit trace 生成（8 GPU 并行）。Golden CSV 扩展 105→205 chains。提取器 IMAD.WIDE.U32 bug 修复。Pannotia parser 8KB→1MB buffer 修复。traceL1 新增 17 个 TRACE_MAP 条目。**已知 blocker**: GRASP CD `global_reads=0`（新 benchmark 上 chain 未被检测）+ debug 模式 segfault（mis2 kernel）。Baseline 仿真部分完成。BH 因 A100 架构不兼容放弃。
- **2026-04-04** INDEX.md 已更新 (~270 行)：新 Benchmark 扩展汇总（MIS/Color/SP/DMR/MST, 205 chains）+ GRASP CD blocker 记录 + IMAD.WIDE.U32 fix + 01/05/06 目录详情更新
- **2026-04-04** INDEX.md 已更新 (~254 行)：Coverage% 全补齐（experiment_results.md 无"需重跑"）+ writing_rules/ 体系（7 §指南）+ 写作计划顺序更新 + Phase 06/07 状态刷新
- **2026-04-04** **论文大纲定稿 + §1 Introduction 重构**: paper_structure.md 创建（§1-§7 完整大纲 + 21fig + 4tab）; 基于 9 篇 CCF-A 论文结构分析; §1 Introduction 从钳形闭合改为 GPU-centric 线性 7 步流程; 图表预算 17→21; abstract.md 评估范围更新; INDEX.md 增量更新。
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
| methodology-§4-write | ~1h | §4 Methodology LaTeX 写入：4 个 block (Simulation / Benchmarks / Comparison Points / Metrics) 写到 main.tex 1106-1180. 新增 Template 7 (tab:algorithms) 到 table_templates.tex. 新增 Khairy ISPASS'20 + Che IISWC'13 bib. Baseline 收紧到 4 个 (No Prefetch / Snake / CAPS / Spare Register), Ideal L1D 不进 baseline. Metrics 显式分开 Accuracy 和 Timeliness. latexmk 编译通过 (12 pages = 10 body + 2 refs). paper_structure.md §4 状态 → [已细化], 顺手修正 32KB→128KB 的笔误. |
| spec-stride-debug | ~6h | Speculative stride (default OFF, -grasp_speculative_stride) + per-chain stride_hint CSV + debug 方法学 (debug/README.md) + DSE 文档 + BFS 1SM root cause 分析 + CT reset 发现 + SASS stride 分析 |
| output-spec | ~1h | 审计全部 GRASP 指标 + 创建 output_specification.md（展示/调试分级 + 三版本规则 + 适用矩阵 + 报告模板）+ CLAUDE.md 注册 |
| caps-snake-eval | ~8h | CAPS 复现 (baseline_caps.{h,cc}, CAP+PAS+DIST persistence+self-CTA+kernel-transition-detect) + IMA demand tracking 移植到 worktree (last_probe_status fix) + Snake/CAPS 4-workload 评估 (v3 final: Snake BFS+0.17%~BC+2.96%, CAPS SpMV+14.3%) |
