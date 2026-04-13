# Shared Running Example — GRASP Architecture Figures

> 最近更新: 2026-04-06
>
> All figures in §3 (GRASP Architecture) use this shared example for consistency.
> Running example based on SpMV kernel: `sum += Ax[offset] * x[Aj[offset]]`

## 1. Arrays and Addresses

### Index Array: Aj[] (column_indices)
| Property | Value |
|----------|-------|
| Const mem ref | c[0x0][0x170] |
| Figure prefix | `0x7FC4D0DA:` |
| Current demand sectors | `0x7FC4D0DA4860`, `0x7FC4D0DA4880` |

### Data Array: x[]
| Property | Value |
|----------|-------|
| Const mem ref | c[0x0][0x180] |
| Runtime base addr | 0x7FC4B7C20000 |
| Figure prefix | `0x7FC4B7:` |
| Scale | 4 (sizeof(float)) |

### Additional TT arrays (hypothetical, for varied CT examples)
| Array | Const mem ref | Runtime base | Scale | Notes |
|-------|--------------|-------------|-------|-------|
| y[] | c[0x0][0x188] | 0x7FC4B7E40000 | 4 | num_targets=2 example |
| z[] | c[0x0][0x190] | 0x7FC4B8100000 | 8 | num_targets=3 example (double) |

## 2. Warp and Threads

| Property | Value |
|----------|-------|
| Warp ID | 0 |
| Thread count | 8 (threads 0–7, simplified) |
| Index PC | 0x03d0 (real SpMV ×16 chain 1) |

## 3. Index Load Coalescing (Current Demand)

8 threads' index addresses coalesce to 2 sectors:

| Sector | Address | Mask | Active Positions | Active Count |
|--------|---------|------|-----------------|-------------|
| S0 | 0x7FC4D0DA:**4860** | 00101010 | [1, 3, 5] | 3 |
| S1 | 0x7FC4D0DA:**4880** | 00101111 | [0, 1, 2, 3, 5] | 5 |

**Tracked sector: S0** (all subsequent examples trace S0 only)

### S0 per-element addresses
| Position | Element Address | Notes |
|----------|----------------|-------|
| 1 | 0x7FC4D0DA4864 | sector_base + 1×4 |
| 3 | 0x7FC4D0DA486C | sector_base + 3×4 |
| 5 | 0x7FC4D0DA4874 | sector_base + 5×4 |

## 4. Index Values and Data Address Computation

When S0 returns, positions [1, 3, 5] contain index values (column_indices entries):

| S0 Position | Index Value (dec) | Index Value (hex) | Data Address = base + val×4 |
|-------------|-------------------|-------------------|----------------------------|
| 1 | 181,064 | 0x2C348 | 0x7FC4B7CD0D20 |
| 3 | 269,280 | 0x41BE0 | 0x7FC4B7D26F80 |
| 5 | 16,176 | 0x3F30 | 0x7FC4B7C2FCC0 |

## 5. TT (Target Table) Entries

| Entry | Valid | Base Address | Scale | Array | Used by CT rows |
|-------|-------|-------------|-------|-------|----------------|
| TT[0] | ✓ | 0x7FC4B7C20000 (x[]) | 4 | x[] | Row 1, 2, 3 |
| TT[1] | ✓ | 0x7FC4B7E40000 (y[]) | 4 | y[] | Row 2, 3 |
| TT[2] | ✓ | 0x7FC4B8100000 (z[]) | 8 | z[] | Row 3 |

## 6. CT (Chain Table) Entries

| Row | Valid | Index PC | tt_idx [0][1][2] | Num Targets | Iter Stride | Stride Valid | stride_obs[0] | stride_obs[1] | Notes |
|-----|-------|----------|-------------------|-------------|-------------|-------------|---------------|---------------|-------|
| 1 | ✓ | 0x03d0 | 0, —, — | 1 | 64 B | ✓ | W5: 0x7FC4D0DA4864 | W5: 0x7FC4D0DA48A4 | Real SpMV ×16 |
| 2 | ✓ | 0xA120 | 0, 1, — | 2 | 16 B | ✓ | W3: 0x7FC4D0DA2100 | W3: 0x7FC4D0DA2110 | Hypothetical ×4 |
| 3 | ✓ | 0xB340 | 0, 1, 2 | 3 | 4 B | ✗ | W8: 0x7FC4D0DA5040 | — | Hypothetical ×1, learning |

### IST Example (CT Row 1, PC 0x03d0)
- Obs[0]: Warp 5, Lane 1, addr = **0x7FC4D0DA4864** @ iter i
- Obs[1]: Warp 5, Lane 1, addr = **0x7FC4D0DA48A4** @ iter i+1
- stride = 0x48A4 − 0x4864 = **0x40 = 64 B** ✓

## 7. Prefetch Pipeline (for Fig E)

| Step | Value | Derivation |
|------|-------|-----------|
| Demand index sector | 0x7FC4D0DA4860 | Current iteration S0 |
| Prefetch index sector | **0x7FC4D0DA48A0** | demand + iter_stride(64) = 0x4860+0x40 |
| Prefetch sector mask | 00101010 | Same active pattern |
| PRB entry | tt_idx=[0], K=1, remaining_sectors=1 | Snapshot from CT Row 1 |
| Index values returned | (next iter's column_indices) | TBD per figure |
| Data addr computation | base + val × scale | ACU reads TT[0] |

## 8. Figure Notation Convention

### Address display
Addresses are 48-bit (12 hex digits). **In figures, write the FULL address** — no abbreviation.

| Array | Full address example | Notes |
|-------|---------------------|-------|
| Aj[] (index sector) | `0x7FC4D0DA4860` | 14 hex digits with 0x prefix |
| Aj[] (element) | `0x7FC4D0DA4864` | sector_base + position × 4 |
| x[]/y[]/z[] (data) | `0x7FC4B7CD0D20` | base + index_val × scale |
| TT base addr | `0x7FC4B7C20000` | Full runtime base pointer |
| IST obs addr | `0x7FC4D0DA4864` | Full per-lane address |

All hex addresses must start with `0x` to indicate hexadecimal. Do NOT use `0x...` abbreviation or separate prefix labels — write the complete value in each cell.

### Color coding (consistent with figure_prompts.md)
| Element | Color |
|---------|-------|
| Index load / index addr | Blue #2B5EA7 |
| Addr generation (IMAD.WIDE) | Purple #6C3483 |
| Data load / data addr | Amber #D4A843 |
| Valid indicator | Green #5AA469 |
| Other / neutral | Gray #BDC3C7 |
