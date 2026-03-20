# IMA Tiny Case

`tiny_case/` 现在按 **trace bundle** 来组织，不再把 trace、metadata、图和 summary 直接散落在当前目录根下。

## 目标

- 用单 SM、`1 CTA x 8 warps` 的独立 IMA 微基准观察 warp 交织
- 用固定的 `warmup -> IMA region -> tail` 结构观察 IMA 段如何影响 warp 发射
- 让每一份 trace 都有自包含的归档目录，后续 debug prefetcher 时不需要再回溯外部源码或 cubin

## 默认实验设定

- benchmark: `ima_tiny_case`
- kernel structure: `warmup -> IMA region -> tail`
- default launch: `1 CTA x 8 warps`
- base config: `SM80_A100_1SM_NOSUBCORE`
- prefetch config: `SM80_A100_1SM_NOSUBCORE_IMAPF`
- 默认图片格式：`svg`
- 默认绘图模式：`gantt`

这里保留 8 个 warp，是为了让单 SM 下的 warp 交织问题足够明显。

## 参数与 bundle 命名

CLI 参数：

- `--ctas`
- `--warps-per-cta`
- `--warmup-iters`
- `--ima-iters`
- `--tail-iters`
- `--data-lines`
- `--mapping-seed`
- `--compute-gap`

trace 阶段仍然走 `NO_ARGS`，所以 benchmark 也接受环境变量覆盖：

- `IMA_TINY_CTAS`
- `IMA_TINY_WARPS_PER_CTA`
- `IMA_TINY_WARMUP_ITERS`
- `IMA_TINY_IMA_ITERS`
- `IMA_TINY_TAIL_ITERS`
- `IMA_TINY_DATA_LINES`
- `IMA_TINY_MAPPING_SEED`
- `IMA_TINY_COMPUTE_GAP`
- `IMA_TINY_METADATA_OUT`

每组 tiny 参数会映射到一个固定 bundle 目录名：

```text
cta<ctas>_w<warps>_wu<warmup>_ima<ima>_tail<tail>_dl<data_lines>_seed<seed>_gap<gap>
```

例如：

```text
cta1_w8_wu256_ima4096_tail256_dl2048_seed1_gap8
```

## Bundle 目录结构

所有 bundle 放在：

```text
ima_plan/04_prefetcher_design/tiny_case/trace_bundles/
```

单个 bundle 的结构固定为：

```text
trace_bundles/<bundle_id>/
├── metadata/
│   ├── config.json
│   └── trace_metadata.json
├── native/
│   ├── <log>_native_stdout.txt
│   └── <log>_native_metadata.json
├── src/
│   └── ima_tiny_case.cu
├── sass/
│   ├── *.sass
│   └── *.static_map.csv
├── trace/
│   ├── run.sh
│   ├── run_spinlock_detection.sh
│   └── traces/
│       ├── kernelslist.g
│       ├── *.trace.xz
│       ├── *.traceg.xz
│       ├── *.cubin
│       └── *.static_map.csv
├── sim/
│   ├── base_lrr/
│   ├── base_gto/
│   ├── pf_lrr/
│   └── pf_gto/
└── analysis/
    ├── phase_summary_<label>.csv
    ├── ima_region_summary_<label>.csv
    ├── warp_load_events_<label>.csv
    ├── warp_load_sectors_<label>.csv
    ├── prefetch_compare.csv
    └── figures/
        └── warp_gantt_<label>.svg
```

关键规则：

- 一个 bundle 只对应 **一组 tiny 参数**
- `lrr/gto` 与 `baseline/prefetch` **共用同一份 trace**
- bundle 内必须保存 **CUDA 源码快照**
- bundle 内必须保存 **SASS 快照**

这里的 `src/ima_tiny_case.cu` 和 `sass/*.sass` 都是复制快照，不是软链接。

## Metadata 契约

benchmark 会在 traced run 工作目录里生成 `./ima_tiny_case_metadata.json`，runner 会把它归档成 `metadata/trace_metadata.json`。

Analyzer 依赖 metadata 中的数组地址范围来分类：

- `warmup`
- `index`
- `data`
- `tail`
- `output`

当前 metadata 顶层结构是：

```json
{
  "benchmark": {"name": "ima_tiny_case", "version": 1},
  "args": {...},
  "launch": {...},
  "phases": {"warmup": 256, "ima": 4096, "tail": 256},
  "arrays": {
    "warmup": {"device_base_hex": "0x...", "bytes": 0, "element_bytes": 4},
    "index":  {"device_base_hex": "0x...", "bytes": 0, "element_bytes": 4},
    "data":   {"device_base_hex": "0x...", "bytes": 0, "element_bytes": 4},
    "tail":   {"device_base_hex": "0x...", "bytes": 0, "element_bytes": 4},
    "output": {"device_base_hex": "0x...", "bytes": 0, "element_bytes": 4}
  },
  "mapping": {
    "seed": 1,
    "data_lines": 2048,
    "elements_per_line": 32,
    "compute_gap": 8,
    "line_bytes": 128,
    "type": "deterministic_line_permutation",
    "permutation_step": 3
  },
  "checksums": {...}
}
```

Analyzer 不依赖外部 workload 的 `pc_classification.csv`。

## Runner

主入口：

- [run_tiny_case.sh](/workspace/prefetch/ima_plan/04_prefetcher_design/tiny_case/run_tiny_case.sh)

默认行为：

1. build benchmark
2. 做一次 native sanity run
3. 生成一份 NVBit trace
4. 把 trace、CUDA、SASS 和 metadata 归档到对应 bundle
5. 对 `baseline/prefetch` 和 `lrr/gto` 组合分别做 sim/analyze

常用例子：

```bash
bash ima_plan/04_prefetcher_design/tiny_case/run_tiny_case.sh
```

只跑 baseline + lrr：

```bash
bash ima_plan/04_prefetcher_design/tiny_case/run_tiny_case.sh \
  --prefetch baseline \
  --scheduler lrr
```

复用已有 bundle 中的 trace，只重跑 sim/analyze：

```bash
bash ima_plan/04_prefetcher_design/tiny_case/run_tiny_case.sh \
  --skip-build \
  --skip-trace \
  --skip-native-check
```

如果需要旧的调试图，再显式打开：

```bash
bash ima_plan/04_prefetcher_design/tiny_case/run_tiny_case.sh \
  --plots all
```

## 默认图形输出

默认表格输出：

- `analysis/warp_load_events_<label>.csv`
- `analysis/warp_load_sectors_<label>.csv`

其中：

- `warp_load_events`：一行对应一次 `index_load` 或 `data_load` issue，记录 warp、issue cycle、地址列表和最后一个 refill cycle
- `warp_load_sectors`：一行对应一个 sector 地址，记录该地址的初始 L1 状态、初始 cycle 和 fill cycle

默认只看一张主图：

- `analysis/figures/warp_gantt_<label>.svg`

默认 `label` 取值：

- `base_lrr`
- `base_gto`
- `pf_lrr`
- `pf_gto`

这张图固定是 **8-warp issue gantt**，并且采用：

- 上半图：完整执行过程
- 下半图：IMA region zoom
- 背景高亮：`warmup / IMA / tail`
- 视觉重点：IMA region、`index_load`、`data_load`
- 非 IMA issue 只用浅灰色做底层参考，不再作为单独主图展开

所以现在默认分析目标不是 cacheline footprint，也不是 chain 甘特，而是先看：

- 8 个 warp 在全程里的发射节奏
- IMA 段进入后是否出现明显空洞
- `lrr/gto` 或 `baseline/prefetch` 下的 8-warp 交织是否变化

## 可选调试输出

只有在 `--plots all` 时，才额外生成：

- `phase_timeline_<label>.svg`
- `ima_chain_<label>_w<id>.svg`
- `overall_cacheline_index_<label>.svg`
- `overall_cacheline_data_<label>.svg`
- `chain_summary_<label>.csv`

这些属于补充调试图，不再是默认工作流的一部分。
