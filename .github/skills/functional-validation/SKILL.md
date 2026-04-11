---
name: functional-validation
description: 'Validate complex features before claiming they work. Use when debugging or implementing any behavior with external calls, side effects, unclear parameters, file writes, Hexo commands, subprocesses, browser automation, network requests, uploads, or other hard-to-observe mechanisms. Identifies which parts are complex, isolates them into single-point checks, executes them, collects evidence, and closes the verification loop with tool-based or human confirmation.'
argument-hint: 'Describe the feature, external behaviors, and expected evidence.'
---

# Functional Validation

用这个 skill 的目标不是“猜哪里有 bug”，而是把一个功能拆成可验证的单点，逐个拿证据确认，最后再回到整体链路。

## When to Use

- 功能包含外部调用，例如保存文件、执行 Hexo、调用 git、上传图片、发网络请求、跑浏览器、调用子进程
- 过程复杂，参数来源不透明，输入输出契约不清楚
- 代码看起来“差不多对”，但一跑就出问题
- agent 打算声称“已经修好”之前，需要先补功能校验闭环
- 某个链路跨越多个模块，必须先确认每个关键单点都能独立工作

## What Counts As A Complex Function

满足任一条，就默认属于“复杂功能”，需要单独校验：

- 有外部副作用：写文件、删文件、改仓库、发请求、启动服务、截图、发布
- 依赖外部环境：路径、端口、配置、环境变量、API key、Node/Python/Hexo 等运行时
- 调用边界不清楚：参数结构、返回值格式、异常语义不明确
- 需要异步、并发、状态注入、事件循环、跨进程协作
- 失败后难以直接观察根因，或者错误信息不够指向性

如果一个功能只是纯内存计算、无副作用、输入输出明确，通常不属于这里的重点。

## Core Rule

先做单点功能校验，再做链路联调。不要在没有证据的情况下直接说“这个功能应该能用”。

校验过程中产生的证据必须保留到人类完成审计或明确允许清理为止。失败证据同样要保留，不能因为“已经知道错了”就删除。

## Procedure

1. 明确目标功能。
2. 列出这条链路上的所有关键步骤，并标出哪些步骤属于复杂功能。
3. 对每个复杂功能建立“单点校验项”：输入是什么，预期输出是什么，副作用是什么，如何观察成功或失败。
4. 优先为单点校验项准备最小验证方式：单元测试、小脚本、直接工具调用、受控命令执行。
5. 执行单点校验，记录证据，不要只凭代码阅读下结论。
6. 如果单点失败，先修这个单点，再重复执行同一个校验，直到拿到通过证据。
7. 单点都通过后，再执行完整链路验证，确认模块之间的参数传递和状态衔接也成立。
8. 最后输出验证结论：哪些已证实可用，哪些仍未证实，缺的证据是什么。

## Validation Loop Per Complex Function

对每个复杂功能，按这个闭环执行：

1. 定义边界：谁调用它，传什么参数，它应该产出什么。
2. 定义观测点：日志、返回值、生成文件、截图、状态变化、命令输出、远端结果。
3. 执行最小验证。
4. 对照预期检查证据。
5. 如果不符合，定位是输入错、实现错、环境错，还是校验方式不够好。
6. 修复后重新执行同一个验证，不允许只改代码不复测。

## Decision Points

### If The Function Can Be Isolated Cleanly

优先写测试或最小调用样例，把验证范围收窄到这个函数本身。

### If The Function Depends On External Runtime

先确认环境和参数，再跑最小外部调用。例子：

- 保存文件：检查目标路径、文件名、编码、实际落盘内容
- Hexo：检查工作目录、命令、生成产物、文章 URL 或 abbrlink
- 截图：检查页面是否可达、选择器是否存在、输出图片是否生成
- 上传：检查认证、目标仓库/分支/路径、返回 URL 是否真实可用

### If A Single-Point Test Is Hard To Write

至少构造一个最小可重复的脚本或直接工具调用，并要求可观察证据。必要时让 agent 自主调用工具验证；如果工具不足，再请求人工确认。

### If Single Points Pass But End-To-End Still Fails

问题大概率在边界传递，而不是单点能力本身。重点检查：

- 参数名和参数值是否在模块之间变形
- 状态是否真正写入并被后续步骤读取
- 相对路径/工作目录是否变化
- 异步调用是否丢结果、丢上下文或重复进入事件循环

## Evidence Requirements

每次校验至少拿到一种可审计证据：

- 通过的测试
- 真实命令输出
- 生成的文件内容或文件存在性
- 截图路径和截图成功结果
- 返回值或日志中可确认的关键字段
- 人工确认结果

并且这些证据必须满足留痕要求：

- 产物要保留到人类审计完成，不能在总结前删除
- 失败校验的截图、日志、输出文件同样必须保留
- 如果证据是临时路径，要在输出里明确写出路径，确保后续能回看
- 如果不得不清理产物，必须先得到用户同意，或先把证据转存到稳定位置

如果没有证据，就视为“未验证”，不是“已完成”。

## Output Format

在执行这个 skill 时，优先给出一个简短的功能校验计划，至少包含：

- 目标功能
- 复杂功能清单
- 每个复杂功能的验证方式
- 预期证据
- 当前状态：未验证 / 失败 / 已验证

验证结束时，明确给出：

- 已验证通过的单点
- 仍然失败或未验证的单点
- 完整链路是否真的闭环
- 保留下来的审计证据路径
- 下一步最小动作

## Completion Criteria

只有同时满足下面几条，才可以说“功能已验证”：

- 已识别出所有关键复杂功能
- 每个复杂功能都做过单点执行
- 每个复杂功能都有通过或失败的明确证据
- 每份关键证据在结论给出时仍然可访问，便于人类复核
- 修复过的地方已经重新验证，不是只改了代码
- 至少做过一次完整链路验证，确认单点之间接得上

## Anti-Patterns

- 只读代码，不执行验证
- 把多个复杂点混在一起改，最后不知道是哪一步坏了
- 只看异常信息，不补观测点
- 单点没过就继续推进整体联调
- 没有证据就宣称“应该可以了”
- 修完不回归原来的失败用例
- 为了“环境整洁”提前删除失败截图、日志或其它审计证据

## Example Prompts

- 用 functional-validation 检查博客写作插件里的预览链路，识别复杂功能并逐个验证
- 用 functional-validation 校验保存草稿、Hexo 生成、读取 abbrlink、截图这四个单点是否真的闭环
- 用 functional-validation 帮我把上传图片功能拆成可验证步骤，并给出每一步需要的证据