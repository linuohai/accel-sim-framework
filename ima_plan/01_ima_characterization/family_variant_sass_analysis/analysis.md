# Family Variant SASS Analysis

## Bottom Line

- 本轮先在 `sm80` 上 screening 了 `8` 个算法家族的本地实现，共 `67` 个 native `.cu` 文件，其中 `61` 个被视为 family-comparable 主证据。
- 在已成功编译并进入 `sm80` screening 的 comparable 实现中，`46/56` 个表现为 stable/mostly fast path，其中 `29` 个是纯 `IMAD.WIDE`、`17` 个只含少量变体。
- 出现明显 mixed / non-IMAD 变体的家族主要集中在：pr, scc, sssp。
- 因而审稿叙事可以升级为：detect 方法不仅覆盖核心算法，也对多数同家族实现扰动稳健；真正的边界来自 mixed-predicate 或 redesign，而不是普通实现切换。

## Family Summary

| Algorithm | Comparable | Compiled@sm80 | Stable | Mostly | Mixed | Variant-only | No-IMA | Compile-fail | Redesign | Wrapper |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bc | 9 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| bfs | 15 | 14 | 8 | 5 | 0 | 0 | 1 | 1 | 2 | 0 |
| cc | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| pr | 10 | 9 | 7 | 0 | 0 | 1 | 1 | 1 | 1 | 1 |
| scc | 5 | 5 | 0 | 0 | 3 | 0 | 2 | 0 | 0 | 0 |
| spmv | 8 | 5 | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 1 |
| sssp | 4 | 4 | 1 | 1 | 2 | 0 | 0 | 0 | 2 | 0 |
| vc | 6 | 6 | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |

## Three-Arch Samples

| Algorithm | Impl | Role | sm70 | sm80 | sm90 |
|---|---|---|---|---|---|
| bc | `linear_base` | stable_rep | stable_fast_path | mostly_fast_path | stable_fast_path |
| bc | `hybrid_base` | variation_rep | mostly_fast_path | mostly_fast_path | mostly_fast_path |
| bfs | `linear_base` | stable_rep | mostly_fast_path | mostly_fast_path | mostly_fast_path |
| bfs | `linear_vector` | variation_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| cc | `base` | stable_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| cc | `warp` | variation_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| pr | `base` | stable_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| pr | `warp` | variation_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| pr | `push_pb` | boundary_rep | variant_only | variant_only | variant_only |
| scc | `base` | stable_rep | mixed_variant_heavy | mixed_variant_heavy | mixed_variant_heavy |
| scc | `bitset` | variation_rep | mixed_variant_heavy | mixed_variant_heavy | mixed_variant_heavy |
| spmv | `base` | stable_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| spmv | `warp` | variation_rep | stable_fast_path | stable_fast_path | stable_fast_path |
| sssp | `linear_base` | stable_rep | mostly_fast_path | mostly_fast_path | mostly_fast_path |
| sssp | `topo_base` | variation_rep | mixed_fast_path | mixed_fast_path | mixed_fast_path |
| vc | `linear_base` | stable_rep | mostly_fast_path | mostly_fast_path | mostly_fast_path |
| vc | `topo_base` | variation_rep | stable_fast_path | stable_fast_path | stable_fast_path |

## Interpretation

- `stable_fast_path` 与 `mostly_fast_path` 都可以拿来支撑“理论很 solid”的论点；两者区别只是后者含少量非主导变体。
- `mixed_fast_path` 表明同一实现里既有 `IMAD.WIDE` 主链，也有不可忽略的非 `IMAD.WIDE` 变体，适合用来说明 detector 的主覆盖面与边界。
- `variant_only` 或 `no_detected_ima` 更像 boundary / redesign 样本，不应与同家族普通实现混算为“理论失效”。
