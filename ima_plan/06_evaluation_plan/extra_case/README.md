# 扩展 Benchmark 实验记录

> 最近更新: 2026-04-07
> 目的: 验证 GRASP prefetcher 在 Gardenia 以外的 benchmark 上的泛化性
> 来源: Pannotia (MIS, Color) + LonestarGPU (MST, DMR, SP, PTA)

---

## 1. GRASP CSV impl 匹配 Bug（已修复）

**问题**: `trace_driven.cc` 中 `derive_impl_from_trace_path()` 从 trace 路径提取到 `impl="12.6"`（CUDA 版本号），导致 CSV 中 `impl="base"/"nsp"/"v2"` 的条目全部被过滤，pair table 未初始化。

**影响**: 所有新 benchmark 的 GRASP 仿真显示 `global_reads>0` 但 `pf_useful=0`（chain detector 在工作，但 pair table 未建立）。

**修复**:
- 将 `strict_selected_chain_instances.csv` 中所有新 benchmark 条目的 `impl` 列清空
- 第一批修复（2026-04-05 01:00）: `pann_mis,base` → `pann_mis,`, `pann_color,max` → `pann_color,`, `ls_mst,v2` → `ls_mst,`, `ls_dmr,v2` → `ls_dmr,`
- 第二批修复（2026-04-05 09:00）: `ls_sp,nsp` → `ls_sp,`（遗漏）
- 标记: 旧 log 后缀 `_grasp` 为 bug 版本，`_grasp2`/`_grasp3` 为修复版本

**附带发现**: `--max-completed-cta` flag 与 GRASP pair table 存在 use-after-free crash（`kernel_trace_t` 被提前释放），属于 Accel-Sim 预存 bug，不影响完整仿真。

---

## 2. 已完成实验结果

详细数据见 `extra_case_results.csv`。

### Pannotia MIS

| Key | 数据集 | 来源 | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | 说明 |
|-----|--------|------|--------:|----------:|--------:|-------:|--------:|-----:|------|
| pann_mis_flickr | flickr | SNAP | 121.94 | 156.14 | **+28.0** | 58.67 | 82.99 | 67.91 | 最佳结果，密集图 IMA 活跃 |
| pann_mis_cit | cit-Patents | SNAP | 604.91 | 604.47 | -0.1 | 31.96 | 77.97 | 34.72 | 84% prefetch 被 throttle 抑制 |
| pann_mis_eco | ecology1 | 自带 | 1067.85 | 1049.50 | -1.7 | 29.42 | 94.76 | 11.24 | Accuracy 极低(11%)，cache 污染 |
| pann_mis_g3 | G3_circuit | 自带 | 1024.82 | 1022.68 | -0.2 | 40.16 | 93.63 | 64.46 | 效果中性，Coverage 仅 1.9% |

### Pannotia Color

| Key | 数据集 | 来源 | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | 说明 |
|-----|--------|------|--------:|----------:|--------:|-------:|--------:|-----:|------|
| pann_color_eco | ecology1 | 自带 | 544.61 | 544.52 | -0.0 | 98.20 | 69.59 | 66.57 | Cov=24.9% 但 rfail 6.6% 抵消 |

### LonestarGPU MST

| Key | 数据集 | 来源 | Base IPC | GRASP IPC | Speedup% | 说明 |
|-----|--------|------|--------:|----------:|--------:|------|
| ls_mst_rmat12 | rmat12 | 自带 | 134.24 | 134.24 | +0.0 | **0pf**: CSV 仅有 `elim_dups` chain，但 rmat12 太小该 kernel 未执行 |

### LonestarGPU SP

| Key | 数据集 | 来源 | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | 说明 |
|-----|--------|------|--------:|----------:|--------:|-------:|--------:|-----:|------|
| ls_sp_42k5 | 42k×5 | 自带 | 662.37 | 572.71 | **-13.5** | 26.24 | 90.75 | 22.13 | 性能退化！rfail=30%, accuracy=22%, 84% throttled |

---

## 3. 0pf / 异常结果分析

### ls_mst_rmat12: 0 prefetch
- **原因**: CSV 中 MST 仅 1 条 chain（`elim_dups` kernel），但 rmat12 (4K nodes) 图太小，`elim_dups` 未被执行
- **运行的 kernel**: `dfindelemln`, `dfindcompmintwo`, `dinit`, `verify_min_elem` — 均不在 CSV 中
- **结论**: 数据集太小导致目标 kernel path 未覆盖

### ls_sp_42k5 (grasp2): 0 prefetch → grasp3 修复后有 prefetch 但性能退化
- **grasp2 0pf 原因**: CSV `impl=nsp` 未被清空（第二批修复遗漏）
- **grasp3 修复后**: 有 prefetch（1.05M useful）但 accuracy=22%，rfail=30%，84% data prefetch 被 throttle 抑制
- **性能退化 -13.5%**: GRASP 对 SP 的 IMA pattern 预测不准确（SP 是 SAT 求解，非图遍历，访问模式与 GRASP 设计目标不同）

### pann_mis_cit: 有 prefetch 但 0% speedup
- **早期误判**: 汇报脚本取到旧 `_grasp` log（broken CSV）导致显示 0pf
- **实际 grasp2 结果**: 有 3.0M pf_useful，但 Accuracy=34.7%，且 84% data prefetch 被 throttle 抑制
- **与 flickr 对比**: flickr 密集图（avg degree 8.25）IMA 数据更规律；cit-Patents 是引用网络（avg degree 4.3），不规则性更强

---

## 4. 运行中实验

| 算法 | 数据集 | Baseline | GRASP | 预估 |
|------|--------|:--------:|:-----:|------|
| MIS | web-Google | SLOW | SLOW | ~20h+ (大 kernel) |
| MIS | roadNet-CA | SLOW | SLOW | ~20h+ |
| Color | G3_circuit | RUN | RUN | 数小时 |
| Color | cit-Patents | RUN | RUN | ~48h (216 kernels) |
| Color | web-Google | SLOW | SLOW | ~24h+ |
| Color | roadNet-CA | SLOW | SLOW | ~12h+ |
| MST | USA-road-NY | RUN | RUN | 数小时 |
| MST | 2d-2e20 | RUN | RUN | 数小时 |
| MST | USA-road-FLA | RUN | RUN | 数小时 |
| MST | cit/web/flickr/road | RUN | RUN | 6-12h |
| DMR | 250k | SLOW | SLOW | ~48h (147G/进程) |
| SP | med (16.8K) | RUN | RUN | ~30h (1479 kernels) |
| PTA | ex | SLOW | SLOW | 数小时 |

---

## 5. 2026-04-07 LonestarGPU 深度调查 — 寻找 LS 提升测例

### 调查目标
找出 1-2 个 LonestarGPU 测例让 GRASP 展示 +speedup，避免大规模实验。

### 核心发现：5 个 LS 算法各有结构性 blocker

#### A. MST — chain 覆盖缺口（结构性）
- Golden CSV 只有 1 条 chain 在 `_Z9elim_dups...`
- 验证 `ls_mst_flickr_grasp2.log` kernel 序列：`dinit, dfindelemin, dfindelemin2, verify_min_elem, dfindcompmintwo` × N — **完全没有 elim_dups**
- `elim_dups` 只在有平行边的图触发；SNAP 都是已去重图
- 所有 MST 测例都是 0 prefetch（CT=0/32, idx_attempted=0）
- **修复成本**: 需 SASS 重新分析为 `dfindcompmintwo` 等主 kernel 提取 chain，超出时间窗口

#### B. DMR — chain 匹配但 data prefetch 从未触发（**关键 GRASP 限制**）
为快速验证创建了截断 trace 变体：
- `ls_dmr_25k_kc1`: 只含 kernel 1 (check_triangles, ~313K 行 trace)
- `ls_dmr_25k_kr28`: 只含 kernel 28 (refine 中最小, ~70M 行 trace)
- 用 `-gpgpu_max_cycle 50000` 跑 KR28 实现 5 分钟内完成

| 配置 | BL IPC | GRASP IPC | Speedup | idx_attempted | idx_rfail | data_enqueued |
|------|------:|---------:|--------:|-------------:|----------:|--------------:|
| KC1 完整跑(11189 cycles) | 602.19 | 602.19 | **+0.00%** | 24290 | 0 (0%) | **0** |
| KC1 + spec_stride 4 | 602.19 | 602.19 | +0.00% | 24290 | 0 | **0** |
| KR28 cycle≤50K | 465.04 | 464.76 | **-0.06%** | 42272 | 22644 (53.6%) | **0** |
| KR28 + spec_stride 4 | 465.04 | 464.76 | -0.06% | 42272 | 22644 | **0** |

**关键观察**:
1. GRASP **正确加载并匹配** DMR chain（KC1 24K + KR28 42K idx_attempted）
2. GRASP **正确减少 index miss**（KR28 上 32628→28375 = -13%）
3. 但 **data_enqueued 始终为 0** — 即使 chain 已检测、index 预取已发出、speculative stride 已开
4. 因此 data miss 几乎不变（112270→112262 = -0.007%），IPC 不变

**根因**: GRASP 在 DMR 上的 data prefetch unit (DPU) 没有触发。可能原因：
- DMR chain 的 data load 是 `LDG.E.64` (64-bit)，DPU 可能只处理 32-bit 数据
- 或 DPU 在 worklist-driven 算法上的某条路径未触发
- 这是 GRASP 内部 bug 而非配置问题，需源码调试

**修复成本**: 1-2 天源码 debugging

#### C. SP — compute-bound + cache pollution（多数据集均验证）
| 数据集 | BL IPC | GRASP | Speedup | 备注 |
|--------|------:|------:|--------:|------|
| ls_sp_42k5（grasp3）| 662.37 | 572.71 | -13.5% | acc 22%, throttle 84%, rfail 30% |
| ls_sp_med v2（前38/1479 kernel）| 568.13 | 534.93 | **-5.84%** | acc 41%, mshr_rfail 75% |
| ls_sp_med + T40C200（前 34/1479）| 568.13 | 549.58 | -3.27% | T40C200 缓解但仍负 |

- SP med 1479 kernels 完整跑需 ~60 小时
- compute-bound kernel (IPC ~980) GRASP 中性，memory-bound kernel (IPC ~470) GRASP 损害
- T40C200 throttle 略缓解 cache pollution 但本质问题仍在

#### D. PTA — kernel 名字不匹配（结构性）
- CSV 中 `_Z6gepInvv` 在实际二进制里**不存在**
- 实际运行的 kernel 是 `_Z8addEdgesPjS_S_jj` + 大量 CUB/thrust 模板 kernel（`cub::DeviceUniqueByKey`, `thrust::for_each` 等）
- 二进制使用 CUB 库实现替代了手写的 gepInv，CSV 是为旧版 andersen.cu 提取的
- **修复成本**: 需为 addEdges + 主要 CUB kernel 重做 SASS 分析

#### E. BH — CSV 零 chain
- 已知盲区，CSV 中 0 条 BH chain，无法启用任何 prefetch

### 结论：当前 5 个 LS 算法都没有"调一两个参数就能起效"的快速路径

| 算法 | 阻碍类型 | 修复成本 |
|------|---------|---------|
| MST | chain CSV 覆盖缺口 | SASS 重分析 `dfindcompmintwo` |
| DMR | data_enqueued=0 内部 bug | GRASP 源码 debug 1-2 天 |
| SP | compute-bound + cache pollution | 算法本身不适合（IPC > 500） |
| PTA | kernel name mismatch | SASS 重分析 + CUB kernel 适配 |
| BH | CSV 零 chain | 完整 SASS 提取 |

### 推荐后续路径（按 ROI 排序）

1. **DMR data_enqueued bug 调试** ★ 最高 ROI
   - DMR chain CSV 是正确的，accuracy 99%（partial 250k 数据），index miss 减少 13%
   - 一旦修好 data prefetch enqueue 路径，DMR 应能立即转正
   - 工具：`--grasp-debug` mode + 看 `effect: pf_useful=0 pf_useless=0 pf_late=0` 的产生条件

2. **MST `dfindcompmintwo` chain 提取** ★ 次高 ROI
   - MST flickr baseline IPC=96，是 LS 中最 memory-bound 的
   - 如果能为该 kernel 提取出 chain，理论上能复现 pann_mis_flickr (+28%) 的成功

3. **SP/PTA/BH** ★ 低优先
   - SP 算法本质 compute-bound，不是 GRASP 设计目标
   - PTA/BH 需要大量 SASS extraction 工作

### 创建的资产
- `generate_traces_dmr_25k.sh` - DMR 25k trace 生成脚本（5 iterations，~7GB 压缩 trace）
- `traceL1` 新增 TRACE_MAP 条目: `ls_dmr_25k`, `ls_dmr_25k_tiny`, `ls_dmr_25k_kc1`, `ls_dmr_25k_kr28`
- `hw_run/traces/.../ls_dmr_25k/`: 完整 28 kernel trace
- `hw_run/traces/.../ls_dmr_25k_kc1/`: kernel 1 only (90 秒可仿真)
- `hw_run/traces/.../ls_dmr_25k_kr28/`: kernel 28 only (5 min 配 cycle cap)

### 关键 logs
- `ls_dmr_kc1_baseline.log`, `ls_dmr_kc1_grasp.log`, `ls_dmr_kc1_gr_specstride.log`
- `ls_dmr_kr28_bl_50k.log`, `ls_dmr_kr28_gr_50k.log`, `ls_dmr_kr28_gr_50k_specstride.log`
- `ls_sp_med_bl_v2.log`, `ls_sp_med_grasp_default.log`, `ls_sp_med_grasp_t40c200.log`（killed at kernel 38/1479）

---

## 6. 文件说明

| 文件 | 说明 |
|------|------|
| `README.md` | 本文档 |
| `extra_case_results.csv` | 已完成实验的详细指标数据 |
| Golden CSV | `ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv` |
| GRASP logs | `result/log/{name}_{grasp2,grasp3}.log`（修复版）|
| Baseline logs | `result/log/{name}_baseline.log` |
| DMR 25k trace 生成 | `/workspace/prefetch/generate_traces_dmr_25k.sh` |
| 2026-04-07 调查 logs | `result/log/ls_dmr_kc1_*.log`, `ls_dmr_kr28_*.log`, `ls_sp_med_*_v2.log` |
