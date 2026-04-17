---
title: LLM Operator Sim-vs-Real MAPE Experiment v2 — Design
date: 2026-04-16
status: finalized (设计冻结于 2026-04-17；§7 Step C 指标修订作为 Open Issue 1 待 v2 实施前讨论)
v1_doc: docs/superpowers/specs/2026-04-14-fa-decode-sim-vs-real-mape-design.md
v1_plan: docs/superpowers/plans/2026-04-14-fa-decode-sim-vs-real-mape.md
v1_results: docs/superpowers/specs/sim_vs_real_mape_results/
---

# LLM Operator Sim-vs-Real MAPE Experiment v2 — Design

## 0. v1 → v2 演进背景

**v1（2026-04-14）**：聚焦 FA prefill + Decode attention 两个算子，14 cfg，最终 11/14 sim 有效。已得到的关键结论：
- runtime MAPE ~34%，IPC MAPE ~34%
- DRAM util 平均偏差 ~52pp，L1 hit 偏差 ~49pp，L2 hit 偏差 ~37pp
- bottleneck 分类一致率仅 2/11 = **18%**，sim 系统性偏向 MEM-BW 判定
- 发现 sim IPC 单位为 thread-active 计数（已用 `÷ N_SM × WARP_SIZE` 近似 warp-IPC，但仍系统偏低 10-30%）
- 发现 sim "DRAM util" 是从 `(rd+wr) × 32B / runtime / 1555 GB/s` 反推，与 NCU 协议层定义不等价
- cfg_05 / cfg_12 / cfg_13 三个失败案例未做正式归类沉淀

**v2 升级目标**：
1. 算子覆盖从 2 → 4，**贴近真实 LLM 推理 stack**
2. 参数选择**锚定真实模型**（LLaMA-2/3.1 / Qwen3 / GLM-4 / Yi / DeepSeek / Kimi），HF `config.json` 校验
3. 引入 **deferred queue** 机制：暂不跑的算子写入队列，分批迭代
4. 引入 **失败配置档案**：把 sim 工具链/性能边界沉淀为约束规则
5. **dtype 统一为 bf16**（替代 v1 的 fp16），与真实生产推理 stack 一致
6. **FA 实现升级**：从 `flash_attn_qkvpacked_func`（MHA-only, non-causal）改为 `flash_attn_func(causal=True)`（支持 GQA + 真实 LLM prefill 语义）
7. **多轴深度**：从 v1 单 seq 轴 → 4 算子各 2-4 条深度轴（seq/GQA ratio/batch/page_size 等）
8. **Step C 指标修订**（IPC warp 级、DRAM 语义对齐、Cache/Issue 加细信息）作为下一轮讨论项

---

## 1. 设计原则（v2 新增；显式声明便于后续迭代）

### P1. 模拟器实操约束优先（hard constraints）
**原则**：实验矩阵必须先满足 sim 工具链能跑得动的约束，否则该 cfg 不入矩阵。

具体规则（来自 v1 失败案例沉淀）：
- **FA seq_len ≤ 4k**：s=8k 时 NVBit instrumentation overhead 不可承受（cfg_05 22 min 卡死）
- **Decode 总 CTA ≤ ~3000**（约 `batch × heads ≤ 256`）：sim 单线程串行 CTA 调度，过大会 hang（cfg_12 DEC-k2k-B8 跑 >4h 无进度）
- **永久排除 collective 算子**：`all_gather / reduce_scatter / all_to_all` 需 ≥2 GPU，GPGPU-Sim 单 GPU 模拟器无能力

### P2. 贴近真实 LLM 推理场景
**原则**：算子参数必须能在主流开源 LLM 中找到对应，不手工扫无意义网格。

锚点选取（详见 §3，HuggingFace `config.json` 校验）：
- **LLaMA-2 7B**（小模型 + MHA 代表）
- **LLaMA-3.1 8B**（小模型 + GQA 4:1）
- **LLaMA-3.1 70B**（大模型 + GQA 8:1）
- **Qwen3-32B**（中-大模型 + 非标 hidden=5120 + 国内代表）
- **GLM-4-9B**（小模型 + 极强 GQA 16:1 + 国内代表）

显式声明覆盖但不进矩阵（与上述锚点 shape 重复）：Qwen3-8B、Yi-1.5-9B、Mistral 7B
永久不进矩阵（不同 codepath）：DeepSeek-V3、Kimi K2、Mixtral-8x7B（MoE+MLA → deferred queue）

### P3. 失败配置沉淀
**原则**：每个失败 cfg 必须分类、归档，并影响后续矩阵设计；不允许"跑不动就忽略"。

分类法：
- **简单失败**：性能慢、配置错、脚本 bug → 修复 + 复盘 + 写入 changelog
- **困难失败**：sim/工具链固有缺陷 → 沉淀为 P1 类硬约束，加入"失败配置档案"（§6）
- **未明失败**：保留 ≤30min 排查窗口，超时则归"困难"

### P4. 深度优先（先深后广）
**原则**：参数矩阵先把少数主流算子的常见参数跑透（每轴 ≥3 点画出趋势），剩余算子分批迭代。

理由：v1 的 14 cfg 看似 5 轴扫描，但每轴 1-3 点，**画不出趋势曲线**也**断不出 sim 何时失效**。深度足够才能有结论价值。

机制：
- 选 4 个主流算子做"深度跑透"
- 剩余算子写入 deferred queue（§5），按优先级分批入 v3、v4
- 每完成一批从 queue 拉一个

### P5. 三 bottleneck class 必须各有锚点
**原则**：选算子必须覆盖 compute-bound / bandwidth-bound / mixed 三种 bottleneck，让 roofline 图每个 ceiling 上都有真实算子贴上去。

具体映射：
- **compute-bound 锚点**：GEMM（large M，逼近 312 TFLOPS）
- **bandwidth-bound 锚点**：fused_add_rmsnorm（pure mem，逼近 1555 GB/s）
- **mixed 锚点**：FA prefill（随 seq 滑动）
- **bandwidth-bound（KV-cache 特殊路径）**：Decode attention

---

## 2. 4 个主流算子（v2 范围）

| 算子 | 在 LLM 推理时间占比 | bottleneck 类 | sim 风险 | v2 状态 |
|---|---|---|---|---|
| **FA prefill** | ~10-20% | mixed (compute + bandwidth) | 低（v1 已验证） | ✅ |
| **Decode attention** | ~30-50%（长 KV） | bandwidth-bound | 低 | ✅ |
| **GEMM (bf16)** | ~40-60%（QKV / FFN proj） | compute-bound（large M） | 极低 | 🆕 |
| **fused_add_rmsnorm** | ~3-5% | bandwidth-bound（pure mem） | 低 | 🆕 |

**为什么不选其他算子**：
- `fused_swiglu` 与 `fused_add_rmsnorm` bottleneck 类相同（都是 bandwidth-bound element-wise），保留一个即可
- `quant_gemm` (W8A8) 是真实生产场景，但 INT8 trace 复杂度更高，二期再加
- `group_gemm`（MoE FFN）需要 cutlass grouped GEMM kernel，分析复杂，二期再加
- `RoPE` 推理占比 <1%，不进核心矩阵
- collectives 单 GPU 永久排除（P1）

---

## 3. 模型锚点（v2 参数来源）

**选取维度**（v2 显式定义）：
- **D1 模型规模**：从小（7-9B）到大（70B+）
- **D2 架构类型**：Dense MHA / Dense GQA（各 ratio）/ MoE / MLA
- **D3 地域分布**：国外 + 国内

**覆盖原则**（用户规定）：
- 主流系列（LLaMA、Qwen）每系列 1-2 个代表
- 其他开源（DeepSeek、Kimi、智谱、Yi 等）每家 1 个代表
- MoE / MLA 因 sim/工具链差异较大，暂入 deferred queue（§5），仅在锚点表中标注存在

**锚点全表**（HuggingFace 公开 `config.json` 校验，2026-04-16 拉取）：

| model | origin | scale | arch | hidden | H | kv_H | ratio | head_dim | FFN inter | max_seq | v2 矩阵 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **LLaMA-2 7B** | 美·Meta | 小 | Dense MHA | 4096 | 32 | 32 | 1:1 | 128 | 11008 | 4K | ✅ MHA 主锚 |
| **LLaMA-3.1 8B** | 美·Meta | 小 | Dense GQA | 4096 | 32 | 8 | 4:1 | 128 | 14336 | 128K | ✅ GQA 主锚 |
| **LLaMA-3.1 70B** | 美·Meta | 大 | Dense GQA | 8192 | 64 | 8 | 8:1 | 128 | 28672 | 128K | ✅ 大模型主锚 |
| **Qwen3-8B** | 中·阿里 | 小 | Dense GQA | 4096 | 32 | 8 | 4:1 | 128 | 12288 | 40K | 与 LLaMA-3.1 8B attn shape 完全相同；锚点声明，不重复进矩阵 |
| **Qwen3-32B** | 中·阿里 | 中-大 | Dense GQA | **5120** | 64 | 8 | 8:1 | 128 | **25600** | 40K | 🆕 hidden=5120 非标 → §4.3 加 G8 |
| **GLM-4-9B** | 中·智谱 | 小 | Dense GQA | 4096 | 32 | **2** | **16:1** | 128 | 13696 | 8K | 🆕 极强 GQA → §4.2 加 D7、§4.3 加 G11 |
| **Yi-1.5-9B** | 中·01.AI | 小 | Dense GQA | 4096 | 32 | 4 | 8:1 | 128 | 11008 | 4K | 与 LLaMA-3.1 70B 同 GQA ratio；锚点声明，不进矩阵 |
| **DeepSeek-V3** | 中·DeepSeek | 671B (MoE) | **MoE + MLA** | 7168 | 128 | 128 (latent_kv=512) | — | qk_nope128+qk_rope64=**192** | dense=18432, MoE=2048×256+1 shared | 160K | 🚫 deferred |
| **Kimi K2** | 中·月之暗面 | (MoE) | **MoE + MLA** | 7168 | 64 | 64 (latent_kv=512) | — | **112** (非标，7168/64) | dense=18432, MoE=2048×384+1 shared | 128K | 🚫 deferred |
| **Mixtral-8x7B** | 美·Mistral | 47B (MoE) | MoE Dense GQA | 4096 | 32 | 8 | 4:1 | 128 | 14336 × 8 | 32K | 🚫 deferred |

**注意 max_seq 与 v2 矩阵 seq 上限的关系**：v2 实验 seq 上限 = 4K（P1 NVBit 约束），低于上述所有模型的训练上限。这意味着我们覆盖的是**模型 prefill 短-中段**；长上下文（>4K）需要 v3 解决 NVBit 约束后再做。

**v2 主锚点（实际进矩阵）= {LLaMA-2 7B, LLaMA-3.1 8B, LLaMA-3.1 70B, Qwen3-32B, GLM-4-9B}**：
- 覆盖 D1（规模）：小（7-9B）+ 中-大（32B）+ 大（70B）
- 覆盖 D2（架构）：MHA（LLaMA-2 7B）+ GQA 多 ratio（4:1, 8:1, 16:1）
- 覆盖 D3（地域）：3 个国外（Meta 系）+ 2 个国内（阿里、智谱）

**显式声明覆盖但不进矩阵**：Qwen3-8B, Yi-1.5-9B, Mistral 7B（与已有锚点 attn/FFN shape 重复或接近，加进矩阵无新增信息量）

**永久不进矩阵**（deferred queue §5）：DeepSeek-V3, Kimi K2, Mixtral-8x7B。这些模型的实际生产 attention/FFN kernel（MLA 子空间投影 / group_gemm）与 v2 选用的 flash-attn / flashinfer-paged / dense GEMM 是**不同的 kernel codepath**——把它们的 hidden/H 灌入 v2 算子矩阵跑出的数据**不能反映这些模型真实推理时的瓶颈**。需要 v3 单独引入 MLA / group_gemm 算子家族后再纳入。

---

## 3.5 v2 实现选型与 prereq

**统一 dtype = bfloat16**

| 项 | 决定 |
|---|---|
| **dtype** | **bfloat16**（全部 4 算子统一） |
| 理由 | (1) 现代开源 LLM 100% 用 bf16 训练 + bf16 权重发布；(2) 主流推理 stack（vLLM / SGLang / TensorRT-LLM）默认 bf16；(3) A100 硬件层 fp16/bf16 算力相同（312 TFLOPS dense）；(4) 用 fp16 与真实生产部署不一致，MAPE 数据缺乏代表性 |
| 影响 | v1 已跑的 14 cfg 全部重跑 bf16；矩阵实际 0 复用 + 41 新跑 |

**算子实现选型**

| 算子 | 实现 | 调用方式 | 备注 |
|---|---|---|---|
| **FA prefill** | flash_attn 2.4.2 (FA2) | `flash_attn_func(q, k, v, causal=True)` | A100 SM80 不支持 FA3（需 Hopper SM90+）；改写从 `flash_attn_qkvpacked_func` 切到 `flash_attn_func` 才能支持 GQA + causal |
| **Decode attention** | flashinfer (paged attention) | `BatchDecodeWithPagedKVCache.forward()` | v1 已用 |
| **GEMM** | PyTorch `torch.matmul(a_bf16, b_bf16)` | dispatch 到 cuBLAS / cublasLt | 这是 vLLM / HF Transformers 实际调用的，A100 SOTA |
| **fused_add_rmsnorm** | vLLM `vllm.model_executor.layers.layernorm.RMSNorm` | `layer.forward(x, residual=residual)` | 含 residual add fusion；如未装 vLLM，fallback 到 flash_attn `rms_norm` + 手写 add |

**v2 必做 prereq**（在跑实验前必须完成）：

1. **`fa.py` 改写**：把 `flash_attn_qkvpacked_func(qkv)` 替换为：
   ```python
   q = torch.randn(B, S, H,    D, dtype=torch.bfloat16, device='cuda')
   k = torch.randn(B, S, kv_H, D, dtype=torch.bfloat16, device='cuda')
   v = torch.randn(B, S, kv_H, D, dtype=torch.bfloat16, device='cuda')
   out = flash_attn_func(q, k, v, causal=True)
   ```
2. **新写 `gemm.py`**：`torch.matmul` bf16 + NVBit 友好的 `torch.cuda.synchronize()`
3. **新写 `rmsnorm.py`**：vLLM `RMSNorm` 调用 + bf16 residual
4. **`flashinfer_decode.py` 检查**：确认 dtype 是 bf16，page_size 可参数化（v1 默认 16，v2 要扫 16/32/64）

---

## 4. 参数矩阵（41 cfg：0 复用 + 41 新跑，全部 bf16 重跑）

### 4.1 FA prefill（11 cfg）

**深度轴**：seq（4 pts）+ GQA ratio（4 pts）+ batch（3 pts，受 P1 CTA 预算 ≤~3000 限制）
**浅轴 ablation**：head_dim
**配置统一**：dtype=bf16, causal=True, 调用 `flash_attn_func(q,k,v,causal=True)`

| # | label | H | kv_H | head_dim | B | seq | 在哪条深度轴上 |
|---|---|---|---|---|---|---|---|
| F1 | FA-7B-s512 | 32 | 32 | 128 | 1 | 512 | seq 深扫（pt 1） |
| F2 | FA-7B-s1k | 32 | 32 | 128 | 1 | 1024 | seq 深扫（pt 2） |
| F3 | FA-7B-s2k | 32 | 32 | 128 | 1 | 2048 | seq 深扫（pt 3）+ 锚点 cfg |
| F4 | FA-7B-s4k | 32 | 32 | 128 | 1 | 4096 | seq 深扫（pt 4） |
| F5 | FA-7B-s2k-d64 | 32 | 32 | **64** | 1 | 2048 | head_dim ablation |
| F6 | FA-7B-s2k-B2 | 32 | 32 | 128 | **2** | 2048 | batch 深扫（pt 2，B=1 在 F3） |
| F7 | FA-7B-s2k-B4 | 32 | 32 | 128 | **4** | 2048 | batch 深扫（pt 3） |
| F8 | FA-LLaMA3-8B-s2k | 32 | **8** | 128 | 1 | 2048 | GQA 深扫（4:1 ratio） |
| F9 | FA-LLaMA3-70B-s2k | **64** | **8** | 128 | 1 | 2048 | GQA 深扫（8:1 ratio + H 增大） |
| F10 | FA-GLM4-s2k | 32 | **2** | 128 | 1 | 2048 | GQA 深扫（16:1 极强） |
| F11 | FA-LLaMA3-8B-s4k | 32 | 8 | 128 | 1 | **4096** | GQA × 长 seq 交叉点 |

**Sim 可行性自检（P1）**：
- F4: seq=4k 已知 OK（v1 cfg_04 验证）
- F7: B=4×H=32 = 128 CTA × ceil(2048/64) = ~4096 CTA（接近 P1 上限，可控）
- F9: H=64 × seq=2k → KV 状态 2× 7B；预估 sim 时间 ~2× 但可控

**Drop 原 v1 cfg_07 FA-s2k-H8**（H=8, kv=8）：手工选的小-H ablation 不对应任何真实模型，违反 P2。

### 4.2 Decode attention（13 cfg）

**深度轴**：kv_len（4 pts）+ GQA ratio（4 pts）+ batch（3 pts）+ page_size（3 pts）
**浅轴 ablation**：head_dim
**配置统一**：dtype=bf16, page_size 默认 16, 调用 `flashinfer.BatchDecodeWithPagedKVCache`

| # | label | H | kv_H | head_dim | B | kv_len | page | 在哪条深度轴上 |
|---|---|---|---|---|---|---|---|---|
| D1 | DEC-7B-k512 | 32 | 32 | 128 | 1 | 512 | 16 | kv_len 深扫（pt 1） |
| D2 | DEC-7B-k1k | 32 | 32 | 128 | 1 | 1024 | 16 | kv_len 深扫（pt 2） |
| D3 | DEC-7B-k2k | 32 | 32 | 128 | 1 | 2048 | 16 | kv_len 深扫（pt 3）+ 锚点 cfg |
| D4 | DEC-7B-k4k | 32 | 32 | 128 | 1 | 4096 | 16 | kv_len 深扫（pt 4） |
| D5 | DEC-7B-k2k-d64 | 32 | 32 | **64** | 1 | 2048 | 16 | head_dim ablation |
| D6 | DEC-7B-k2k-B2 | 32 | 32 | 128 | **2** | 2048 | 16 | batch 深扫（pt 2，B=1 在 D3） |
| D7 | DEC-7B-k2k-B4 | 32 | 32 | 128 | **4** | 2048 | 16 | batch 深扫（pt 3） |
| D8 | DEC-7B-k2k-page32 | 32 | 32 | 128 | 1 | 2048 | **32** | page_size 深扫（pt 2） |
| D9 | DEC-7B-k2k-page64 | 32 | 32 | 128 | 1 | 2048 | **64** | page_size 深扫（pt 3） |
| D10 | DEC-LLaMA3-8B-k2k | 32 | **8** | 128 | 1 | 2048 | 16 | GQA 深扫（4:1 ratio） |
| D11 | DEC-LLaMA3-70B-k2k | **64** | **8** | 128 | 1 | 2048 | 16 | GQA 深扫（8:1 ratio + H 增大） |
| D12 | DEC-GLM4-k2k | 32 | **2** | 128 | 1 | 2048 | 16 | GQA 深扫（16:1 极强） |
| D13 | DEC-LLaMA3-8B-k4k | 32 | 8 | 128 | 1 | **4096** | 16 | GQA × 长 KV 交叉点 |

**Sim 可行性自检（P1）**：
- D7: B=4 × H=32 = 128 CTA（OK）
- D11: B=1 × H=64 = 64 CTA（OK，但 KV 占 2× 内存）
- 不收 DEC-7B-k8k：v1 已观察 DEC-7B-k4k 的 sim L2 hit 异常下降（22.8% → MSHR back-pressure），k8k 大概率落入 sim credibility boundary 之外

### 4.3 GEMM (bf16, cuBLAS via `torch.matmul`)（12 cfg）

**M/N/K 到 LLM 推理的映射**（写在表前以便理解 shape pattern）：

`[M, K] @ [K, N]` 在 LLM 推理中对应 4 种 shape pattern：

| pattern | shape 公式 | M | K | N |
|---|---|---|---|---|
| **QKV proj** | `(H + 2·kv_H) × head_dim` | B × S（token 数） | hidden_size | (H + 2·kv_H) × head_dim |
| **O proj** | hidden | B × S | hidden_size | hidden_size |
| **FFN gate/up** | intermediate | B × S | hidden_size | intermediate_size |
| **FFN down** | hidden | B × S | intermediate_size | hidden_size |

**关键**：QKV 的 N 是**架构敏感的**（GQA ratio 越大 N 越小），FFN 的 N 是**模型敏感的**（intermediate 不同）。这两条 pattern 走**不同的 fan-out 路径**。

**深度轴**：M（5 pts）+ shape pattern（4 种）+ model scale（3 个）

| # | label | M | K | N | shape pattern | 模型 |
|---|---|---|---|---|---|---|
| G1 | GEMM-7B-FFN-up-M1 | 1 | 4096 | 11008 | FFN up | LLaMA-2 7B（M 深扫 pt 1，极端 bandwidth） |
| G2 | GEMM-7B-FFN-up-M64 | 64 | 4096 | 11008 | FFN up | LLaMA-2 7B（M 深扫 pt 2） |
| G3 | GEMM-7B-FFN-up-M256 | 256 | 4096 | 11008 | FFN up | LLaMA-2 7B（M 深扫 pt 3） |
| G4 | GEMM-7B-FFN-up-M1024 | 1024 | 4096 | 11008 | FFN up | LLaMA-2 7B（M 深扫 pt 4） |
| G5 | GEMM-7B-FFN-up-M4096 | 4096 | 4096 | 11008 | FFN up | LLaMA-2 7B（M 深扫 pt 5，compute 满） |
| G6 | GEMM-7B-FFN-down-M1024 | 1024 | 11008 | 4096 | **FFN down** | LLaMA-2 7B（skewed inner-dim） |
| G7 | GEMM-70B-FFN-up-M1024 | 1024 | 8192 | 28672 | FFN up | LLaMA-2 70B（model scale） |
| G8 | GEMM-Qwen3-32B-FFN-up-M1024 | 1024 | **5120** | **25600** | FFN up | Qwen3-32B（非标 hidden=5120） |
| G9 | GEMM-7B-QKV-MHA-M1024 | 1024 | 4096 | **12288** | **QKV (MHA 1:1)** | LLaMA-2 7B（QKV pattern 起点） |
| G10 | GEMM-LLaMA3-8B-QKV-GQA4-M1024 | 1024 | 4096 | **6144** | **QKV (GQA 4:1)** | LLaMA-3.1 8B |
| G11 | GEMM-GLM4-QKV-GQA16-M1024 | 1024 | 4096 | **4608** | **QKV (GQA 16:1)** | GLM-4-9B |
| G12 | GEMM-7B-O-M1024 | 1024 | 4096 | 4096 | **O proj** | LLaMA-2 7B |

**为什么 M 轴 = AI 旋钮**：固定 K, N 时，arithmetic intensity AI = `2·M·K·N / (2·(M·K + K·N + M·N))` 随 M 单调增。这让单条 M 扫描就能横跨整个 roofline。

**Sim 可行性自检（P1）**：cuBLAS bf16 GEMM 是 NVBit/sim 的常规 case，无已知风险。

### 4.4 fused_add_rmsnorm（5 cfg）

**深度轴**：M（3 pts）+ hidden（3 pts）
**配置统一**：dtype=bf16，调用 vLLM `RMSNorm.forward(x, residual=residual)`（含 residual add fusion）

input: `(M, hidden)` 残差 + `(M, hidden)` 主路径，输出 `(M, hidden)`

| # | label | M | hidden | bottleneck 预期 |
|---|---|---|---|---|
| R1 | RMS-7B-M256 | 256 | 4096 | bandwidth-bound（部分 SM 占用，M 深扫 pt 1） |
| R2 | RMS-7B-M1024 | 1024 | 4096 | bandwidth-bound（SM 饱和过渡，pt 2） |
| R3 | RMS-7B-M4096 | 4096 | 4096 | bandwidth saturated（roofline 顶点，pt 3） |
| R4 | RMS-Qwen3-32B-M1024 | 1024 | **5120** | hidden 深扫 pt 2（5120 非标） |
| R5 | RMS-70B-M1024 | 1024 | **8192** | hidden 深扫 pt 3（大 hidden） |

**Sim 可行性自检（P1）**：element-wise + reduce kernel，无风险。

### 4.2 Decode attention（7 cfg）

axis：kv_len sweep + 模型规模 + 小 batch（避开 cfg_12 hang 区域）

| # | label | H | kv_H | D | B | kv_len | 来源/状态 |
|---|---|---|---|---|---|---|---|
| D1 | DEC-7B-k512 | 32 | 32 | 128 | 1 | 512 | ✅ v1 cfg_08 |
| D2 | DEC-7B-k1k | 32 | 32 | 128 | 1 | 1024 | ✅ v1 cfg_09 |
| D3 | DEC-7B-k2k | 32 | 32 | 128 | 1 | 2048 | ✅ v1 cfg_10 |
| D4 | DEC-7B-k4k | 32 | 32 | 128 | 1 | 4096 | ✅ v1 cfg_11 |
| D5 | DEC-8B-k2k (GQA) | 32 | 8 | 128 | 1 | 2048 | ✅ v1 cfg_14 |
| D6 | DEC-7B-k2k-B4 | 32 | 32 | 128 | 4 | 2048 | 🆕 batch effect（远小于 B=8 hang 阈值） |
| D7 | DEC-70B-k2k | 64 | 8 | 128 | 1 | 2048 | 🆕 大模型 GQA |
| D8 | DEC-GLM4-k2k | 32 | **2** | 128 | 1 | 2048 | 🆕 极强 GQA 16:1（GLM-4-9B 锚点；测 sim 在低 KV 流量下的表现） |

**Sim 可行性自检（P1）**：
- D6: B=4 × H=32 = 128 CTA（OK）
- D7: B=1 × H=64 = 64 CTA（OK，但 KV 占 2× 内存）
- 不收 DEC-7B-k8k：v1 已观察 DEC-7B-k4k（cfg_11）的 sim DRAM util 异常下降（22.8% L2 hit → MSHR back-pressure），k8k 大概率落入 sim credibility boundary 之外，不再加深探测；以后单独立题做"sim long-KV 失效"研究

### 4.3 GEMM (fp16, cuBLAS)（7 cfg）

axis：M sweep（AI 调节旋钮，扫遍 memory→compute 频谱）+ 模型 FFN 规模

shape = `[M, K] @ [K, N]`，使用 LLaMA FFN up projection 形状（K=hidden, N=intermediate）

| # | label | M | K | N | shape 来源 | bottleneck 预期 |
|---|---|---|---|---|---|---|
| G1 | GEMM-7B-FFN-up-M1 | 1 | 4096 | 11008 | LLaMA-2 7B FFN up | 极端 bandwidth-bound（decode 单 token） |
| G2 | GEMM-7B-FFN-up-M64 | 64 | 4096 | 11008 | 同上 | memory-bound |
| G3 | GEMM-7B-FFN-up-M256 | 256 | 4096 | 11008 | 同上 | mixed |
| G4 | GEMM-7B-FFN-up-M1024 | 1024 | 4096 | 11008 | 同上 | mixed → compute |
| G5 | GEMM-7B-FFN-up-M4096 | 4096 | 4096 | 11008 | 同上 | compute-bound 满（prefill ctx=4k） |
| G6 | GEMM-7B-FFN-down-M1024 | 1024 | 11008 | 4096 | LLaMA-2 7B FFN down | skewed inner-dim ablation |
| G7 | GEMM-70B-FFN-up-M1024 | 1024 | 8192 | 28672 | LLaMA-2 70B FFN up | 大模型 compute |
| G8 | GEMM-Qwen3-32B-FFN-up-M1024 | 1024 | **5120** | **25600** | Qwen3-32B FFN up（非标 hidden=5120） | mixed → compute |

**为什么 M 轴 = AI 旋钮**：固定 K, N 时，arithmetic intensity AI = `2·M·K·N / (2·(M·K + K·N + M·N))` 随 M 单调增（小 M 时 K·N 项主导内存量；大 M 时 M·N 主导计算量）。这让单条 M 扫描就能横跨整个 roofline。

**Sim 可行性自检（P1）**：cuBLAS GEMM 是 NVBit/sim 的常规 case，无已知风险。

### 4.4 fused_add_rmsnorm（4 cfg）

axis：M sweep + hidden sweep（bandwidth 锚点，验证算子在 SM 数受限/带宽受限的过渡）

input: `(M, hidden)` 残差 + `(M, hidden)` 主路径，输出 `(M, hidden)`

| # | label | M | hidden | bottleneck 预期 |
|---|---|---|---|---|
| R1 | RMS-7B-M256 | 256 | 4096 | bandwidth-bound（部分 SM 占用） |
| R2 | RMS-7B-M1024 | 1024 | 4096 | bandwidth-bound（SM 饱和过渡） |
| R3 | RMS-7B-M4096 | 4096 | 4096 | bandwidth saturated（roofline 顶点） |
| R4 | RMS-70B-M1024 | 1024 | 8192 | 大 hidden 验证 |

**算子选取**：使用 `flash_attn` 或 `apex` 中的 fused kernel（含 residual add + RMSNorm，不含 quant，简化 trace）；如二者都不可用则用纯 PyTorch 实现（性能差但 NCU/sim 数据仍可比）。

**Sim 可行性自检（P1）**：element-wise + reduce kernel，无风险。

### 4.5 矩阵汇总

| 算子 | 复用 v1 | 新跑 | 小计 | 主深度轴数 |
|---|---|---|---|---|
| FA prefill | 0 | 11 | 11 | 3（seq, GQA ratio, batch） |
| Decode | 0 | 13 | 13 | 4（kv_len, GQA ratio, batch, page_size） |
| GEMM | 0 | 12 | 12 | 3（M, shape pattern, model scale） |
| fused_add_rmsnorm | 0 | 5 | 5 | 2（M, hidden） |
| **总** | **0** | **41** | **41** | — |

> v1 已跑的 14 cfg 全部重跑 bf16（决策来自 §3.5：fp16/bf16 不混用以保 MAPE 可比性）。8 卡并行约 **8-10h** 跑完。

---

## 5. Deferred Operator Queue（v3+ 候选）

按优先级排序，每完成一轮 v_n 实验后从 queue 拉一个进 v_{n+1}：

| 优先级 | 算子 | 出处场景 | 暂缓原因 |
|---|---|---|---|
| ⭐⭐⭐ | **quant_gemm** (W8A8) | 量化推理（LLM 实际生产） | INT8 trace 复杂度需先 PoC |
| ⭐⭐⭐ | **group_gemm** (MoE FFN) | Mixtral / DeepSeek-V2 | cutlass grouped GEMM kernel 分析复杂 |
| ⭐⭐ | **fused_swiglu_quant** | LLaMA FFN 激活路径 | 与 fused_add_rmsnorm bottleneck 类相同，先做后者代表 |
| ⭐⭐ | **fused_softmax_topk** | MoE gating + sampling | 占比小但有信息量 |
| ⭐ | **gating_gemm** | MoE 路由头 | 是个普通小 GEMM，等同 G2-G3 缩小版 |
| ⭐ | **store_kv** standalone | 解耦 decode 流水线测 | 已含在 decode 中，独立测意义不大 |
| ⭐ | **RoPE** | attn 前置 | 占比 <1% |

**永久排除**（P1 单 GPU 限制）：`all_gather`, `reduce_scatter`, `all_to_all`

---

## 6. 失败配置档案（v1 沉淀）

| cfg | label | 失败 stage | root cause | 类别（P3） | 沉淀规则 |
|---|---|---|---|---|---|
| v1 cfg_05 | FA-s8k (B=1, H=32, D=128) | NVBit | seq=8k → trace 体积爆炸 + instrument overhead 不可控 | **困难（工具链）** | **P1: FA seq ≤ 4k** |
| v1 cfg_12 | DEC-k2k-B8 | sim | batch=8 × H=32 = 256 attn 实例，sim 单线程 CTA 调度太慢（>4h） | **简单（性能，非错误）** | **P1: decode 总 CTA ≤ ~3000（B × H ≤ 256）** |
| v1 cfg_13 | DEC-k2k-B32 | sim | bail at kernel-198 (CatArrayBatchedCopy) 没到主 kernel | **未明** | 投入不超过 30 分钟的**人工排查时间**（包括读 sim log、定位 bail kernel-198 是什么、检查 trace 完整性；**不含实验运行时间**）。若该时间窗内无法定位 root cause，则归"困难"类，加入 §6 失败档案，并在 deferred queue 标注"sim 多 kernel 序列前置失败" |

---

## 7. Step C：指标修订（v2 决定，已收敛）

> 决定于 2026-04-17，作为 Phase 0.5 在 v2 bulk 实验前实施。详见 plan §Phase 0.5。

| 指标 | v1 现状 | 问题 | v2 修订方向 | v2 状态 |
|---|---|---|---|---|
| **IPC** | sim: `gpu_sim_insn / cycle ÷ (108·32)` thread 级近似 | 系统偏低 10-30%（不计 predication） | sim 加 `WINSN_TOTAL:` per-kernel dump（累加 `m_num_sim_winsn`）；parser 用 `winsn / cycle / 432` 算 warp-IPC | ✅ Phase 0.5 SC.1 |
| **DRAM util** | sim: `(rd+wr)·32B / runtime / 1555` 反推 | 假设 burst 永远 32B，与 NCU 协议层不等价 | sim 加 `DRAM_UTIL_BINS:` per-kernel dump（10 bins）；parser 加权平均 → 与 NCU `dram__throughput.pct_of_peak_sustained_elapsed` 语义对齐 | ✅ Phase 0.5 SC.2 |
| **Cache (L1/L2)** | 仅 hit rate % | 在 access count 极小时无意义（如 GEMM 只读权重 1 次，0% hit rate 实属噪音） | NCU 加 `l1tex__t_sectors.sum`, `l1tex__t_sectors_pipe_lsu_mem_global_op_{ld,st}.sum`, `l1tex__t_sectors_hit.sum`, `lts__t_sectors.sum`, `lts__t_sectors_op_{read,write}.sum`；sim 解析现有 access count 字段 | ✅ Phase 0.5 SC.4-6 |
| **Issue execution rate** | 无 | 缺执行节奏指标 | NCU 加 `smsp__inst_executed.avg.per_cycle_active`（execution rate）；不加 issue/eligible/active warps（v1 已 drop SM busy、issue 阶段语义不对齐） | ⭕ Phase 0.5 SC.4-5（仅 1 项） |
| **Stall reasons** | sim 3-4 桶 + NCU 17 项，display-only 不算 MAPE | sim 分类基于内部 issue 决策路径（架构实现选择），NCU 17 项基于硬件事件枚举——**两套体系本质不同，强映射会引入 artifact** | **不对齐**。两边各画一套 stacked bar 让读者看 shape distribution，但不计 MAPE | ❌ 保持 v1 处理 |
| **SM Busy** | v1 已 drop（sim 只有静态 occupancy） | 无对应动态 metric | 保持 drop | ❌ 不变 |

---

## 8. v1 → v2 changelog

- **算子**：2 → 4（加 GEMM, fused_add_rmsnorm）
- **cfg**：14 → 41（0 复用 + 41 新跑，全部 bf16 重跑）
- **dtype**：fp16 → **bf16**（与现代 LLM 推理 stack 一致；A100 算力相同所以无性能取舍）
- **FA 实现**：`flash_attn_qkvpacked_func`（MHA-only, non-causal）→ `flash_attn_func(causal=True)`（支持 GQA + 真实 LLM prefill 语义）
- **GEMM 实现**：v1 无 → v2 用 `torch.matmul(bf16, bf16)`（dispatch 到 cuBLAS）
- **RMSNorm 实现**：v1 无 → v2 用 vLLM `RMSNorm.forward(x, residual=residual)`
- **深度结构**：v1 单 seq 轴 → v2 多轴深度（FA 3 轴 / Decode 4 轴 / GEMM 3 轴 / RMSNorm 2 轴）
- **GEMM shape pattern**：v1 无 → v2 覆盖 LLM block 全部 4 种 pattern（QKV / O / FFN-up / FFN-down）
- **Decode page_size**：v1 固定 16 → v2 扫 {16, 32, 64}
- **参数选择**：手工扫网格 → 锚定真实开源模型（HF `config.json` 校验）
- **模型锚点**：v1 隐式 LLaMA only → v2 显式 5 主锚点（实进矩阵）+ 5 声明锚点（含国内 Qwen3 / GLM-4 / Yi / DeepSeek / Kimi）
- **选取维度**：单一 → 显式 D1 规模 + D2 架构 + D3 地域三维度
- **失败处理**：临时跳过 → 沉淀为 P3 档案 + P1 硬约束
- **算子排队**：无 → 引入 deferred queue 机制（含 MoE / MLA 整族架构 deferred）
- **设计原则**：隐式 → 显式（P1-P5）
- **指标修订**：v1 已识别问题 → v2 Step C 集中修订（IPC warp 级、DRAM 语义对齐、Cache access count、Issue 细分）

## 9. Open Issues（v2 未决）

1. ~~**Step C 指标修订方案**~~ → **RESOLVED 2026-04-17**：4 项中 IPC + DRAM + Cache 全做（Phase 0.5 SC.1-SC.8）；Issue stage 仅加 `smsp__inst_executed.avg.per_cycle_active` 一项；Stall reasons 不对齐（架构实现 vs 硬件事件，强映射有 artifact）保持 v1 display-only。详见 §7。
2. **cfg_13 排查窗口**：v2 一开始投入 ≤30min 人工排查时间。若超时则归"困难"，加入 §6 失败档案 + deferred queue。
3. **vLLM 是否安装**：当前环境是否已装 vLLM（用于 RMSNorm impl）？若未装，需先 `pip install vllm` 或 fallback 到 flash_attn `rms_norm` + 手写 add（v2 需在 prereq 验证）
4. **flashinfer page_size 参数化**：当前 `flashinfer_decode.py` 默认 page_size=16，需验证脚本是否能传 page_size 参数（D8/D9 cfg 依赖此能力）
