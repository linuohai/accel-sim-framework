# SM80 Runtime SASS Artifacts for IMA Level 2

This directory stores the runtime-based `sm_80` SASS files used by
`ima_plan/01_ima_characterization.md` and downstream analysis scripts.

Location:

- `ima_plan/01_ima_characterization/sass_analysis/`

Canonical files:

- `bfs_linear_base.sm80.sass`
- `sssp_linear_base.sm80.sass`
- `bc_linear_base.sm80.sass`
- `cc_base.sm80.sass`
- `spmv_base.sm80.sass`

## Source of Truth

These SASS files are no longer generated from offline Gardenia cubins under
`gpu-app-collection/gardenia/src/`.

They are now generated from **runtime cubins dumped by the NVBit tracer during
the same tracing flow that produces instruction traces**. The corresponding
runtime evidence is stored under:

- `analyze/l1trace_mismatch/bfs_runtime_sm80/`
- `analyze/l1trace_mismatch/sssp_runtime_sm80/`
- `analyze/l1trace_mismatch/spmv_runtime_sm80/`
- `analyze/l1trace_mismatch/bc_runtime_sm80/`
- `analyze/l1trace_mismatch/cc_runtime_sm80/`

The key reason for this switch is that trace PCs were shown to match the
runtime code object seen by NVBit, while the previous offline cubin SASS could
map the same PC to different instructions.

## Extraction Flow

1. Run the tracer with runtime artifact dumping enabled.
2. Read the trace header and collect:
   - `binary version`
   - `function addr`
   - `runtime cubin`
   - `runtime static map`
3. Disassemble the runtime cubin:

```bash
nvdisasm --print-code --print-line-info --separate-functions <runtime.cubin> > <runtime.cubin.sass>
```

4. Store the runtime `.cubin.sass` under `analyze/l1trace_mismatch/*_runtime_sm80/`.
5. Copy or merge those raw runtime `.cubin.sass` files into this directory.
   Downstream analysis scripts still select the target kernels by symbol, so the
   files here can keep the full runtime section set.

## Workload Notes

- `bfs`, `sssp`, and `spmv` use raw runtime `.cubin.sass` extracted from
  representative `ima_high` tracing runs.
- `bc` and `cc` use runtime cubins extracted from a tiny temporary MatrixMarket
  graph that forces the target kernels to launch quickly. This is valid because
  the runtime code object depends on the executable binary, not on graph size.
- `bc_linear_base.sm80.sass` is the merged union of the raw runtime SASS files
  for `bc_forward` and `bc_reverse`.
- `cc_base.sm80.sass` currently reuses the raw runtime SASS dumped from the
  `hook` extraction run, which already includes both `hook` and `shortcut`.

## Auxiliary Files

- `bfs_linear_base.sm80.cfg.dot`
- `bfs_linear_base.sm80.cfg.png`

These CFG artifacts were produced from the older SASS workflow and are kept only
as auxiliary material. They are not the canonical runtime-SASS baseline.
