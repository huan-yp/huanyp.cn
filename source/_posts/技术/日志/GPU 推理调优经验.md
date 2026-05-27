---
title: GPU 推理调优经验
categories:
  - 技术
  - 日志
tags:
  - pytorch
  - Agent
date: 2026-05-27 17:00:00
---

## 调优经验

核心还是打实际的 Profile 数据，耗时和显存都是。

意识到问题，合理选择 AI 的方案就行。

### 显存相关

动态分配显存的 fragmentation 问题比较严重，尽量还是用手写 Pool 的方案，更稳定。

### CUDA graph

关于动态 shape（主要是不同 batch_size），一般是采用捕获多个 graph，**共享预分配显存池**，然后请求做 Padding。

*由于现代硬件关于 zero padding 有稀疏算力处理，所以性能退化不严重。*

捕获的时候会定死执行路径（分支，循环步数之类的），重放的时候必须一致。

### 速度相关

#### 基本方案

- CUDA graph + torch.compile
- 攒调度的 Batch，通常 Batch 越大平均开销越低。

#### 进阶方案

- 找找有没有 CPU bound 之类的优化掉，比如零碎的拼接操作，显存分配等。

### 正确性相关

一定要建立自动化的简单 benchmark，建立好 baseline 之后再开始优化。

### 工作交接相关

AI 改的代码 commit 的时候需要人类读核心 diff 并理解，利于交接。

核心路径需要减少分支，降低人类阅读的心智负担。

*似乎可以考虑让 AI 审查核心 diff*。



### AI 使用相关

1M 的 context 上下文退化比较严重，可以让它生成交接报告，新的 chat 可以获取新的洞见。

### Future Exploration

- 为什么有 Batch 总耗时还是会增长。
- 如何评估理论算力和实际耗时的差距。
