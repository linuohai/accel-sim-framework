# 实验输出规范

> 最近更新: 2026-03-31

本文档定义所有实验（Baseline / GRASP / SOTA baseline）的标准输出指标。所有实验结果报告必须遵循此规范。

---

## 1. 适用范围

| 实验类型 | 适用指标 |
|----------|----------|
| **Baseline** | §2.1 基础性能 + §2.2 IMA Demand（baseline 也有 `IMA_DEMAND` 输出）+ §2.4 Global L1 + §4 完成性 |
| **GRASP** | 全部 §2 展示指标 + 全部 §3 调试指标 + §4 完成性 + §5 配置快照 |
| **SOTA baseline** | 与 Baseline 相同 + SOTA 特有指标（视实现而定） |

---

## 1b. 三版本规则

**所有可按 Index/Data 拆分的指标，必须同时提供三个版本：**

| 版本 | 含义 | 覆盖 PC |
|------|------|---------|
| **IMA Index** | 仅 index load PC（chain CSV 中的 index_pc） | Index LDG |
| **IMA Data** | 仅 data load PC（chain CSV 中的 data_pc） | Data LDG |
| **Total** | Index + Data 合计 | 两者之和 |

**适用指标**（标 ★）：IMA Demand 分项、Timeliness、Coverage、Prefetch 活动、RFAIL 分项、FUNNEL。

**不适用**（天然单维度）：IPC、Cycles、Speedup、Storage、CD/CT/IST/PRB 训练状态、Pair Table、Throttle、Legacy EFFECT。

---

## 2. 展示指标（Display Metrics）

### 2.1 基础性能

| 指标 | 定义 | 公式 | 来源 | Baseline | GRASP |
|------|------|------|------|:---:|:---:|
| **IPC** | Instructions per cycle | total_insn / total_cycles | EXPERIMENT SUMMARY `final_ipc` | ✓ | ✓ |
| **Cycles** | 总仿真周期 | — | EXPERIMENT SUMMARY `final_cycles` | ✓ | ✓ |
| **Speedup** | vs baseline IPC | (grasp_ipc − baseline_ipc) / baseline_ipc × 100% | baseline_registry.csv | — | ✓ |
| **Kernel count** | 完成的 kernel 数 | expected / completed | EXPERIMENT SUMMARY | ✓ | ✓ |
| **Status** | 实验状态 | COMPLETE / PARTIAL / CRASHED | EXPERIMENT SUMMARY `status` | ✓ | ✓ |

### 2.2 IMA Demand 分项 ★ 三版本

每个指标提供 IMA Index / IMA Data / Total 三列：

| 指标 | IMA Index | IMA Data | Total | 说明 |
|------|-----------|----------|-------|------|
| **reads** | idx_reads | data_reads | idx + data | 总访问次数 |
| **hits** | idx_hits | data_hits | sum | L1D 命中（数据已就绪） |
| **hit_reserved** | idx_hit_reserved | data_hit_reserved | sum | L1D 行已分配但数据在途（MSHR 中） |
| **misses** | idx_misses | data_misses | sum | L1D 未命中（需从 L2 取） |

**恒等式**：`reads = hits + hit_reserved + misses`（三个版本各自成立，代码中有 assert 保证）

**来源**：
- Per-SM: `GRASP_IMA_DEMAND SM%u: idx(reads=... hits=... hit_res=... misses=...) data(reads=... hits=... hit_res=... misses=...)`
- 全局汇总: `IMA_DEMAND: idx(...) data(...)`（baseline 和 GRASP 都有）

### 2.3 效果指标 ★ 三版本（Timeliness/Coverage）

| 指标 | IMA Index | IMA Data | Total | 公式 |
|------|-----------|----------|-------|------|
| **Timeliness** | idx_T | data_T | total_T | `hits / (hits + hit_reserved)` |
| **Coverage** | idx_C | data_C | total_C | `(baseline_misses − grasp_misses) / baseline_misses` |

**Accuracy**（不分 Index/Data，来自 L1 cache 级）：

| 指标 | 公式 | 来源 |
|------|------|------|
| **Accuracy** | `pf_useful / (pf_useful + pf_useless)` | `GRASP_EFFECT SM*` |

**注意**：
- Timeliness 来源: `GRASP_TIMELINESS SM%u: index=%.2f%% data=%.2f%%` + `IMA_TIMELINESS`
- Coverage 需要 baseline 的 misses 数据（来自 `baseline_registry.csv` 或 baseline 实验的 `IMA_DEMAND` 输出）
- Accuracy 不区分 IMA PC，是 L1 cache tag 级统计，仅 GRASP 实验可用

### 2.4 Global L1 指标

| 指标 | 定义 | 公式 | 来源 |
|------|------|------|------|
| **Total demand global reads** | 所有 global load 总数 | — | `GRASP_DEMAND SM*: global_reads=...` |
| **Total demand global misses** | 所有 global load miss 总数 | — | `GRASP_DEMAND SM*: global_misses=...` |
| **IMA Miss Share** | IMA miss 占总 L1 miss 的比例 | `total_IMA_misses / total_demand_global_misses` | 由 §2.2 + §2.4 计算 |

---

## 3. 调试指标（Debug Metrics）

> 以下指标仅在 GRASP 实验中输出，用于内部诊断。

### 3.1 Pair Table

| 指标 | 说明 | 来源 |
|------|------|------|
| **pair_table_lookup_hit** | Pair table 命中（找到 index→data 映射） | `GRASP_SM*: pair_table(hit=... miss=...)` |
| **pair_table_lookup_miss** | Pair table 未命中 | 同上 |

### 3.2 Prefetch 活动 ★ 三版本

| 指标 | Index PF | Data PF | Total | 说明 |
|------|----------|---------|-------|------|
| **issued** | idx_pf_issued | data_pf_issued | sum | 成功注入 L1D 的 prefetch 数 |
| **hit** | idx_pf_hit | data_pf_hit | sum | 注入时 L1D 已有数据 |
| **miss** | idx_pf_miss | data_pf_miss | sum | 注入后需从 L2 取 |
| **mshr_merge** | idx_pf_mshr | data_pf_mshr | sum | 合并到已有 MSHR 请求 |
| **reservation_fail** | idx_pf_rfail | data_pf_rfail | sum | 注入失败（资源不足） |

Data PF 独有：

| 指标 | 说明 | 来源 |
|------|------|------|
| **enqueued** | 从 PRB fill 后入队等待注入 | `GRASP_FUNNEL SM*: data_enqueued=...` |

**来源**: `GRASP_SM*: idx_pf(issued=... hit=... miss=... mshr=... rfail=...) data_pf(...)`

### 3.3 RFAIL 分项 ★ 三版本

5 类失败原因，每类提供 Index / Data / 合并 三个值 + 百分比：

| 失败原因 | 含义 | Index | Data | Total % |
|----------|------|:---:|:---:|:---:|
| **LINE_ALLOC** | L1D cache 行分配失败 | idx_rfail[0] | data_rfail[0] | % |
| **MISSQ** | Miss queue 已满 | idx_rfail[1] | data_rfail[1] | % |
| **MSHR_ENTRY** | MSHR 条目已满 | idx_rfail[2] | data_rfail[2] | % |
| **MSHR_MERGE** | MSHR merge 失败 | idx_rfail[3] | data_rfail[3] | % |
| **RW_PENDING** | 读写竞争待决 | idx_rfail[4] | data_rfail[4] | % |

**来源**:
- Per-type: `GRASP_SM*: idx_rfail(line_alloc=... missq=... mshr_entry=... mshr_merge=... rw_pending=...) data_rfail(...)`
- 合并百分比: `GRASP_RFAIL SM%u: total=... line_alloc=%.1f%% missq=%.1f%% mshr_entry=%.1f%% mshr_merge=%.1f%% rw_pending=%.1f%%`

### 3.4 Throttle

| 指标 | 说明 | 来源 |
|------|------|------|
| **throttle_suppressed** | 被 Throttle Controller 抑制的 Data PF 数 | `GRASP_DEMAND SM*: throttle_suppressed=...` |

> 注：Throttle 仅作用于 Data PF，不区分 Index/Data。

### 3.5 Storage 利用率

| 组件 | 指标 | 公式 | 来源 |
|------|------|------|------|
| **PRB** | peak / capacity (%) | `100 × prb_peak / prb_capacity` | `GRASP_STORAGE SM*: prb=X/Y(Z%)` |
| **CT** | peak / ct_size (%) | `100 × ct_peak / ct_size` | 同上 `ct=X/Y(Z%)` |
| **CD FIFO** | peak / depth (%) | `100 × cd_peak / cd_fifo_depth` | 同上 `cd_fifo=X/Y(Z%)` |
| **PF Queue** | peak depth | — | 同上 `pf_queue_peak=...` |

### 3.6 训练状态

#### Chain Detector (CD)

| 指标 | 说明 | 来源 |
|------|------|------|
| **chains_detected** | 检测到的 IMA chain 数 | `GRASP_CD SM*` |
| **fifo_peak** | FIFO 峰值占用 | 同上 |
| **drops** | FIFO 溢出丢弃数 | 同上 |
| **read_inv** | 寄存器读后失效数 | 同上 |
| **write_inv** | 寄存器覆写失效数 | 同上 |
| **frozen** | CD 训练是否已冻结 | 同上 |

#### Chain Table (CT)

| 指标 | 说明 | 来源 |
|------|------|------|
| **peak_occ** | CT 峰值占用 | `GRASP_CT SM*` |
| **evictions** | LRU 淘汰次数 | 同上 |
| **evict_stride_valid** | 被淘汰时 stride 已收敛的条目数 | 同上 |
| **all_stride_valid** | 所有条目 stride 是否已收敛 | 同上 |

#### Iteration Stride Tracker (IST)

| 指标 | 说明 | 来源 |
|------|------|------|
| **generated** | Stride 收敛后生成的 prefetch 请求数 | `GRASP_IST SM*` |
| **issued** | 成功发出的 prefetch 数 | 同上 |
| **filtered** | 被下游过滤的 prefetch 数 | 同上 |

#### Prefetch Request Buffer (PRB)

| 指标 | 说明 | 来源 |
|------|------|------|
| **peak_occ** | PRB 峰值占用 | `GRASP_PRB SM*` |
| **allocs** | 总分配次数 | 同上 |
| **stall_cycles** | PRB 满导致的 stall 周期数 | 同上 |

### 3.7 FUNNEL 管线 ★ 三版本

Prefetch 管线端到端转化率，分 Index 路径和 Data 路径：

**Index 路径**：
```
idx_attempted → idx_rfail (%) → idx_got_data
```

**Data 路径**：
```
data_enqueued → data_throttled → data_attempted → data_rfail (%) → data_got_data
```

**Total**：合并 Index + Data 路径的对应计数。

| 指标 | 公式 | 来源 |
|------|------|------|
| idx_attempted | issued + hit + mshr + rfail | `GRASP_FUNNEL SM*` |
| idx_rfail | reservation_fail (count + %) | 同上 |
| idx_got_data | attempted − rfail | 同上 |
| data_enqueued | PRB fill 后入队数 | 同上 |
| data_throttled | TC 抑制数 | 同上 |
| data_attempted | issued + hit + mshr + rfail | 同上 |
| data_rfail | reservation_fail (count + %) | 同上 |
| data_got_data | attempted − rfail | 同上 |

### 3.8 Legacy EFFECT

| 指标 | 说明 | 来源 |
|------|------|------|
| **pf_useful** | Prefetch 在 demand 前命中 | `GRASP_EFFECT SM*` |
| **pf_useless** | Prefetch 在使用前被淘汰 | 同上 |
| **pf_late** | Demand 合并到 prefetch 的 MSHR（来晚了） | 同上 |
| **accuracy** | `pf_useful / (pf_useful + pf_useless)` | 同上 |

> **注意**：Legacy EFFECT 不区分 IMA PC，是 L1 cache tag 级统计。仅供交叉验证，不作为主指标。已被 §2.2 + §2.3 的 IMA PC 分类指标替代。

---

## 4. 实验完成性检查

**所有实验在读取结果前必须通过以下检查：**

| 检查项 | 条件 | 来源 |
|--------|------|------|
| Status | `status=COMPLETE` | EXPERIMENT SUMMARY |
| Kernel 完整性 | `completed_kernels == expected_kernels` | EXPERIMENT SUMMARY |

`traceL1` 在仿真结束后自动写入 `=== EXPERIMENT SUMMARY ===` 到 log 末尾。

---

## 5. GRASP 配置快照

GRASP 实验的报告必须附带参数快照：

```
GRASP_CONFIG: cd_fifo=20 ct_size=32 tt_size=8 ist_ipt=64 ist_dist=1 ist_conf=2
              prb_cap=1024 tc_mshr_thr=80 pt_scope=0
```

来源：仿真 log 中 `GRASP_CONFIG:` 行（仅 SM0 输出一次）。

---

## 6. 适用矩阵

| 指标组 | 章节 | Baseline | GRASP | SOTA stride | SOTA spare_reg |
|--------|------|:---:|:---:|:---:|:---:|
| 基础性能 | §2.1 | ✓ | ✓ | ✓ | ✓ |
| IMA Demand 分项 | §2.2 | ✓ | ✓ | ✓ | ✓ |
| Timeliness | §2.3 | — | ✓ | — | — |
| Coverage | §2.3 | 提供 baseline misses | ✓ | 可选 | 可选 |
| Accuracy | §2.3 | — | ✓ | — | — |
| Global L1 | §2.4 | ✓ | ✓ | ✓ | ✓ |
| Pair Table | §3.1 | — | ✓ | — | — |
| Prefetch 活动 | §3.2 | — | ✓ | — | — |
| RFAIL | §3.3 | — | ✓ | — | — |
| Throttle | §3.4 | — | ✓ | — | — |
| Storage | §3.5 | — | ✓ | — | — |
| 训练状态 | §3.6 | — | ✓ | — | — |
| FUNNEL | §3.7 | — | ✓ | — | — |
| Legacy EFFECT | §3.8 | — | ✓ | — | — |
| 完成性检查 | §4 | ✓ | ✓ | ✓ | ✓ |
| 配置快照 | §5 | — | ✓ | — | — |

---

## 7. 结果报告模板

### 7.1 简表模板（论文用）

适用于论文 table 和 experiment_progress.md 的结果汇总：

| Workload | Baseline IPC | GRASP IPC | Speedup | Idx Timeliness | Data Timeliness | Total Timeliness | Idx Coverage | Data Coverage | Total Coverage | Accuracy |
|----------|:-----------:|:---------:|:-------:|:--------------:|:---------------:|:----------------:|:------------:|:-------------:|:--------------:|:--------:|
| BFS | — | — | — | — | — | — | — | — | — | — |
| SSSP | — | — | — | — | — | — | — | — | — | — |
| SpMV | — | — | — | — | — | — | — | — | — | — |
| BC | — | — | — | — | — | — | — | — | — | — |
| **Geomean** | | | — | | | | | | | |

### 7.2 详表模板（调试用）

适用于调试诊断，附在简表之后：

**IMA Demand 分项**：

| Workload | Idx reads | Idx hits | Idx hit_res | Idx misses | Data reads | Data hits | Data hit_res | Data misses | Total reads | Total hits | Total hit_res | Total misses |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| BFS | — | — | — | — | — | — | — | — | — | — | — | — |

**Prefetch 活动 + RFAIL**：

| Workload | Idx PF issued | Idx PF rfail | Data PF issued | Data PF rfail | Total rfail | RFAIL 主因 | Throttled |
|----------|:-:|:-:|:-:|:-:|:-:|------|:-:|
| BFS | — | — | — | — | — | — | — |

**Storage + 训练**：

| Workload | PRB util% | CT util% | CD util% | Queue peak | Chains detected | CT evictions | All stride valid |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| BFS | — | — | — | — | — | — | — |

**FUNNEL**：

| Workload | Idx attempted | Idx rfail% | Idx got_data | Data enqueued | Data throttled | Data attempted | Data rfail% | Data got_data |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| BFS | — | — | — | — | — | — | — | — |
