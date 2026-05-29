# memSu Product Roadmap

memSu 的主线不是做一个越来越复杂的记忆框架，而是做一个本机工作辅助闭环：

1. 用户提供自己的偏好 context，或者从冷启动开始。
2. memSu 定时观察工作设备上的低风险信息。
3. 用户把乱写资料、未来事项和任务碎片放进 inbox；agent 整理成结构化任务板并归档来源。
4. 模型整理偏好、观察、inbox、任务板、记忆和历史结果，判断当前用户需要什么协助。
5. 模型在可审计边界内自主执行低风险验证和状态更新；高风险动作进入确认流。

旧的 `PLAN_V2.md`、`PLAN_V3.md`、`PLAN_V4.md`、`PLAN_AUTO.md` 继续作为技术设计历史保留。本文件是新的产品路线图入口。

This roadmap is intentionally user-context-shaped rather than project-context-shaped.
Personal alignment files, operating principles, and work preferences belong in
the user's cold-start context, for example `${MEMSU_HOME:-~/.memsu}/inspire.md`
or `inspire.d/*.md`, not as baked-in product doctrine.

每个本地 memSu home 还应该有一个给 agent 的入口文件：

```text
${MEMSU_HOME:-~/.memsu}/AGENTS.md
```

它不是项目 doctrine，而是用户本机的操作说明：agent 先读它，再读 `status`、
`inspire`、`inbox`、`tasks`、`advance agenda` 和 observe evidence。

## Product Loop

```text
Local AGENTS.md / agent read order
        |
        v
User context / cold start
        |
        v
Scheduled device observation
        |
        v
Human inbox / messy notes
        |
        v
Structured Markdown task board
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

`AGENTS.md` 是 agent 面向本用户的使用说明，不是偏好本身。它应该告诉 agent：读什么、怎么整理 inbox、怎么认领任务、怎么记录证据、什么动作需要确认。用户偏好和私人 alignment 仍放在 `inspire.md`、`inspire.d/` 或 inbox 里。

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

### 3. Human Inbox And Manual Task Board

人类不应该被迫直接维护结构化任务板。v1 增加一个更宽松的用户入口：

```text
${MEMSU_HOME:-~/.memsu}/inbox/
${MEMSU_HOME:-~/.memsu}/inbox/archive/
```

用户可以在 `inbox/` 里随便放 Markdown/TXT：未来要做的事、资料、链接、半成型任务、上下文片段、甚至一段抱怨。agent 的工作是读取这些材料，把真正可执行的事项整理进任务板；整理成功后，把原始文件移动到 `inbox/archive/`，并在任务里保留 `source:` 归档路径。

这层 inbox 是给人类的低摩擦入口；`tasks.md` 是给 agent 的结构化工作面。

v1 任务板标准来源是：

```text
${MEMSU_HOME:-~/.memsu}/tasks.md
```

任务板由用户拥有，可以手写，也可以主要由 agent 从 inbox 整理生成。memSu 只需要在 v1 解析最小结构：

- 标题
- 状态
- 优先级
- 上下文
- 来源
- 认领租约
- 阻塞点
- 验收条件

建议模板：

```markdown
# memSu Tasks

## [todo][P1] Stabilize observe-to-assistance loop

scope: project:memSu
context: 用户希望 roadmap 回到产品闭环，不再按技术版本堆叠。
source: inbox/archive/2026-05-28/20260528T100000Z-roadmap-note.md
claimed_by:
claimed_at:
claim_until:
blocked: 任务板还不是一等输入。

acceptance:
- advance agenda 会读取任务板。
- 建议能引用 observe snapshot 和 task id。

notes:
- 任务板是用户手写文件，memSu 可以更新状态，但必须留下状态变更记录。
```

状态建议从少量可读词开始：`todo`、`active`、`blocked`、`verifying`、`done`、`dropped`。不要把认领塞进状态里，也不要使用 `in_progress`。agent 认领用 `claimed_by`、`claimed_at`、`claim_until` 表示临时租约；任务本身仍保持原状态。不要在 v1 把格式做成复杂 DSL；模型应该能容忍用户的自然 Markdown。对于更乱的输入，不要求用户修格式，直接放进 inbox，由 agent 归纳。

任务不会因为写进 `tasks.md` 自动执行。执行入口分三类：用户手动叫某个 agent 做；agent 读取 `advance agenda` 后主动认领；或用户额外配置 cron、Codex automation、Hermes workflow 定时读取 agenda 并派发。

### 4. Assistance Analysis

`advance agenda` 应成为协助分析入口。它不只看观察结果，也要把 inbox 和任务板作为一等输入，与记忆、候选记忆、冲突、历史验证结果一起整理。

输出目标不是泛泛的建议，而是回答：

- 用户现在有哪些活跃任务线？
- inbox 里有哪些未整理材料？
- 哪些任务最需要帮助？
- 哪些上下文已经足够，哪些还缺证据？
- 哪些协助可以自动验证？
- 哪些动作需要用户确认？

模型可以自由综合信息，不要过早写死排序规则。系统只要求输出带证据、风险等级、预期收益和下一步。排序、取舍、追问和协助路径应尽量交给模型判断，而不是用固定权重替模型做决定。

### 5. Autonomous Verify And State Update

默认自主边界是“低风险改动可自动”。

这里的关键不是把 `advance run` 做成固定 checklist，而是把它做成模型主导的执行回合：模型读取当前 context、任务板、观察证据、历史结果和可用能力后，自行选择最值得做的一步；系统只要求它说明证据、风险、预期结果、执行内容和写回状态。

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

因此 R5/R6 的实现应该优先暴露能力和上下文，让模型做选择；只有风险边界、证据要求、审计格式和回滚说明是硬约束。不要把“选择建议 -> 执行验证 -> 写回状态”写成只能按固定顺序运行的流程，它应该是模型在当前局面里可以自由组合的一组低风险动作。

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

- 新增 `${MEMSU_HOME:-~/.memsu}/AGENTS.md` 默认 agent guide。
- 新增 `guide` CLI：
  - `python -m memsu guide init`
  - `python -m memsu guide path`
  - `python -m memsu guide show`
- 继续使用 `inspire.md` 和 `inspire.d/*.md`。
- 支持用户把个人 alignment、工作原则或外部 context 放进冷启动目录；这些内容只影响该用户的本地 memSu，不进入项目内置文档。
- 把默认模板从“观察 checklist”调整成“偏好、目标、隐私、工作区提示”。
- `init` 和 `doctor` 会创建 agent guide；`status` 和 discovery manifest 会暴露 agent guide 路径。
- `status` 和 `doctor` 能提示 context 是否存在、是否为空、是否需要初始化。

Success check:

- 新 agent 只看 `.memsu/AGENTS.md` 和 `python -m memsu status`，就能知道如何继续使用本地 memSu。
- 新用户运行 `memsu init` 后能看到清晰的 context 文件位置。
- 用户不写 context 时，memSu 也能运行 observe，并明确标出未知项。

Current status:

- Implemented: local `AGENTS.md` template, `guide init`, `guide path`,
  `guide show`, init/doctor creation, status/discovery path exposure, and docs.

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

### R3: Human Inbox And Manual Task Board

Goal: 让用户可以低摩擦丢资料，同时让整理后的任务板成为产品闭环的一等输入。

Deliverables:

- 新增 `${MEMSU_HOME:-~/.memsu}/inbox/` 和 `inbox/archive/`，作为人类乱写入口和归档区。
- 新增 `${MEMSU_HOME:-~/.memsu}/tasks.md` 默认模板。
- 规划并实现 inbox CLI：
  - `python -m memsu inbox init`
  - `python -m memsu inbox list`
  - `python -m memsu inbox add`
  - `python -m memsu inbox promote <file>`
- 规划并实现任务 CLI：
  - `python -m memsu task init`
  - `python -m memsu task list`
  - `python -m memsu task show <task_id>`
  - `python -m memsu task claim <task_id> --agent ...`
  - `python -m memsu task release <task_id> --agent ...`
  - `python -m memsu task update <task_id> --status ...`
- 解析 Markdown 标题、状态、优先级、上下文、来源、认领字段、阻塞点和验收条件。
- 对任务状态更新保留 history，避免静默覆盖用户意图。
- 对 agent 认领保留 claim lease 和 history，避免多个 agent 同时抢同一任务。
- `inbox promote` 把整理后的任务写入任务板，并把原始文件移动到 `inbox/archive/`。

Success check:

- 用户乱写一个 inbox 文件后，agent 能 promote 成任务并归档源文件。
- 用户手写或 agent 整理出一个任务后，memSu 能稳定列出任务、识别状态、认领信息和关联 scope。

Current status:

- Implemented: `inbox/` and `inbox/archive/`, `inbox init`, `inbox path`,
  `inbox list`, `inbox add`, `inbox promote`, `tasks.md` template, `task init`,
  `task path`, `task list`, `task show`, `task claim`, `task release`,
  `task update`, Markdown parsing, source parsing, claim lease parsing, archive
  provenance, and status/history append.

### R4: Assistance Analysis

Goal: 让 memSu 能回答“现在最该帮用户什么”。

Deliverables:

- `advance agenda` 读取 inbox 和任务板作为一等输入。
- agenda 综合 inbox、任务、observe、memory、candidate、conflict、prior outcomes。
- 输出 active worklines、recommended assistance、automatic verification candidates、confirmation-required actions。
- 对每条建议记录 evidence、risk level、expected benefit 和 unknowns。

Success check:

- 有任务板和 observe snapshot 时，agenda 能给出具体、可执行、带证据的协助建议。
- 有 inbox 未整理材料时，agenda 会建议 `organize_inbox`，但不会把粗糙材料直接当作已承诺任务。
- 没有足够证据时，agenda 会提出最小观察或澄清路径。

Current status:

- Implemented: `advance agenda` reads unprocessed inbox files and open task
  board items as first-class inputs, creates `organize_inbox` suggestions, and
  creates task-id-backed assistance suggestions.

### R5: Autonomous Verify And State Change

Goal: 让 memSu 不止建议，还能由模型在低风险边界内选择并推进下一步。

Deliverables:

- `advance run` 进入 model-led execution turn：把 context、任务板、观察证据、agenda、历史结果和能力清单交给模型判断。
- 模型可以选择运行验证命令、写回任务状态、记录 workflow result、提出 memory candidate、或在范围清晰时做小型低风险本地改动。
- 验证结果和状态变化写回 advancement history、workflow event 和任务板。
- 支持小型低风险文件改动，但必须记录范围、证据、验证结果和回滚说明。
- L3/L4 动作仍走 policy proposal 和 explicit confirmation。

Success check:

- 对低风险任务，memSu 能让模型自主选择合理动作，例如运行验证、记录结果，并把任务从 `active` 推进到 `verifying` 或 `done`。
- 对高风险任务，memSu 只创建待确认 proposal。
- 执行日志能解释“为什么是这一步”，而不只是显示命中了哪条固定规则。

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

## Public Interfaces

已实现的 R3/R4 接口：

```powershell
python -m memsu guide path
python -m memsu guide init
python -m memsu guide show
python -m memsu inbox path
python -m memsu inbox init
python -m memsu inbox list
python -m memsu inbox add
python -m memsu inbox promote <file>
python -m memsu task path
python -m memsu task init
python -m memsu task list
python -m memsu task show <task_id>
python -m memsu task claim <task_id> --agent codex --lease 2h
python -m memsu task release <task_id> --agent codex
python -m memsu task update <task_id> --status active
python -m memsu advance agenda
```

仍属于 R5 方向、尚未实现完整自动验证闭环的接口：

```powershell
python -m memsu advance run
```

Expected behavior:

- `guide init` 创建本地 `AGENTS.md`，让 agent 知道 read order、inbox/task/advance 用法和风险边界。
- `guide path` 和 `guide show` 让外部 agent 可以稳定发现并读取本地指导。
- `inbox init` 创建人类乱写入口和 archive 目录。
- `inbox promote` 把 agent 整理后的任务追加到 `tasks.md`，并把源文件移动到 `inbox/archive/`。
- `task init` 创建用户拥有的 `tasks.md` 模板，不覆盖用户编辑，除非显式 `--force`。
- `task list` 和 `task show` 读取 Markdown 并输出结构化 JSON。
- `task claim` 和 `task release` 管理 agent 认领租约，不改变任务状态。
- `task update` 可以更新任务状态，但必须保留变更记录。
- `advance agenda` 把 inbox 和任务板作为一等输入。
- `advance run` 未来可以执行低风险验证，并把验证结果写回 memSu 状态或任务板状态。

## Acceptance Scenarios

- Cold start: 没有偏好、inbox 和任务板时，memSu 能创建最小模板、运行 observe，并说明未知项。
- Agent onboarding: 新 agent 进入 `.memsu` 后，通过 `AGENTS.md` 能知道先读哪些文件、如何整理 inbox、如何认领任务、如何写回状态、哪些动作需要确认。
- Messy input: 用户把未来任务或资料乱写进 `inbox/` 后，agent 能整理成任务、写入 `tasks.md`、归档原文件，并保留 `source:`。
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
