# memSu Product Roadmap

memSu 的主线不是做一个越来越复杂的记忆框架，而是做一个本机工作辅助闭环：

1. 用户提供自己的偏好 context，或者从冷启动开始。
2. memSu 定时观察工作设备上的低风险信息。
3. memSu 读取用户手动写入的本地 Markdown 任务板。
4. 模型整理偏好、观察、任务板、记忆和历史结果，判断当前用户需要什么协助。
5. 模型在可审计边界内自主执行低风险验证和状态更新；高风险动作进入确认流。

旧的 `PLAN_V2.md`、`PLAN_V3.md`、`PLAN_V4.md`、`PLAN_AUTO.md` 继续作为技术设计历史保留。本文件是新的产品路线图入口。

## Product Loop

```text
User context / cold start
        |
        v
Scheduled device observation
        |
        v
Manual Markdown task board
        |
        v
Assistance analysis
        |
        v
Autonomous verify / low-risk action
        |
        v
State update / memory candidates / next attention
```

### 1. Context Or Cold Start

用户可以通过 `${MEMSU_HOME:-~/.memsu}/inspire.md` 和 `inspire.d/*.md` 写入偏好、工作根目录、工具习惯、隐私边界和观察提示。没有这些信息时，memSu 也应该能冷启动：创建最小模板，运行低成本观察，并把未知项明确写出来。

Context 是提示，不是硬规则。模型应优先尊重用户表达的偏好，但仍可根据证据发现新项目、新工具和新工作线。

### 2. Scheduled Device Observation

memSu 定时观察本机低风险信息，形成可审计的工作图景。观察优先读取 metadata、摘要、状态和时间线，而不是私密正文。

初始观察面沿用现有 `observe run` 和 V4 inspire direction：

- 最近项目、文件和构建产物的时间线。
- Git 状态、最近提交、分支和工作区变化。
- Windows Recent、PowerShell history、进程和窗口标题中的低风险信号。
- 本地 agent 的 session index、标题、更新时间和已有摘要。
- memSu 自己的 events、memories、candidates、findings 和 advancement history。

观察结论必须区分事实、推断、未知和跳过项，并尽量带上 evidence id、snapshot id、event id 或文件路径。

### 3. Manual Markdown Task Board

v1 任务板标准来源是：

```text
${MEMSU_HOME:-~/.memsu}/tasks.md
```

任务板由用户拥有，可以手写。memSu 只需要在 v1 解析最小结构：

- 标题
- 状态
- 优先级
- 上下文
- 阻塞点
- 验收条件

建议模板：

```markdown
# memSu Tasks

## [todo][P1] Stabilize observe-to-assistance loop

scope: project:memSu
context: 用户希望 roadmap 回到产品闭环，不再按技术版本堆叠。
blocked: 任务板还不是一等输入。

acceptance:
- advance agenda 会读取任务板。
- 建议能引用 observe snapshot 和 task id。

notes:
- 任务板是用户手写文件，memSu 可以更新状态，但必须留下状态变更记录。
```

状态建议从少量可读词开始：`todo`、`active`、`blocked`、`verifying`、`done`、`dropped`。不要在 v1 把格式做成复杂 DSL；模型应该能容忍用户的自然 Markdown。

### 4. Assistance Analysis

`advance agenda` 应成为协助分析入口。它不只看观察结果，也要把任务板作为一等输入，与记忆、候选记忆、冲突、历史验证结果一起整理。

输出目标不是泛泛的建议，而是回答：

- 用户现在有哪些活跃任务线？
- 哪些任务最需要帮助？
- 哪些上下文已经足够，哪些还缺证据？
- 哪些协助可以自动验证？
- 哪些动作需要用户确认？

模型可以自由综合信息，不要过早写死排序规则。系统只要求输出带证据、风险等级、预期收益和下一步。

### 5. Autonomous Verify And State Update

默认自主边界是“低风险改动可自动”。

可以自动执行：

- 运行只读检查、状态检查、测试、lint、doctor、dry-run 和低风险验证命令。
- 更新 memSu 内部状态、观察记录、advancement history、memory candidate 和任务状态。
- 在证据充分、范围明确、可回滚说明清楚时，执行小型低风险本地文件改动。

必须确认或拒绝：

- 外部消息、跨 agent 敏感分享、权限变更、账号配置、发布、支付。
- 删除、不可逆操作、读取密钥或私密正文。
- 大范围重构、模糊目标下的项目文件改动。

每次自主执行都应记录：

- 为什么选择这个动作。
- 使用了哪些证据。
- 实际运行了什么。
- 变更了什么状态或文件。
- 如何验证成功或失败。
- 如有文件改动，如何回滚。

## Autonomy Principle

memSu 应假设模型能力会持续高于早期预期。路线图不应把模型困在固定 checklist 里，而应提供：

- 用户偏好和当前任务目标。
- 低风险观察工具。
- 证据账本和审计记录。
- 清晰的风险边界。
- 可回滚的执行记录。
- 对高风险动作的确认流。

规则应约束风险，不应替模型决定什么重要。模型负责发现线索、关联任务、提出或执行下一步；memSu 负责让这些行为可解释、可审计、可撤回。

## Build Sequence

### R0: Roadmap Reset

Goal: 让项目重新以产品闭环为主线。

Deliverables:

- 新增 `ROADMAP.md` 作为产品入口。
- 在 `README.md` 和 `PLAN.md` 顶部指向新路线图。
- 保留历史技术计划，避免丢失已有设计上下文。

Success check:

- 新读者先理解 Context -> Observe -> Task Board -> Understand -> Act/Verify -> Update State，而不是先理解 V2/V3/V4/AUTO。

### R1: Context And Cold Start

Goal: 让用户可以提供偏好 context；没有偏好时也能启动。

Deliverables:

- 继续使用 `inspire.md` 和 `inspire.d/*.md`。
- 把默认模板从“观察 checklist”调整成“偏好、目标、隐私、工作区提示”。
- `status` 和 `doctor` 能提示 context 是否存在、是否为空、是否需要初始化。

Success check:

- 新用户运行 `memsu init` 后能看到清晰的 context 文件位置。
- 用户不写 context 时，memSu 也能运行 observe，并明确标出未知项。

### R2: Scheduled Device Observation

Goal: 形成定时、低成本、低风险的本机工作图景。

Deliverables:

- 复用现有 `observe run` 和 Windows Scheduled Task 脚本。
- 观察输出继续写入 `${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md`。
- 观察结果继续写入 SQLite snapshot、event、finding 和 evidence records。
- 明确区分事实、推断、未知、跳过敏感源。

Success check:

- 定时 observe 不依赖正在进行的聊天。
- 观察结果能支撑后续任务分析，而不是只做日志归档。

### R3: Manual Task Board

Goal: 让用户手写任务板成为产品闭环的一等输入。

Deliverables:

- 新增 `${MEMSU_HOME:-~/.memsu}/tasks.md` 默认模板。
- 规划并实现任务 CLI：
  - `python -m memsu task init`
  - `python -m memsu task list`
  - `python -m memsu task show <task_id>`
  - `python -m memsu task update <task_id> --status ...`
- 解析 Markdown 标题、状态、优先级、上下文、阻塞点和验收条件。
- 对任务状态更新保留 history，避免静默覆盖用户意图。

Success check:

- 用户手写一个任务后，memSu 能稳定列出任务、识别状态和关联 scope。

### R4: Assistance Analysis

Goal: 让 memSu 能回答“现在最该帮用户什么”。

Deliverables:

- `advance agenda` 读取任务板作为一等输入。
- agenda 综合任务、observe、memory、candidate、conflict、prior outcomes。
- 输出 active worklines、recommended assistance、automatic verification candidates、confirmation-required actions。
- 对每条建议记录 evidence、risk level、expected benefit 和 unknowns。

Success check:

- 有任务板和 observe snapshot 时，agenda 能给出具体、可执行、带证据的协助建议。
- 没有足够证据时，agenda 会提出最小观察或澄清路径。

### R5: Autonomous Verify And State Change

Goal: 让 memSu 不止建议，还能在低风险边界内推进。

Deliverables:

- `advance run` 支持执行低风险验证命令。
- 验证结果写回 advancement history 和任务状态。
- 支持小型低风险文件改动，但必须记录范围、证据、验证结果和回滚说明。
- L3/L4 动作仍走 policy proposal 和 explicit confirmation。

Success check:

- 对低风险任务，memSu 能自动运行验证、记录结果，并把任务从 `active` 推进到 `verifying` 或 `done`。
- 对高风险任务，memSu 只创建待确认 proposal。

### R6: Freer Model-Led Capabilities

Goal: 逐步开放更自由的模型主导能力，而不是不断增加固定流程。

Deliverables:

- 把 adapter 和 skill 注册成模型可选择的能力单元。
- 给每个能力声明输入、输出、最大风险、证据要求和回滚要求。
- 允许模型基于任务和证据选择能力组合。
- 对重复成功的能力组合沉淀为 skill candidate 或 workflow template。

Success check:

- 模型可以根据新工具、新项目和新任务自适应选择下一步。
- memSu 仍能解释每次选择、每条证据和每个状态变化。

## Planned Public Interfaces

这些接口是路线图方向，不要求本次文档变更同时实现代码：

```powershell
python -m memsu task init
python -m memsu task list
python -m memsu task show <task_id>
python -m memsu task update <task_id> --status active
python -m memsu advance agenda
python -m memsu advance run
```

Expected behavior:

- `task init` 创建用户拥有的 `tasks.md` 模板，不覆盖用户编辑，除非显式 `--force`。
- `task list` 和 `task show` 读取 Markdown 并输出结构化 JSON。
- `task update` 可以更新任务状态，但必须保留变更记录。
- `advance agenda` 把任务板作为一等输入。
- `advance run` 可以执行低风险验证，并把验证结果写回 memSu 状态或任务板状态。

## Acceptance Scenarios

- Cold start: 没有偏好和任务板时，memSu 能创建最小模板、运行 observe，并说明未知项。
- User context: 用户写入 `inspire.md` 后，观察和建议体现偏好，但不会把偏好当硬编码规则。
- Manual task: 用户手写一个任务后，memSu 能读取、关联观察证据，并给出下一步协助。
- Autonomous verification: 对低风险任务，memSu 能运行验证命令、记录结果、更新内部状态。
- Low-risk edit: 模型在范围明确、可回滚、证据充分时可做小改动，并写入审计记录。
- High-risk action: 外部消息、权限变更、删除、敏感读取和不可逆操作仍需要确认或拒绝。

## Relationship To Existing Plans

- `PLAN.md`: 现有实现状态和历史 phase 记录。
- `PLAN_V2.md`: deterministic observe layer。
- `PLAN_V3.md`: agent-led observation。
- `PLAN_V4.md`: inspire-driven observation。
- `PLAN_AUTO.md`: skill/adapter-controlled advancement。

后续新增功能应先说明它推进了本 roadmap 的哪一段闭环，再决定是否需要更细的技术设计文档。
