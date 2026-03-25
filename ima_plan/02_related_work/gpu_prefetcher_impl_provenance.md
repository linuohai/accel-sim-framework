# GPU Prefetcher 实现来源与 Baseline Provenance 调研

> 范围：`02_related_work.md` 中 GPU 侧 9 篇论文
>
> 调研日期：**2026-03-22**
>
> 方法：本地 PDF 抽取 + Web/GitHub 检索 + 本仓库 `gpu-simulator/` 现状核对

## 快速结论

1. **这 9 篇 GPU 论文里，我没有确认到任何一篇公开了 paper-specific 的 repo / artifact。**
2. **多数论文建立在开源 simulator 上（主要是 GPGPU-Sim 3.2.2，另有 MacSim 和 Accel-Sim），但提出的 prefetcher 本身和 evaluation baseline 通常是作者在 simulator 内自行实现的 patch，论文没有公开补丁。**
3. **后续论文拿来对比的 MTA / CTA-aware / SLD / APOGEE / Tree 等 baseline，基本都应视为“论文内重实现”，而不是直接复用公开代码。**
4. **我还检查了当前仓库的 `gpu-simulator/` 树，没有发现这些旧 GPU prefetcher 作为上游现成模块长期保留，这进一步支持“baseline 多为论文侧重实现”的判断。**

## 总表

| Paper | Eval stack | 提案实现是否公开 | 对比 baseline | Baseline provenance 判断 | 置信度 |
|---|---|---|---|---|---|
| [MT-Prefetch (MICRO'10)](<gpu/Lee 等 - 2010 - Many-Thread Aware Prefetching Mechanisms for GPGPU Applications.pdf>) | in-house trace-driven simulator | **未找到公开 repo / artifact** | RPT Stride, StridePC, Stream, AC/DC GHB | 论文明确同时评估 naive 与 warp-id enhanced 版本，说明这些 baseline 是作者在自家 simulator 里实现/改写，不是直接拿公开代码跑 | 中 |
| [COMPASS (ASPLOS'10)](<gpu/Woo和Lee - 2010 - COMPASS a programmable data prefetcher using idle GPU shaders.pdf>) | extended SESC CPU-GPU simulator | **未找到公开 patch / artifact** | baseline CPU with L2 next-line, conventional stride-GHB prefetchers | COMPASS 与 stride-GHB 都是在扩展后的 SESC 模型里对比；没有公开 patch 线索 | 中 |
| [Spare Register (HPCA'14)](<gpu/Lakshminarayana和Kim - 2014 - Spare register aware prefetching for graph algorithms on GPUs.pdf>) | MacSim timing simulator + custom GPU model | **提案 patch 未公开**；底层 simulator 公开：[MacSim][macsim] | Stride, Stream, GHB | 论文给出对比 prefetcher 配置表，说明这些 baseline 在作者的 MacSim 环境中实现；不是“直接复用现成 artifact” | 中高 |
| [Rethinking Prefetching in GPGPUs (~2014)](<gpu/Rethinking prefetching in GPGPUs - Exploiting unique opportunities.pdf>) | GPGPU-Sim 3.2.2 | **未找到公开 patch / artifact** | 无外部 prefetch baseline；主要是 no-prefetch + I/S/R machine models | 这篇重点是自定义 API + machine model；比较对象主要是理想/半理想/现实 machine，而不是复用已有开源 prefetcher | 高 |
| [DSAP (IEEE Access'18)](<gpu/Guo 等 - 2018 - Accelerating BFS via Data Structure-Aware Prefetching on GPU.pdf>) | GPGPU-Sim 3.2.2 + GPUWattch | **未找到公开 patch / artifact**；底层 simulator 公开：[GPGPU-Sim][gpgpusim] | Next Line, stride-based GHB | 论文明确写到“在 GPGPU-Sim 上实现了 Next Line 和 stride-based GHB”，因此 baseline provenance 是**作者在同一 simulator 里重实现** | 高 |
| [CAPS (IPDPS'18)](<gpu/Koo 等 - 2018 - CTA-Aware Prefetching and Scheduling for GPU.pdf>) | GPGPU-Sim 3.2.2 | **未找到公开 patch / artifact**；底层 simulator 公开：[GPGPU-Sim][gpgpusim] | INTRA, INTER, MTA, NLP, LAP, ORCH | 论文明确说这些 prefetching methods 都被实现来做比较，且对 MTA 还特别说明是实现了其中的 hardware-based 版本 | 高 |
| [WASP (IEEE TC'18)](<gpu/WASP_Selective_Data_Prefetching_with_Monitoring_Runtime_Warp_Progress_on_GPUs.pdf>) | GPGPU-Sim 3.2.2 | **未找到公开 patch / artifact**；底层 simulator 公开：[GPGPU-Sim][gpgpusim] | MTA, SLD, APOGEE | 论文写明 “used MTA and SLD” 且 “modeled APOGEE”；整体应归类为**作者在同一模拟环境中的对比实现** | 高 |
| [Stream Data Prefetcher (J. Supercomputing'18)](<gpu/Neves 等 - 2018 - Stream data prefetcher for the GPU memory interface.pdf>) | GPGPU-Sim 3.2.2 + GPUWattch | **未找到公开 patch / artifact**；底层 simulator 公开：[GPGPU-Sim][gpgpusim] | 主要是 no-prefetch baseline | 主评测基本是“baseline architecture vs proposed stream prefetching architecture”；没有成体系复用别的公开 prefetch baseline | 高 |
| [Snake (MICRO'23)](<gpu/Mostofi 等 - 2023 - Snake A Variable-length Chain-based Prefetching for GPUs.pdf>) | Accel-Sim v1.2.0 + AccelWattch v1.0 | **未找到公开 patch / artifact**；底层 simulator 公开：[Accel-Sim][accelsim] | INTRA, INTER, MTA, CTA, Tree, 以及若干 ablation | 论文直接写 `MTA is a hardware implementation`、`CTA is an implementation`、`Tree ... We adopt this work in the GPU context`，因此 baseline 是**作者在 Accel-Sim 中实现/适配**，不是上游现成模块 | 高 |

## 分论文细化

### 1. MT-Prefetching (MICRO 2010)

- **实现公开性**：未找到公开 repo 或 artifact。
- **论文内实现栈**：作者使用 **in-house cycle-accurate, trace-driven simulator**。
- **evaluation baseline**：
  - `Stride`（RPT stride）
  - `StridePC`
  - `Stream`
  - `GHB`（AC/DC GHB）
- **baseline provenance 判断**：
  - 论文不只是“引用这些 baseline”，而是明确对每个 baseline 同时评估了 `naive` 和 `enhanced warp-id indexing` 版本。
  - 这意味着 baseline 实现是作者在自家 simulator 中自己写的/改的，不是调用现成公开模块。

### 2. COMPASS (ASPLOS 2010)

- **实现公开性**：未找到公开 patch / artifact。
- **论文内实现栈**：作者写明是 **extending the SESC simulator**，并集成了 CPU-GPU 平台建模。
- **evaluation baseline**：
  - `baseline CPU with L2 next-line prefetcher`
  - `hardware stride GHB prefetchers`
- **baseline provenance 判断**：
  - 这些 baseline 与 COMPASS 一样，都在扩展后的 SESC 平台里建模。
  - 论文没有给出公开 patch，因此应归类为**论文侧 simulator modeling**。

### 3. Spare Register Aware Prefetching (HPCA 2014)

- **实现公开性**：
  - 论文方案本身：未找到公开 patch / artifact。
  - 底层 simulator：`MacSim` 是公开项目，[MacSim][macsim]。
- **论文内实现栈**：`MacSim` heterogeneous architecture simulator。
- **evaluation baseline**：
  - `Stride`
  - `Stream`
  - `GHB`
- **baseline provenance 判断**：
  - 论文给出了对比 prefetcher 的配置表，并说明这些 baseline 在 L1/L2 access stream 上训练。
  - 更合理的判断是：作者在 MacSim 内实现了这些 baseline；**不是从论文公开 artifact 直接拿来的**。

### 4. Rethinking Prefetching in GPGPUs

- **实现公开性**：未找到公开 patch / artifact。
- **论文内实现栈**：
  - `GPGPU-Sim 3.2.2`
  - 通过静态分析器 + 手工注入 `cudaSetCTATracker()` 一类 API 到 benchmark source。
- **evaluation baseline**：
  - 主要是 `no-prefetch baseline`
  - 外加 `I-Machine / S-Machine / R-Machine` 三种 machine model
- **baseline provenance 判断**：
  - 这篇并没有系统性复用外部 GPU prefetcher baseline。
  - 比较对象本质上是作者自己构造的理想化/半理想化/现实 machine model。

### 5. DSAP (IEEE Access 2018)

- **实现公开性**：
  - 论文方案本身：未找到公开 patch / artifact。
  - 底层 simulator：`GPGPU-Sim` 公开，[GPGPU-Sim][gpgpusim]。
- **论文内实现栈**：`GPGPU-Sim 3.2.2 + GPUWattch`。
- **evaluation baseline**：
  - `Next Line prefetcher`
  - `stride-based GHB prefetcher`
- **baseline provenance 判断**：
  - 论文原文直接写：**“We implement a Next Line prefetcher and a stride-based GHB prefetcher on GPGPU-Sim”**。
  - 所以这里不是“用了别人开源 baseline”，而是**作者自己在 GPGPU-Sim 上实现的对照组**。

### 6. CAPS (IPDPS 2018)

- **实现公开性**：
  - 论文方案本身：未找到公开 patch / artifact。
  - 底层 simulator：`GPGPU-Sim` 公开，[GPGPU-Sim][gpgpusim]。
- **论文内实现栈**：`GPGPU-Sim 3.2.2`。
- **evaluation baseline**：
  - `INTRA`
  - `INTER`
  - `MTA`
  - `NLP`（next-line prefetcher）
  - `LAP`
  - `ORCH`
- **baseline provenance 判断**：
  - 论文写明“prefetching methods are implemented to compare the relative performance benefits of CAPS”。
  - 对 `MTA` 还补了一句：**实现的是 [9] 里各种机制中的 hardware-based 版本**。
  - 因此这些 baseline 都应看成**CAPS 论文作者在 GPGPU-Sim 中重实现的 comparison points**。

### 7. WASP (IEEE TC 2018)

- **实现公开性**：
  - 论文方案本身：未找到公开 patch / artifact。
  - 底层 simulator：`GPGPU-Sim` 公开，[GPGPU-Sim][gpgpusim]。
- **论文内实现栈**：`GPGPU-Sim 3.2.2`。
- **evaluation baseline**：
  - `MTA`
  - `SLD`
  - `APOGEE`
- **baseline provenance 判断**：
  - 论文写明：`We used MTA and SLD`，并且 `we modeled one more prefetching scheme, called APOGEE`。
  - 这说明至少 `APOGEE` 是作者在本论文环境里建模出来的。
  - 结合没有发现公开 patch 的事实，整个 baseline 组最稳妥的分类是：**paper-side reimplementation/modeling**。

### 8. Stream Data Prefetcher (Journal of Supercomputing 2018)

- **实现公开性**：
  - 论文方案本身：未找到公开 patch / artifact。
  - 底层 simulator：`GPGPU-Sim` 公开，[GPGPU-Sim][gpgpusim]。
- **论文内实现栈**：`GPGPU-Sim 3.2.2 + GPUWattch`。
- **evaluation baseline**：
  - 主要是**未加 prefetch 的 baseline architecture**
- **baseline provenance 判断**：
  - 这篇工作的比较重点不是“和一串已有 GPU prefetcher 横向打擂台”，而是“pattern-encoded stream prefetching architecture”相对 baseline 的收益。
  - 因此没有明显的“来自开源代码库的 baseline prefetcher”问题。

### 9. Snake (MICRO 2023)

- **实现公开性**：
  - 论文方案本身：未找到公开 patch / artifact。
  - 底层 simulator：`Accel-Sim` 公开，[Accel-Sim][accelsim]。
- **论文内实现栈**：`Accel-Sim v1.2.0 + AccelWattch v1.0`。
- **evaluation baseline**：
  - `INTRA`
  - `INTER`
  - `MTA`
  - `CTA`
  - `Tree`
  - 以及 `s-Snake / Snake-DT / Snake-T / Snake+CTA` 等 ablation
- **baseline provenance 判断**：
  - 论文原文非常直接：
    - `MTA is a hardware implementation`
    - `CTA is an implementation`
    - `Tree ... We adopt this work in the GPU context`
  - 这三句话几乎已经明示：**baseline 是作者在 Snake 的 Accel-Sim 环境里实现或适配出来的**。
  - 我没有找到配套公开 patch，也没有在当前 Accel-Sim 树里看到这些 baseline 作为上游现成模块长期保留。

## 横向基线矩阵

| Baseline 名称 | 在这些论文里的典型来源 | 我能确认的公开性 | 备注 |
|---|---|---|---|
| `next-line / NLP` | 论文作者在 simulator 内实现的简单对照组 | 没有必要单独找 repo；通常是 paper-side baseline | DSAP、CAPS 都是这种用法 |
| `Stride / StridePC / RPT / Stream / GHB` | 通常是作者在 simulator 内实现的 CPU 风格 baseline | **未看到这些 GPU 论文直接引用公开 patch** | MTA、Spare Register、DSAP 都是自己在模拟器里接入 |
| `INTRA / INTER` | CAPS、Snake 中的轻量 comparison point | 本质是 paper-side implementation | 常作为 warp-level stride baseline |
| `MTA` | 原始论文未找到公开 repo；后续论文各自重实现 | **未确认到公开 artifact** | CAPS、WASP、Snake 都把它当“自己实现的 comparison point” |
| `CTA / CTA-aware` | CAPS 原始方案；Snake 中重新实现 | **未确认到公开 artifact** | Snake 明写 `CTA is an implementation` |
| `SLD / APOGEE` | WASP 中的 comparison point | **未确认到公开 artifact** | WASP 至少对 APOGEE 明写是“modeled” |
| `LAP / ORCH` | CAPS comparison point | **未确认到公开 artifact** | 更像论文内建模/重实现 |
| `Tree` | Snake 将 CPU-GPU spatial prefetcher 适配到 GPU context | **未确认到公开 artifact** | Snake 明写 `We adopt this work in the GPU context` |

## 对你后续写 related work / evaluation 的直接建议

1. **不要把这些 baseline 写成“用了开源实现”**，除非论文明确给出 artifact/repo。
2. 更稳妥的表述是：
   - `implemented on top of GPGPU-Sim / Accel-Sim / MacSim`
   - `the compared baselines were modeled / reimplemented in the same simulator`
3. 只有底层 simulator 本身可以明确写成开源：
   - `GPGPU-Sim`：[gpgpu-sim/gpgpu-sim_distribution][gpgpusim]
   - `Accel-Sim`：[accel-sim/accel-sim-framework][accelsim]
   - `MacSim`：[gthparch/macsim][macsim]
4. 如果你后面要做自己论文的 baseline 复现，**最现实的路径仍然是自己在 Accel-Sim / GPGPU-Sim 里重实现**，不要预期能直接找到这些老论文的可运行 patch。

[gpgpusim]: https://github.com/gpgpu-sim/gpgpu-sim_distribution
[accelsim]: https://github.com/accel-sim/accel-sim-framework
[macsim]: https://github.com/gthparch/macsim
