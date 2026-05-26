from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import default_inspire_dir, default_inspire_path


DEFAULT_INSPIRE = """# memSu V4 观察启发配置

这个文件由用户拥有，用中文描述 memSu V4 agent-led observe 在本机观察时应该关注什么、避免什么、如何输出结论。

V4 原则：写观察方向，不写死具体目录。agent 应该在运行时通过用户 home、Windows Recent、Git 仓库、shell 历史、进程、agent 元数据和已有 memSu evidence 自己发现具体路径。

## 总体目标

memSu 不是隐藏监控系统，而是本机多 agent 长期记忆监督层。观察时优先理解显式工作流和本地开发上下文，帮助 Hermes / Codex / Gemini / Claude / Kimi / OpenClaw 等工具共享可审计的长期记忆。

观察时请重点关注：

- 我最近主要在做哪些项目线、架构线和调试线。
- 本机上 AI agent / CLI / IDE / 自动化工具是否有新增、卸载、活跃、停用或迁移迹象。
- Codex、Claude、Kimi、Gemini、Hermes、OpenClaw 等本地 agent / AI 工具最近留下的非敏感元数据和 summary，尤其是 agent session 内容摘要。
- 重复出现的流程是否适合沉淀为 Hermes skill、memSu adapter、cron workflow 或项目规则。
- 项目决策、用户偏好、失败教训、约束和修正是否值得形成 memory candidate。
- 当前证据和旧记忆之间是否存在冲突、过期或需要降权的内容。

## V4 最小观察面

不要把这些写成硬编码路径清单；它们是每次观察至少要考虑的信号面。

- 文件修改时间：常用工作根、文档/下载/桌面、Android 项目根、构建输出区域、近期产物目录。
- Git 记录：重点仓库和最近活跃仓库的 `git log --since`、`git status`、`git show --stat`。
- Windows 最近打开项目：Recent 快捷方式元数据，用来判断最近打开过的 APK、目录、图片、工具、压缩包或项目。
- PowerShell 历史：最近执行过的 Gradle、ADB、agent、APK/签名/发布相关命令。
- 当前运行进程：IDE、浏览器窗口、Codex/Hermes/Java/Gradle/ADB/终端等仍在运行的进程和窗口标题。
- 本地 agent 会话元数据：覆盖 Codex、Claude、Kimi、Gemini、Hermes、OpenClaw 等；只看会话标题、更新时间、summary/索引；默认不展开完整对话正文。
- 构建/发布产物：APK、加固输出、market 包、zip、png、下载产物等最近生成或打开的文件。

## 观察风格

- 默认中文输出。
- 先给结论，再列证据。
- 明确区分：事实、推断、未知、建议。
- 不要把“文件时间戳活跃”说成“用户一定在做某事”；只能说“有迹象显示”。
- 重要结论必须附证据路径、snapshot id、run id、evidence id 或可复查的命令结果。
- 对 memory candidate 默认 review-first，不自动接受。
- 对重复流程，只提出“是否做成 skill/adapter”的建议，不擅自创建，除非用户明确要求。

## Agent session 内容摘要要求

对于 agent 相关信息，不只看活跃度和文件元数据，还要尽量形成中文 session 内容摘要。

优先摘要来源：各本地 agent 的 session index、history、rollout summary、conversation metadata、项目级 summary、MEMORY.md、AGENT_LINKS.md、任务 run summary 等非敏感元数据或已有摘要。

摘要应包含：每个 agent 最近在做什么、关联项目路径或 workspace、session 任务目标、关键操作、结论、失败点和后续建议，以及是否产生可复用 workflow / 项目决策 / 用户偏好 / memory candidate。

如果只能看到元数据，必须明确写“仅基于元数据推断”；不要伪装成读过正文。优先读取已有 summary；不直接读取私聊正文、凭证、token、cookie、private key 或敏感会话内容。

## 隐私与安全边界

- 默认只读元数据；需要内容时优先读取 summary、README、计划文件、日志摘要，而不是聊天正文或凭证文件。
- 不读取 credential、cookie、token、private key、账号 secret、浏览器会话、私聊正文、私密归档。
- 不做 keylogging、不抓屏、不抓网络流量、不后台常驻监控。
- 不自动发消息、不自动跨 agent 分享 sensitive memory、不自动改项目文件。
- L0/L1 可自动：内部维护、被动 recall、只读状态检查。
- L2 可有限主动：低风险建议、提醒、冲突提示。
- L3 必须确认：发消息、改文件、跨 agent 分享、执行有副作用操作。
- L4 拒绝：凭证捕获、隐藏监控、绕过授权、读取明确敏感内容。

## 当前长期方向

当前最重要的方向是：把 Hermes + memSu 变成本机多 agent 记忆中枢。memSu 负责显式观察、证据账本、候选记忆、审计、curator；Hermes 负责交互、工具执行、技能化和任务编排。V4 的重点是让模型主导发现，但用上述最小观察面和证据约束避免发散。
"""


DEFAULT_INSPIRE_FILES = {
    "00-v4-loop.md": """# V4 观察循环

V4 的目标不是套固定框架，而是让模型主导发现，同时用证据约束防止发散。

默认循环：

1. 先找变化：最近新增、删除、打开、构建、提交、运行、失败或迁移的迹象。
2. 再归并线索：把文件时间、Git、Recent、历史命令、进程、agent 元数据、产物归到同一项目线或工作流。
3. 再形成结论：事实、推断、未知、建议分开写。
4. 再提出候选记忆：只有稳定、重复、可复用或影响后续行为的信息才进入 review-first memory candidate。
5. 最后列下一步：证据不足时，不硬编故事，只给出下一条安全探测建议。

如果只能看到元数据，必须明确写“仅基于元数据推断”。
""",
    "05-local-signal-surfaces.md": """# V4 本地观察信号面

这个文件只写方向，不写死具体目录。agent 需要在运行时从用户 home、常见工作根、Git 仓库、Windows Recent、PowerShell 历史、进程列表、agent 元数据和已有 memSu evidence 中发现具体路径。

## 最小覆盖面

- 文件修改时间：常用工作根、文档、下载、桌面、Android 项目根、构建输出区域、近期产物目录。
- Git 记录：重点仓库和最近活跃仓库的 `git log --since`、`git status`、`git show --stat`。
- Windows 最近打开项目：通过 `.lnk` 快捷方式元数据判断最近打开过的 APK、目录、图片、工具、压缩包或项目。
- PowerShell 历史：判断最近执行过哪些本地命令，例如 Gradle、ADB、agent 工具、APK、签名、发布相关命令。
- 当前运行进程：通过进程名和窗口标题判断仍在运行的 IDE、浏览器、Codex、Hermes、Java/Gradle、ADB、终端等。
- 本地 agent 会话元数据：覆盖 Codex、Claude、Kimi、Gemini、Hermes、OpenClaw 等；只看会话标题、更新时间、summary 或索引，不默认展开完整对话正文。
- 构建/发布产物：关注 APK 输出、加固输出、market 包、Downloads 里的 APK/zip/png 等近期产物。

## 判断规则

- 先找“变化”：新增、删除、最近打开、最近构建、最近提交、最近执行。
- 再归类到项目线、agent/tool 状态、构建发布活动、可复用工作流。
- 只有证据充分时才输出结论；证据薄弱时明确写“仅基于元数据推断”。
- 不要把路径存在或时间戳活跃直接等同于用户意图。
""",
    "10-output-contract.md": """# V4 输出契约

一次有效的观察 brief 至少回答：

- 最近发生了什么变化？
- 用户最近可能在做哪些工作线？
- 哪些 agent / 工具是活跃、新增、卸载、停用、残留或未知？
- 每个重要结论有哪些证据？
- 哪些信息值得成为 review-first memory candidate？
- 哪些内容因为隐私、安全或证据不足需要跳过？

推荐输出结构：

1. 当前图景：一句话结论。
2. 工作线：按项目或任务线列出事实、推断、证据。
3. Agent / 工具状态：活跃、新增、卸载、残留、未知分开。
4. 构建与发布：APK、加固、market 包、下载产物、签名/ADB/Gradle 命令。
5. 候选记忆：只列待 review 的候选，不自动接受。
6. 未知与下一步：明确还缺什么证据。

默认中文输出，先结论后证据。
""",
    "20-signal-quality.md": """# V4 信号质量规则

不要高估弱信号。

强信号：

- 明确的 summary、计划、提交、测试、命令输出、run/evidence/finding 记录。
- 多个来源共同支持同一条结论。
- 安装、卸载、配置迁移、构建产物或发布动作有时间和上下文。
- 用户显式纠正、决策、偏好、失败教训。

弱信号：

- 单个时间戳，没有上下文。
- 目录存在但没有近期活动。
- Recent 里有快捷方式但无法确认是否实际工作。
- 进程存在但窗口标题或上下文不足。
- 模型自己猜测但没有证据。

冲突处理：

- 新旧记忆矛盾时，记录冲突，不静默覆盖。
- 证据不足时标记“未知”。
- 对可能过期的信息提出 review，而不是自动删除。
""",
    "agents.md": """# Agent 与工具观察提示

观察 AI agent / 开发工具时，优先使用非敏感元数据判断活跃度和变化。

重点关注：

- Hermes：skills、cron jobs、session store、gateway 状态、最近非敏感日志和配置变化。
- Codex：session_index.jsonl、history.jsonl、rollout_summaries、最近 session 元数据。
- Claude：区分 Claude Desktop、Claude Code、配置残留、会话摘要和项目记忆；不要读取凭证。
- Kimi / GLM / 其他新装 agent：如果发现新增安装、卸载、配置迁移、命令历史或进程痕迹，要作为“工具状态变化”单独记录。
- Gemini / Antigravity：项目配置、conversation 元数据、非敏感状态文件；跳过私密正文和 token。
- OpenClaw：workspace、MEMORY.md、AGENT_LINKS.md、runs.sqlite 这类协作元数据。

工具状态变化是一等信号：

- 新增：最近出现的命令、配置目录、进程、快捷方式、包管理记录、下载/安装产物。
- 卸载或停用：旧配置仍在但进程/命令/Recent 不再活跃，或用户历史命令显示卸载/迁移。
- 迁移：同类 agent 从一个工具切到另一个工具，或默认模型/提供商变化。
- 不确定：只看到残留目录或单一时间戳时，只能写“未知/残留”，不要下结论。

## Session 内容摘要要求

对于 agent 相关 session，除了活跃度和元数据，也希望尽量形成中文 session 内容摘要。

优先摘要来源：

- 各 agent 的 session index、history、rollout summary、conversation metadata、项目级 summary、系统生成摘要。
- Hermes 的 session store / session_search 结果、非敏感会话标题、任务目标、最终结论。
- Claude / OpenClaw 的 MEMORY.md、AGENT_LINKS.md、任务 run summary、非敏感项目记忆。

摘要粒度：

- 每个 agent 最近在做什么。
- 关联的项目路径 / workspace。
- session 的任务目标、关键操作、结论、失败点和后续建议。
- 是否产生了可复用 workflow、项目决策、用户偏好或 memory candidate。
- 如果只能看到元数据，要明确写“仅基于元数据推断”，不要伪装成读过正文。

隐私边界：

- 优先读取已有 summary，不直接读取私聊正文、凭证、token、cookie、private key 或敏感会话内容。
- 对长 session 只取摘要或 bounded excerpt，并记录证据路径。
- 如果 session 内容看起来敏感，只记录标题/时间/来源和“跳过敏感内容”。

输出时使用中文，并标注每个 agent 的状态：活跃、有残留、未活跃、未知、跳过敏感；同时尽量附上该 agent 最近 session 的中文摘要。
""",
    "privacy.md": """# 隐私与风险策略提示

默认策略：中文、可审计、最小读取、review-first。

禁止或跳过：

- API key、token、cookie、SSH/private key、浏览器会话、账号 secret。
- 私聊正文、私密归档、未授权截图、键盘输入、网络抓包。
- 未经确认的跨 agent 敏感信息共享。
- 未经确认的文件修改、删除、迁移、上传、发送消息。

允许自动执行：

- 只读状态检查。
- 读取非敏感 summary / README / plan / metadata。
- 记录 observation run、evidence ref、finding。
- 提出 pending memory candidate，但不自动接受。

输出要求：

- 所有主动建议用中文说明风险等级。
- 遇到敏感路径，只记录“跳过”和原因，不读取内容。
- 对不确定事项标记为“未知”或“推断”，不要伪装成事实。
""",
    "projects.md": """# 项目观察提示

优先关注这些项目线：

1. memSu
   - 当前方向：V4 inspire-driven agent-led observe。
   - 重点：schema_version、inspire / inspire.d、observation_runs、evidence_refs、observation_findings、observe snapshot、review-first candidate。
   - 通过 Git、近期文件、测试结果和 memSu 自身 run/evidence/finding 判断活跃度。

2. Hermes Agent
   - 重点：skills、cron、gateway、memory 配置、工具和 profile。
   - 通过 Hermes home 元数据、skills、cron、session store、日志摘要和进程状态判断，不写死目录。

3. Android / 移动端项目
   - 重点：隐私合规、管控链路、厂商权限、锁屏、预检、构建签名、渠道包和发布产物。
   - 通过 Android 项目根、Gradle/ADB/签名/构建历史、APK 产物和 Git 记录判断近期工作。

4. 本机环境维护
   - 关注磁盘空间、worktree 清理、Android SDK、Gradle、Anaconda、agent 工具安装/卸载变化。

5. 其他最近活跃项目
   - 不依赖固定项目清单；通过文件修改时间、Git 近期提交/状态、Recent、PowerShell 历史和进程窗口主动发现。

结论需要中文摘要，并尽量说明“这条项目线最近是否活跃”。
""",
    "workflows.md": """# 工作流观察提示

V4 观察循环：

1. 先发现变化：文件时间、Git、Recent、历史命令、进程、agent session metadata、构建产物。
2. 再合并证据：把同一项目线或同一工作流的多个信号归到一起。
3. 再给结论：事实、推断、未知、建议分开写。
4. 最后提出 review-first memory candidate，不自动接受。

重点识别重复出现、适合沉淀的工作流：

- memSu 初始化、status、doctor、observe run、observe agent dry-run、audit/recall/candidate review。
- Hermes skill 创建/维护、cron 任务、gateway 状态检查、多 agent 协调。
- Agent session summary 到 memSu evidence / memory candidate 的摄取链路。
- Android 项目排查：先只读调查、定位证据、再按用户确认做 targeted fix。
- Windows 本机维护：先列清单和风险分级，再执行清理；不默认删除脏 worktree 或迁移系统目录。

当某个流程重复 3 次以上，建议用户是否封装成 skill、adapter 或 cron job。
""",
}


def ensure_inspire_files(*, overwrite: bool = False) -> dict[str, Any]:
    path = default_inspire_path()
    inspire_dir = default_inspire_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    inspire_dir.mkdir(parents=True, exist_ok=True)

    created = False
    if overwrite or not path.exists():
        path.write_text(DEFAULT_INSPIRE, encoding="utf-8")
        created = True

    created_files: list[str] = []
    for name, content in DEFAULT_INSPIRE_FILES.items():
        child = inspire_dir / name
        if overwrite or not child.exists():
            child.write_text(content, encoding="utf-8")
            created_files.append(str(child))

    return {
        "inspire_path": str(path),
        "inspire_dir": str(inspire_dir),
        "created": created,
        "created_files": created_files,
        "user_editable": True,
    }


def inspire_status() -> dict[str, Any]:
    path = default_inspire_path()
    inspire_dir = default_inspire_dir()
    return {
        "inspire_path": str(path),
        "inspire_dir": str(inspire_dir),
        "exists": path.exists(),
        "dir_exists": inspire_dir.exists(),
        "user_editable": True,
    }


def read_inspire() -> dict[str, Any]:
    status = inspire_status()
    path = Path(status["inspire_path"])
    inspire_dir = Path(status["inspire_dir"])
    content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    extra_files: list[str] = []
    sections = [content.rstrip()] if content.strip() else []
    if inspire_dir.exists():
        for child in sorted(inspire_dir.glob("*.md")):
            if not child.is_file():
                continue
            extra_files.append(str(child))
            child_content = child.read_text(encoding="utf-8", errors="replace").strip()
            if child_content:
                sections.append(f"# inspire.d/{child.name}\n\n{child_content}")
    combined = "\n\n".join(sections)
    return {**status, "content": combined, "inspire_files": extra_files}
