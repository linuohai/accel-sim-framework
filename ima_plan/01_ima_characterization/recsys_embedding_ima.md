# 现代推荐 / Embedding IMA 调研线

> 作用：作为图算法 IMA 之外的补充调研线，聚焦 recommendation / embedding-heavy workload。
>
> 目标：找到能直接落到 CUDA kernel 的现代推荐模型 IMA 证据，并把它和 Gardenia SGD baseline 做对照。

---

## 1. 为什么要单独拆出来

现代推荐系统的主热点通常不是图算法式的邻接遍历，而是：

- 稀疏 ID 到 embedding table 的 lookup
- 多表 batched gather
- 读后聚合 / reduce
- 训练时的 embedding update / atomic write

这类 workload 的 IMA 形态和 BFS / SpMV 不同，但仍然具备“用数据当索引”的核心特征，因此适合纳入同一 IMA 研究框架。

---

## 2. 当前仓库里的可用入口

### 2.1 直接可分析的 CUDA baseline

- `gpu-app-collection/gardenia/src/sgd/base.cu`
- `gpu-app-collection/gardenia/src/sgd/vector.cu`
- `gpu-app-collection/gardenia/src/sgd/sgd.h`

这条线是仓库里最明确的“推荐系统 + CUDA 源码”实现，适合作为 baseline：

- `column_indices[offset]` 提供稀疏交互索引
- `user_lv[...]` / `item_lv[...]` 提供 embedding / latent vector 访问
- `vector.cu` 还体现了 warp 协同和向量化访问方式

### 2.2 框架入口，但不是主证据

- `gpu-app-collection/src/cuda/mlperf/`
- `gpu-app-collection/src/cuda/mlperf_inference/`
- `gpu-app-collection/src/cuda/huggingface/`

当前仓库里这些目录更像 benchmark / launcher / example 入口，不等价于“推荐系统 CUDA kernel 源码”。它们的作用是：

- 提供现代 workload 的线索
- 定位上游模型实现
- 判断是否有可追踪的 embedding-heavy 代码路径

---

## 3. 调研范围定义

本线采用“宽定义”的现代推荐 / embedding IMA：

- 严格推荐系统：DLRM、two-tower、CTR / ranking、embedding bag
- 近似代理：token embedding、table lookup、retrieval-heavy GPU kernel
- 不纳入主线：纯 launcher、纯 Python 例子、没有真实 CUDA kernel 的框架入口

如果某个 workload 只在上游仓库存在 CUDA 实现，而本仓库里只有入口脚本，也仍然可以纳入，但必须明确标注“来源于 upstream implementation”。

---

## 4. 分析方法

### 4.1 源码层

重点回答四个问题：

- 索引来自哪里
- embedding table 是单表还是多表
- 访问是读为主还是读改写
- 是否存在一对多复用

### 4.2 SASS 层

重点看这几类特征：

- `LDG -> IMAD.WIDE -> LDG` 的 gather 链
- 多表 lookup 共享同一个 index 的复用链
- `ATOM / STG` 参与的训练更新路径
- warp 协同的 gather / reduce 模式

### 4.3 Trace 层

重点收集：

- L1 miss / L2 miss
- issue stall 与同步等待
- 同一表的热点 PC 分布
- warp 内与 warp 间的 locality 差异

---

## 5. 建议的分类维度

| 维度 | 取值示例 | 用途 |
|------|---------|------|
| Lookup 结构 | single-table gather / multi-table gather / hashed lookup | 区分索引路径复杂度 |
| 数据复用 | hot table / cold table / one-to-many | 判断 prefetch ROI |
| 访问阶段 | inference / training | 判断是否有 write-back 和原子冲突 |
| 执行上下文 | thread-serial / warp-cooperative | 判断 locality 和 coalescing 机会 |
| 依赖深度 | 直接 lookup / lookup-after-aggregate | 区分纯 gather 和更深依赖链 |

---

## 6. 交付物

- 一个现代推荐 / embedding IMA 的候选表
- 一个与 SGD baseline 的对照表
- 一份源码到 SASS 的依赖链总结
- 一份 trace 级别的 miss / stall 归因总结

---

## 7. 结论性约束

- 不能把 `mlperf` 目录里的 launcher 误当作 kernel 证据
- 不能把所有 embedding-heavy workload 都自动等价为 recommendation system
- 但只要存在“稀疏 ID 作为索引”的主路径，就应该纳入 IMA 研究框架
