# §4 Methodology 写作规则

> 标杆论文: Snake (MICRO'23) + DMP (HPCA'24)
> 目标篇幅: 0.5 pages

## 一、总体原则

### 规则 M-1：极度精简，信息密度最大化

Methodology 是全文最短的节（0.5 page），但必须提供读者复现所需的全部信息。**不写散文，用加粗标签分块。**

**Snake 示范**：分四个加粗标题段落——Simulation / Baseline benchmark suites / Comparison Metrics / Comparison Points
**DMP 示范**：分三个加粗标签——Prefetchers / Workloads / （含 Table IV）

## 二、段落结构

### 规则 M-2：四块结构

```
**Simulation Infrastructure.**
    仿真器名称 + 版本 + 模式（trace-driven）
    GPU 配置（SM 数、warp/SM、L1 size、L2 size）
    一句话：配置文件位置（可选）

**Benchmarks and Datasets.**
    Table X：benchmark × dataset 矩阵
    每行标注：算法名 | Suite | IMA Pattern 类型（映射到 §2 分类）
    数据集标注：顶点数 | 边数 | 类型

**Comparison Points.**
    逐一编号定义每个 baseline：
    (1) No Prefetch — 性能下界
    (2) stride-INTRA (+ IMA gating) — 参考 Snake
    (3) Snake — MICRO'23
    ...
    (N) Ideal L1D — 性能上界

**Metrics.**
    逐一定义每个评估指标：
    - IPC Speedup: ...
    - IMA Coverage: ...
    - Accuracy: ...
    - Timeliness: ...
```

### 规则 M-3：Baseline 定义格式

每个 baseline 用一句话完整定义，包含三要素：**名称 + 来源 + 一句话说明**。

**Snake 示范**：9 个 baseline，编号 (1)-(9)，每个一句话。Evaluation 节中引用编号即可，不重复定义。

**对 GRASP**：

| # | Baseline | 来源 | 说明 |
|---|----------|------|------|
| 1 | No Prefetch | — | 性能下界 |
| 2 | stride-INTRA | 参考 Snake | Intra-warp stride, IMA PC 过滤 |
| 3 | Snake | MICRO'23 | Variable-length chain stride |
| 4 | CAPS | IPDPS'18 | CTA-aware stride |
| 5 | Spare Register | HPCA'14 | 唯一 GPU IMA 前驱 |
| 6 | Ideal L1D | — | 性能上界 (load-only perfect L1) |

## 三、Table 设计

### 规则 M-4：Benchmark Table 映射到分类框架

DMP Table IV 的做法：每个 workload 标注其 indirect access pattern 类型，直接映射到 §2 的分类。

**对 GRASP**：Benchmark Table 应标注每个 workload 属于四类 IMA Pattern 中的哪一类（I/II/III/IV），让 Evaluation 中的结果可以按 Pattern 类别分组分析。

### 规则 M-5：GPU 配置用行内文字，不单独成表

GPU 配置信息（SM80_A100, 108 SMs, 64 warps/SM, 32KB L1D, 40MB L2）用一句话写在 Simulation 段内。**不**需要像 CPU 论文那样列出详细的 pipeline 参数表——GPU simulator 配置文件本身就是标准化的。

## 四、过渡

### 规则 M-6：Methodology → Evaluation 无需过渡

Methodology 的最后一个 baseline 定义句结束后，直接 §5 Evaluation 开始。不需要 "In the next section, we present..." 这类过渡。

## 五、常见陷阱

### 规则 M-7：避免的写法

| 陷阱 | 为什么不好 | 正确做法 |
|------|----------|---------|
| 把 GRASP 参数配置放在 Methodology | 读者还不知道组件细节 | 放在 §3 Design 的各子节末尾 |
| 把 Metric 定义展开成长段 | 浪费篇幅 | 每个 metric 一句话 |
| 不列 Ideal baseline | 缺乏上界参考 | 必须有 Ideal L1D 作为天花板 |
| Benchmark 描述重复 §2 的内容 | 冗余 | Methodology 只列表，§2 才分析 |
