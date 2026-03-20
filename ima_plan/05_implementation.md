# 05 — GPGPU-Sim 实现计划

> 对应文件夹：`05_implementation/`（存放代码 patch、接口设计图、测试记录等）
>
> 状态：待开始（依赖 Phase 3 方案设计完成）

---

## 目标

在 GPGPU-Sim 中实现 Phase 3 选定的 prefetcher 方案，确保：
1. 功能正确：prefetch 行为符合设计文档
2. 可配置：通过 gpgpusim.config 参数控制开关和配置
3. 可观测：prefetch 行为可通过 trace 系统记录和分析
4. 不破坏已有功能：baseline / ideal L1D / 各种 trace 正常工作

---

## GPGPU-Sim 相关模块概览

### 需要修改的文件（预期）

| 文件 | 角色 | 修改内容 |
|------|------|---------|
| `gpu-cache.cc/h` | L1D/L2 cache | 添加 prefetch 请求处理逻辑 |
| `shader.cc/h` | SM / memory unit | prefetch 触发点（load 返回时 / 发射时） |
| `gpu-sim.cc` | 主仿真循环 | prefetch 统计收集 |
| `option_parser.*` | 配置解析 | 添加 prefetcher 相关配置项 |
| `l1_tracer.cc` | L1 trace | 标记 prefetch 请求（区分 demand vs prefetch） |

### 不应修改的（保持兼容）

- `accel-sim.cc/h`：trace 前端，与 prefetch 无关
- `ISA_Def/`：指令定义不需要改（除非做 ISA 扩展方案）

---

## 实现步骤（高层）

### Step 1：Prefetch Infrastructure（基础框架）

建立 prefetch 请求的基本管道，不含具体 pattern detection：

- [ ] 定义 `prefetch_request` 数据结构（source PC、target address、type、confidence）
- [ ] 在 `gpu-cache.cc` 中添加 prefetch 请求入口（与 demand request 区分）
- [ ] 添加 prefetch 请求的 MSHR 处理（是否共享 MSHR？单独 prefetch buffer？）
- [ ] 添加配置项：`-gpgpu_prefetch_enable`, `-gpgpu_prefetch_type`, `-gpgpu_prefetch_queue_size` 等
- [ ] 添加统计计数器：prefetch issued / useful / useless / late / polluting

### Step 2：Pattern Detection Module（模式检测模块）

根据 Phase 3 选定的方案实现具体的 pattern detection 逻辑：

- [ ] 实现 pattern table（PC-indexed 或 address-indexed）
- [ ] 实现 IMA 模式识别算法
- [ ] 实现 prefetch address generation
- [ ] 实现 confidence / throttling 逻辑

### Step 3：Integration & Testing（集成与测试）

- [ ] 单元测试：用简单 trace 验证 prefetch 触发和地址正确性
- [ ] 回归测试：确保 prefetch off 时行为与 baseline 完全一致
- [ ] 功能测试：在一个 IMA workload 上验证 prefetch 是否产生 L1 hit
- [ ] 性能测试：在全部 workload 上收集 IPC 对比数据

### Step 4：Trace Integration（Trace 系统集成）

- [ ] 在 L1 trace 中标记 prefetch 请求（新增 op type 或 flag）
- [ ] 添加 prefetch accuracy trace（useful vs useless 统计随时间变化）
- [ ] 可选：在 issue trace 中标记因 prefetch hit 而避免的 stall

---

## 编码规范

- 遵循 GPGPU-Sim 现有代码风格（C++，类 C 命名）
- 新增文件放在 `src/gpgpu-sim/` 下，如 `prefetcher.cc/h`
- 所有新增配置项以 `-gpgpu_prefetch_` 为前缀
- 所有 prefetch 相关统计以 `prefetch_` 为前缀
- 使用 `#ifdef` 或运行时 flag 控制，确保可完全关闭

---

## 预期产出

1. **代码 patch**：可合并到当前仓库的 prefetcher 实现
2. **测试报告**：回归测试 + 功能测试结果
3. **实现文档**：接口说明、配置项说明、使用方法

---

## 文件夹内容规划

```
05_implementation/
├── design/                 # 模块接口设计图、数据流图
├── patches/                # 重要的代码变更记录 / diff
├── test_records/           # 测试记录（回归测试、功能测试）
└── notes.md                # 实现过程中的笔记和踩坑记录
```

---

## 关键问题（待讨论）

1. Prefetch 请求是否与 demand 请求共享 MSHR？（共享简单但可能阻塞 demand；独立则需额外硬件）
2. Prefetch 在 cache 中的优先级？（低于 demand？eviction 时优先踢出 prefetch line？）
3. 是否需要 prefetch buffer（不进 L1，单独缓存）？
4. `traceL1` 脚本是否需要新增 prefetch 相关的命令行选项？
