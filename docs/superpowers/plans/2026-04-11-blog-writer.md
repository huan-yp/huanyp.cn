# Blog Writer 实现计划

> **For agentic workers:** REQUIRED: Use the `subagent-driven-development` agent (recommended) or `executing-plans` agent to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个 QQ 消息驱动的博文交互式写作系统，通过 NcatBot 插件接收用户指令，LangChain Agent 完成写作，支持分段预览、修改、发布。

**Architecture:** NcatBot 插件（`plugins/blog-writer/`）接收 QQ 消息 → 消息协议解析器将用户消息映射为 Agent 指令 → LangChain Agent 管理写作会话、调用 LLM 写内容并编辑 `.md` 文件 → 三个确定性工具（preview/upload_image/publish）完成截图预览、图床上传、git push 发布。

**Tech Stack:** Python 3.11+, NcatBot (QQ Bot), LangChain + langchain-openai (Agent), Puppeteer/Node.js (截图), requests (GitHub API), subprocess (git)

**Design Spec:** `docs/superpowers/specs/2026-04-11-blog-writer-design.md`

---

## 文件结构总览

本计划涉及以下文件的创建：

```
plugins/blog-writer/
├── manifest.toml              # NcatBot 插件清单
├── main.py                    # 插件入口：QQ 消息处理 + 协议解析
├── protocol.py                # 消息协议解析器（agent 输出 → 消息列表）
├── agent/
│   ├── __init__.py            # 空，包标识
│   ├── core.py                # LangChain Agent 初始化 + 会话管理
│   ├── tools.py               # 3 个确定性工具的 LangChain Tool 定义
│   └── state.py               # ArticleState 数据类
├── agent/skills/
│   └── writing-guide.md       # 写作策略 Skill 文档（agent system prompt）
├── preview/
│   ├── preview.js             # Puppeteer 截图脚本（Node.js）
│   └── preview.py             # Python 封装：调 subprocess 跑 preview.js
├── uploader/
│   └── github_upload.py       # GitHub Contents API 上传图片
├── publisher/
│   └── git_push.py            # git add + commit + push
└── config_template.toml       # 配置模板（用户复制后填写）
```

测试文件：

```
plugins/blog-writer/tests/
├── test_protocol.py           # 协议解析器单元测试
├── test_state.py              # ArticleState 序列化测试
├── test_tools.py              # 工具函数单元测试（mock subprocess/requests）
├── test_agent.py              # Agent 集成测试（mock LLM）
└── conftest.py                # pytest fixtures
```

---

## Task 1: 项目骨架 + 依赖

**Files:**
- Create: `plugins/blog-writer/manifest.toml`
- Create: `plugins/blog-writer/config_template.toml`
- Create: `plugins/blog-writer/agent/__init__.py`
- Create: `plugins/blog-writer/tests/__init__.py`
- Create: `plugins/blog-writer/tests/conftest.py`

- [ ] **Step 1: 创建 manifest.toml**

```toml
name = "blog_writer"
version = "0.1.0"
main = "main.py"
entry_class = "BlogWriterPlugin"
author = "huan-yp"
description = "QQ 消息驱动的博文交互式写作系统"

[pip_dependencies]
langchain = ">=0.3.0"
langchain-openai = ">=0.3.0"
requests = ">=2.31.0"
```

- [ ] **Step 2: 创建 config_template.toml**

```toml
[blog_writer]
# 博客仓库绝对路径
blog_repo_path = "/path/to/huanyp.cn"

# 允许使用 /blog 命令的 QQ 用户 ID 列表（安全白名单）
allowed_users = []

[blog_writer.llm]
base_url = "https://api.openai.com/v1"
api_key = ""
model = "gpt-4o"

[blog_writer.image_host]
github_token = ""
github_user = "huan-yp"
github_repo = "image_space"
github_branch = "master"
upload_dir = "img"

[blog_writer.preview]
hexo_port = 4000
preview_dir = ".preview"
node_path = "node"
```

- [ ] **Step 3: 创建空包文件**

`plugins/blog-writer/agent/__init__.py`：空文件

`plugins/blog-writer/tests/__init__.py`：空文件

`plugins/blog-writer/tests/conftest.py`：

```python
import sys
from pathlib import Path

# 把插件根目录加到 sys.path，使 import protocol / agent 等可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 4: 确认目录结构完整**

Run: `find plugins/blog-writer -type f | sort`

Expected:
```
plugins/blog-writer/agent/__init__.py
plugins/blog-writer/config_template.toml
plugins/blog-writer/manifest.toml
plugins/blog-writer/tests/__init__.py
plugins/blog-writer/tests/conftest.py
```

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/
git commit -m "feat(blog-writer): project skeleton + manifest + config template"
```

---

## Task 2: 消息协议解析器

**Files:**
- Create: `plugins/blog-writer/protocol.py`
- Create: `plugins/blog-writer/tests/test_protocol.py`

- [ ] **Step 1: 写 protocol 解析器的测试**

`plugins/blog-writer/tests/test_protocol.py`：

```python
from protocol import parse_protocol


def test_parse_single_text():
    raw = "---MSG---\ntype: text\ncontent: hello world"
    result = parse_protocol(raw)
    assert result == [{"type": "text", "content": "hello world"}]


def test_parse_multiple_messages():
    raw = (
        "---MSG---\n"
        "type: text\n"
        "content: 大纲如下：\n"
        "1. 第一节\n"
        "2. 第二节\n"
        "---MSG---\n"
        "type: image\n"
        "path: .preview/section_1.png\n"
        "---MSG---\n"
        "type: text\n"
        "content: 回复 ok 继续"
    )
    result = parse_protocol(raw)
    assert len(result) == 3
    assert result[0]["type"] == "text"
    assert "大纲如下" in result[0]["content"]
    assert "1. 第一节" in result[0]["content"]
    assert result[1] == {"type": "image", "path": ".preview/section_1.png"}
    assert result[2]["type"] == "text"


def test_parse_confirm():
    raw = "---MSG---\ntype: confirm\ncontent: 确认发布？"
    result = parse_protocol(raw)
    assert result == [{"type": "confirm", "content": "确认发布？"}]


def test_fallback_no_separator():
    raw = "这是一段没有协议格式的纯文本"
    result = parse_protocol(raw)
    assert result == []


def test_fallback_empty():
    result = parse_protocol("")
    assert result == []


def test_multiline_content():
    raw = (
        "---MSG---\n"
        "type: text\n"
        "content: 第一行\n"
        "第二行\n"
        "第三行"
    )
    result = parse_protocol(raw)
    assert result[0]["content"] == "第一行\n第二行\n第三行"


def test_content_with_colon():
    raw = "---MSG---\ntype: text\ncontent: 时间：2026-04-11"
    result = parse_protocol(raw)
    assert result[0]["content"] == "时间：2026-04-11"
```

- [ ] **Step 2: 运行测试确认全部失败**

Run: `cd plugins/blog-writer && python -m pytest tests/test_protocol.py -v`

Expected: 7 FAILED（`ModuleNotFoundError: No module named 'protocol'` 或类似）

- [ ] **Step 3: 实现 protocol.py**

`plugins/blog-writer/protocol.py`：

```python
"""消息协议解析器。

将 Agent 输出的 ---MSG--- 分隔的文本解析为消息列表。
每个消息是一个 dict，包含 type 和对应字段（content/path/options）。
解析失败时返回空列表，由调用方执行兜底策略。
"""

_SEPARATOR = "---MSG---"


def parse_protocol(raw: str) -> list[dict]:
    """解析 agent 输出协议。

    Args:
        raw: agent 的原始输出文本

    Returns:
        消息列表。解析失败返回空列表。
    """
    if _SEPARATOR not in raw:
        return []

    blocks = raw.split(_SEPARATOR)
    messages = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        msg = _parse_block(block)
        if msg is not None:
            messages.append(msg)

    return messages


def _parse_block(block: str) -> dict | None:
    """解析单个消息块。

    块的第一行必须是 type: <类型>。
    后续每行如果是 key: value 格式，则作为字段解析。
    content 字段特殊处理：从 content: 开始到块结尾都算 content。
    """
    lines = block.split("\n")
    if not lines:
        return None

    # 第一行必须是 type
    first_line = lines[0].strip()
    if not first_line.startswith("type:"):
        return None

    msg_type = first_line.split(":", 1)[1].strip()
    if not msg_type:
        return None

    msg = {"type": msg_type}

    i = 1
    while i < len(lines):
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if key == "content":
                # content 从这一行的值开始，到块结尾
                remaining = [value] + [l for l in lines[i + 1 :]]
                msg["content"] = "\n".join(remaining).rstrip()
                break
            else:
                msg[key] = value
        i += 1

    return msg
```

- [ ] **Step 4: 运行测试确认全部通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_protocol.py -v`

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/protocol.py plugins/blog-writer/tests/test_protocol.py
git commit -m "feat(blog-writer): message protocol parser with tests"
```

---

## Task 3: 会话状态

**Files:**
- Create: `plugins/blog-writer/agent/state.py`
- Create: `plugins/blog-writer/tests/test_state.py`

- [ ] **Step 1: 写 ArticleState 测试**

`plugins/blog-writer/tests/test_state.py`：

```python
from agent.state import ArticleState


def test_create_default():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    assert s.title == ""
    assert s.status == "init"
    assert s.sections == []
    assert s.messages == []


def test_file_path_generation():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    s.title = "Docker 实践"
    s.category = "技术"
    path = s.generate_file_path()
    assert path == "source/_posts/技术/Docker 实践.md"


def test_build_markdown():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    s.title = "测试文章"
    s.category = "技术"
    s.tags = ["Python", "测试"]
    s.sections = ["## 第一节\n\n内容一", "## 第二节\n\n内容二"]

    md = s.build_markdown()
    assert "title: 测试文章" in md
    assert "categories:" in md
    assert "- 技术" in md
    assert "- Python" in md
    assert "## 第一节" in md
    assert "## 第二节" in md


def test_build_markdown_with_mathjax():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    s.title = "公式文章"
    s.category = "学术"
    s.tags = ["数学"]
    s.sections = ["## 定义\n\n$E=mc^2$"]

    md = s.build_markdown()
    assert "mathjax: true" in md
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd plugins/blog-writer && python -m pytest tests/test_state.py -v`

Expected: FAILED

- [ ] **Step 3: 实现 state.py**

`plugins/blog-writer/agent/state.py`：

```python
"""写作会话状态。"""

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ArticleState:
    """一次写作会话的状态。"""

    session_id: str
    user_id: str
    group_id: str

    # 文章内容
    title: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    outline: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)

    # 进度
    current_index: int = 0
    status: str = "init"  # init | outlining | writing | reviewing | published

    # 文件
    file_path: str = ""

    # 对话历史（传给 LLM）
    messages: list[dict] = field(default_factory=list)

    def generate_file_path(self) -> str:
        """根据分类和标题生成 source/_posts/ 下的路径。"""
        category = self.category or "uncategorized"
        title = self.title or "untitled"
        self.file_path = f"source/_posts/{category}/{title}.md"
        return self.file_path

    def build_markdown(self) -> str:
        """将当前状态组装为完整的 Markdown 文件内容。"""
        today = date.today().isoformat()
        content = "\n\n".join(self.sections)
        has_math = bool(re.search(r"\$.*?\$", content))

        front = [
            "---",
            f"title: {self.title}",
            f"date: {today}",
        ]
        if has_math:
            front.append("mathjax: true")
        if self.category:
            front.append("categories:")
            front.append(f"- {self.category}")
        if self.tags:
            front.append("tags:")
            for tag in self.tags:
                front.append(f"- {tag}")
        front.append("---")

        return "\n".join(front) + "\n\n" + content + "\n"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_state.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/agent/state.py plugins/blog-writer/tests/test_state.py
git commit -m "feat(blog-writer): ArticleState data class with markdown builder"
```

---

## Task 4: 写作策略 Skill 文档

**Files:**
- Create: `plugins/blog-writer/agent/skills/writing-guide.md`

- [ ] **Step 1: 创建 writing-guide.md**

这是 Agent 的 system prompt 参考文档。内容直接从设计文档的「写作风格指南」章节复制并改写为 system prompt 格式。

`plugins/blog-writer/agent/skills/writing-guide.md`：

```markdown
# 博文写作策略指南

你是一个博文写作助手，负责帮助用户「幻影彭」撰写博客文章。你的输出必须与他已有的 60+ 篇博文风格保持一致。

## 你的身份

你不是独立的作者，你是「幻影彭」的代笔。你写出来的内容，读者看到后应该认为是他本人写的。

## 工作流程

1. 收到主题后，先生成大纲（3-7 个 `##` 级标题）
2. 用户确认大纲后，逐段展开内容
3. 每段写完后，调用 preview 工具生成预览，发给用户确认
4. 用户回复 ok 继续下一段，回复 "改 xxx" 则按反馈修改
5. 全部段落完成后，进入 reviewing 状态
6. 用户确认后，调用 publish 工具发布

## 输出协议

你的输出必须使用 ---MSG--- 协议格式：

---MSG---
type: text
content: 你要发的文字

---MSG---
type: image
path: 截图路径

每次输出可包含多个 ---MSG--- 块。

## 写作风格规则（必须严格遵循）

### 语言基调

- 全程第一人称「我」的视角
- 口语化但不散漫，像在和一个水平差不多的人面对面聊
- 专业术语和网络用语混搭：可以在技术讨论中穿插「TM」「咕咕咕」「woc」，但只用于强调或吐槽，不是每句都带
- 大量使用转折：「但是」「然而」「虽然…但」「不过」
- 省略号表示思考或戏谑

### 叙事特征

- 自我吐槽但不自苦——坦诚承认不足，语气洒脱不抱怨
- 对他人评价坦诚且尊重——直接说好坏，但不恶意
- 理性与感性自由切换——可以从公式跳到人生感悟，用技术类比讲生活
- 写具体的细节（时间、数字、命令、路径），不写抽象空话

### 按文章分类调整风格

- **技术文**：问题→方案→代码→注意事项。代码块前解释后总结。代码占 40-60%
- **生活文**：散文式，短段落，大量心理描写和细节观察，情感克制但真实
- **科普文**：从简到繁层层递进，大量类比，面向非专业读者
- **学术文**：定义→定理→证明→应用，公式密集，夹带个人评价
- **OI/算法文**：假设读者有基础，跳过基本定义，竞赛圈共同语言

### 开头模式

1. 直接开场（最常用）：一两句话说清楚文章是什么
2. "写在前面"（技术/学术文）：`### 写在前面` 或 `>` 引用块交代背景
3. 背景故事（生活文）：直接把自己拉进场景
4. 问题引入（科普/OI）：直接抛出问题定义

### 结尾模式

- 说完即止，不做总结。大多数文章没有「总结」「结语」标题
- 技术文：最后一个要点说完就结束
- 科普文可以有简短展望

### Markdown 格式

- 标题从 `##` 开始写（`#` 由 Hexo 生成）
- 代码块始终标注语言
- 粗体用于关键概念强调
- 无序列表用 `-`
- 公式行内 `$...$`，块级 `$$...$$`，融入文本段落
- 图片 `![alt](URL)` 格式

### 特色用语（适当使用，别每句都加）

- 「咕咕咕」= 鸽了/没写完
- 「TM」「woc」= 技术问题吐槽，绝不针对人
- 「不得不说…」「不妨…」= 引入观点
- 「理论上…」「实际上…」= 理想 vs 现实转折
- 「我打算…」= 表达未来行动

### 绝对禁止

- emoji 装饰
- 「总结」「结语」「最后」套路性收尾
- 「让我们一起…」「相信大家…」公众号体
- 过度感叹号
- 「感谢阅读」「希望对大家有帮助」无意义客气
- 「值得注意的是」「需要指出的是」「综上所述」AI 腔
- 人身攻击
- 未标注语言的代码块

## front-matter 模板

---
title: <标题>
date: <YYYY-MM-DD>
categories:
- <分类>
tags:
- <标签1>
- <标签2>
mathjax: true  # 仅在有公式时添加
---
```

- [ ] **Step 2: Commit**

```bash
git add plugins/blog-writer/agent/skills/writing-guide.md
git commit -m "feat(blog-writer): writing strategy skill document"
```

---

## Task 5: Agent 核心（LangChain 初始化 + 会话管理）

**Files:**
- Create: `plugins/blog-writer/agent/core.py`
- Create: `plugins/blog-writer/tests/test_agent.py`

- [ ] **Step 1: 写 Agent 核心测试**

`plugins/blog-writer/tests/test_agent.py`：

```python
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from agent.core import create_agent, BlogWriterAgent
from agent.state import ArticleState


@pytest.fixture
def mock_config():
    return {
        "llm": {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "model": "gpt-4o",
        },
        "blog_repo_path": "/tmp/test-blog",
        "preview": {
            "hexo_port": 4000,
            "preview_dir": ".preview",
            "node_path": "node",
        },
        "image_host": {
            "github_token": "test-token",
            "github_user": "test-user",
            "github_repo": "test-repo",
            "github_branch": "main",
            "upload_dir": "img",
        },
    }


def test_create_agent(mock_config):
    agent = create_agent(mock_config)
    assert isinstance(agent, BlogWriterAgent)


def test_agent_has_tools(mock_config):
    agent = create_agent(mock_config)
    tool_names = [t.name for t in agent.tools]
    assert "preview" in tool_names
    assert "upload_image" in tool_names
    assert "publish" in tool_names


@pytest.mark.asyncio
async def test_agent_run_returns_string(mock_config):
    agent = create_agent(mock_config)
    state = ArticleState(session_id="test", user_id="u1", group_id="g1")

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "---MSG---\ntype: text\ncontent: 已收到主题"
        result = await agent.run("Docker 网络", state)
        assert "---MSG---" in result
        assert state.status == "outlining"


@pytest.mark.asyncio
async def test_agent_continue_session(mock_config):
    agent = create_agent(mock_config)
    state = ArticleState(session_id="test", user_id="u1", group_id="g1")
    state.status = "writing"

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "---MSG---\ntype: text\ncontent: ok 继续"
        result = await agent.continue_session("ok", state)
        assert isinstance(result, str)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd plugins/blog-writer && python -m pytest tests/test_agent.py -v`

Expected: FAILED

- [ ] **Step 3: 实现 agent/core.py**

`plugins/blog-writer/agent/core.py`：

```python
"""LangChain Agent 核心：初始化、会话管理、LLM 调用。"""

from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from agent.state import ArticleState
from agent.tools import build_tools

_SKILL_PATH = Path(__file__).parent / "skills" / "writing-guide.md"


def create_agent(config: dict) -> "BlogWriterAgent":
    """创建 BlogWriterAgent 实例。"""
    llm_cfg = config["llm"]
    llm = ChatOpenAI(
        base_url=llm_cfg["base_url"],
        api_key=llm_cfg["api_key"],
        model=llm_cfg["model"],
        temperature=0.7,
    )
    tools = build_tools(config)
    return BlogWriterAgent(llm=llm, tools=tools, config=config)


class BlogWriterAgent:
    """管理写作会话、调用 LLM、调用工具。"""

    def __init__(self, llm: ChatOpenAI, tools: list[BaseTool], config: dict):
        self.llm = llm
        self.tools = tools
        self.config = config
        self._system_prompt = self._load_skill()
        self.llm_with_tools = llm.bind_tools(tools)

    def _load_skill(self) -> str:
        """加载写作策略 Skill 文档。"""
        if _SKILL_PATH.exists():
            return _SKILL_PATH.read_text(encoding="utf-8")
        return "你是一个博文写作助手。"

    async def run(self, topic: str, state: ArticleState) -> str:
        """启动新写作会话。"""
        state.status = "outlining"
        state.messages = []

        user_msg = f"请为以下主题撰写博文，先生成大纲：\n\n{topic}"
        return await self._invoke(user_msg, state)

    async def continue_session(self, user_input: str, state: ArticleState) -> str:
        """继续已有的写作会话。"""
        return await self._invoke(user_input, state)

    async def _invoke(self, user_input: str, state: ArticleState) -> str:
        """调用 LLM 并处理工具调用。"""
        state.messages.append({"role": "user", "content": user_input})

        lc_messages = [SystemMessage(content=self._system_prompt)]
        for msg in state.messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        response = await self.llm_with_tools.ainvoke(lc_messages)

        # 处理工具调用
        if response.tool_calls:
            tool_results = await self._execute_tools(response.tool_calls, state)
            # 把工具结果追加到上下文，再调一次 LLM 生成最终回复
            state.messages.append({"role": "assistant", "content": response.content})
            tool_summary = "\n".join(
                f"工具 {r['name']} 返回: {r['result']}" for r in tool_results
            )
            state.messages.append({"role": "user", "content": tool_summary})
            lc_messages.append(AIMessage(content=response.content))
            lc_messages.append(HumanMessage(content=tool_summary))
            response = await self.llm_with_tools.ainvoke(lc_messages)

        result = response.content
        state.messages.append({"role": "assistant", "content": result})
        return result

    async def _execute_tools(
        self, tool_calls: list, state: ArticleState
    ) -> list[dict]:
        """执行 LLM 请求的工具调用。"""
        tool_map = {t.name: t for t in self.tools}
        results = []
        for call in tool_calls:
            tool = tool_map.get(call["name"])
            if tool is None:
                results.append({"name": call["name"], "result": "工具不存在"})
                continue
            # 注入 state 中的上下文到工具参数
            args = call.get("args", {})
            args["_blog_repo_path"] = self.config.get("blog_repo_path", "")
            args["_state"] = state
            try:
                result = await tool.ainvoke(args)
                results.append({"name": call["name"], "result": str(result)})
            except Exception as e:
                results.append({"name": call["name"], "result": f"错误: {e}"})
        return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_agent.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/agent/core.py plugins/blog-writer/tests/test_agent.py
git commit -m "feat(blog-writer): LangChain agent core with session management"
```

---

## Task 6: 三个确定性工具

**Files:**
- Create: `plugins/blog-writer/agent/tools.py`
- Create: `plugins/blog-writer/preview/preview.py`
- Create: `plugins/blog-writer/preview/preview.js`
- Create: `plugins/blog-writer/uploader/github_upload.py`
- Create: `plugins/blog-writer/publisher/git_push.py`
- Create: `plugins/blog-writer/tests/test_tools.py`

本 Task 拆分为 6a-6e 五个子任务。

---

### Task 6a: publish 工具（git push）

**Files:**
- Create: `plugins/blog-writer/publisher/__init__.py`
- Create: `plugins/blog-writer/publisher/git_push.py`

- [ ] **Step 1: 写 publish 测试**

在 `plugins/blog-writer/tests/test_tools.py` 中：

```python
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from publisher.git_push import git_publish


def test_git_publish_success():
    with patch("publisher.git_push.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = git_publish(
            repo_path="/tmp/blog",
            file_path="source/_posts/技术/Docker.md",
            commit_message='post: Docker 实践',
        )
        assert "huanyp.cn" in result
        assert mock_run.call_count == 3  # add, commit, push


def test_git_publish_default_message():
    with patch("publisher.git_push.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = git_publish(
            repo_path="/tmp/blog",
            file_path="source/_posts/技术/Docker.md",
        )
        calls = mock_run.call_args_list
        commit_cmd = calls[1][0][0]
        assert "post:" in " ".join(commit_cmd)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py::test_git_publish_success -v`

Expected: FAILED

- [ ] **Step 3: 实现 git_push.py**

`plugins/blog-writer/publisher/__init__.py`：空文件

`plugins/blog-writer/publisher/git_push.py`：

```python
"""Git 提交并推送博文。"""

import subprocess
from pathlib import Path


def git_publish(
    repo_path: str,
    file_path: str,
    commit_message: str = "",
) -> str:
    """执行 git add + commit + push 发布文章。

    Args:
        repo_path: 博客仓库绝对路径
        file_path: 文章相对于仓库根目录的路径
        commit_message: 提交信息，空则自动生成

    Returns:
        文章预期 URL
    """
    if not commit_message:
        title = Path(file_path).stem
        commit_message = f"post: {title}"

    cwd = repo_path
    _run_git(["git", "add", file_path], cwd)
    _run_git(["git", "commit", "-m", commit_message], cwd)
    _run_git(["git", "push", "origin", "main"], cwd)

    return f"https://huanyp.cn/ (部署中，推送完成)"


def _run_git(cmd: list[str], cwd: str) -> str:
    """执行 git 命令并返回 stdout。"""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git 命令失败: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py -v -k "git_publish"`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/publisher/
git commit -m "feat(blog-writer): publish tool (git add/commit/push)"
```

---

### Task 6b: upload_image 工具（GitHub 图床）

**Files:**
- Create: `plugins/blog-writer/uploader/__init__.py`
- Create: `plugins/blog-writer/uploader/github_upload.py`

- [ ] **Step 1: 写 upload 测试**

追加到 `plugins/blog-writer/tests/test_tools.py`：

```python
from unittest.mock import patch, MagicMock
from uploader.github_upload import upload_to_github


def test_upload_to_github():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "content": {
            "download_url": "https://raw.githubusercontent.com/user/repo/main/img/test.png"
        }
    }

    with patch("uploader.github_upload.requests.put", return_value=mock_response):
        with patch("builtins.open", MagicMock()):
            with patch("uploader.github_upload.Path") as mock_path:
                mock_path.return_value.read_bytes.return_value = b"fake-png"
                mock_path.return_value.name = "test.png"
                url = upload_to_github(
                    file_path="/tmp/test.png",
                    token="ghp_test",
                    user="user",
                    repo="repo",
                    branch="main",
                    upload_dir="img",
                )
                assert "raw.githubusercontent.com" in url


def test_upload_to_github_conflict():
    """文件已存在时应该生成新文件名重试。"""
    mock_409 = MagicMock()
    mock_409.status_code = 422  # "sha" is required = file exists
    mock_409.json.return_value = {"message": "\"sha\" wasn't supplied"}

    mock_201 = MagicMock()
    mock_201.status_code = 201
    mock_201.json.return_value = {
        "content": {
            "download_url": "https://raw.githubusercontent.com/u/r/main/img/test_1.png"
        }
    }

    with patch("uploader.github_upload.requests.put", side_effect=[mock_409, mock_201]):
        with patch("uploader.github_upload.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"fake"
            mock_path.return_value.name = "test.png"
            mock_path.return_value.stem = "test"
            mock_path.return_value.suffix = ".png"
            url = upload_to_github(
                file_path="/tmp/test.png",
                token="ghp_test",
                user="u",
                repo="r",
                branch="main",
                upload_dir="img",
            )
            assert url is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py -v -k "upload"`

Expected: FAILED

- [ ] **Step 3: 实现 github_upload.py**

`plugins/blog-writer/uploader/__init__.py`：空文件

`plugins/blog-writer/uploader/github_upload.py`：

```python
"""通过 GitHub Contents API 上传图片到图床仓库。"""

import base64
from pathlib import Path

import requests


def upload_to_github(
    file_path: str,
    token: str,
    user: str,
    repo: str,
    branch: str,
    upload_dir: str,
) -> str:
    """上传本地文件到 GitHub 仓库并返回 raw URL。

    Args:
        file_path: 本地文件路径
        token: GitHub Personal Access Token
        user: GitHub 用户名
        repo: 仓库名
        branch: 分支名
        upload_dir: 上传到仓库中的目录

    Returns:
        raw.githubusercontent.com 的文件 URL
    """
    p = Path(file_path)
    content = base64.b64encode(p.read_bytes()).decode("ascii")
    filename = p.name

    # 尝试上传，文件名冲突时追加后缀
    for attempt in range(3):
        if attempt > 0:
            filename = f"{p.stem}_{attempt}{p.suffix}"

        api_path = f"{upload_dir}/{filename}"
        url = f"https://api.github.com/repos/{user}/{repo}/contents/{api_path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "message": f"upload: {filename}",
            "content": content,
            "branch": branch,
        }

        resp = requests.put(url, json=payload, headers=headers, timeout=30)

        if resp.status_code == 201:
            return resp.json()["content"]["download_url"]

        # 422 = file exists, retry with different name
        if resp.status_code == 422:
            continue

        resp.raise_for_status()

    raise RuntimeError(f"上传失败，尝试 3 次仍然冲突: {filename}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py -v -k "upload"`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/uploader/
git commit -m "feat(blog-writer): upload_image tool (GitHub Contents API)"
```

---

### Task 6c: preview 工具（Puppeteer 截图）

**Files:**
- Create: `plugins/blog-writer/preview/__init__.py`
- Create: `plugins/blog-writer/preview/preview.js`
- Create: `plugins/blog-writer/preview/preview.py`

- [ ] **Step 1: 创建 preview.js（Puppeteer 脚本）**

`plugins/blog-writer/preview/__init__.py`：空文件

`plugins/blog-writer/preview/preview.js`：

```javascript
/**
 * Puppeteer 截图脚本。
 * 用法: node preview.js <url> <output_path> [section_selector]
 *
 * - 无 section_selector: full page screenshot
 * - 有 section_selector: 只截取该 CSS 选择器匹配的元素
 */

const puppeteer = require("puppeteer");

async function main() {
  const [url, outputPath, sectionSelector] = process.argv.slice(2);

  if (!url || !outputPath) {
    console.error("Usage: node preview.js <url> <output_path> [section_selector]");
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });

    // 等待内容渲染
    await page.waitForSelector(".post-body", { timeout: 10000 });

    if (sectionSelector) {
      const element = await page.$(sectionSelector);
      if (element) {
        await element.screenshot({ path: outputPath });
      } else {
        // selector 不存在时截全页
        await page.screenshot({ path: outputPath, fullPage: true });
      }
    } else {
      await page.screenshot({ path: outputPath, fullPage: true });
    }

    console.log(outputPath);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
```

- [ ] **Step 2: 实现 preview.py（Python 封装）**

`plugins/blog-writer/preview/preview.py`：

```python
"""Puppeteer 截图的 Python 封装。"""

import subprocess
from pathlib import Path


_SCRIPT_PATH = Path(__file__).parent / "preview.js"


def take_screenshot(
    article_url: str,
    output_path: str,
    section_selector: str = "",
    node_path: str = "node",
) -> str:
    """调用 Puppeteer 截图并返回截图路径。

    Args:
        article_url: 文章的完整 URL（如 http://localhost:4000/posts/abc123.html）
        output_path: 截图保存路径
        section_selector: CSS 选择器，空则全页截图
        node_path: node 可执行文件路径

    Returns:
        截图文件路径
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [node_path, str(_SCRIPT_PATH), article_url, output_path]
    if section_selector:
        cmd.append(section_selector)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"截图失败: {result.stderr}")

    return output_path
```

- [ ] **Step 3: 写 preview 测试**

追加到 `plugins/blog-writer/tests/test_tools.py`：

```python
from preview.preview import take_screenshot


def test_take_screenshot_calls_node():
    with patch("preview.preview.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=".preview/full.png", stderr=""
        )
        result = take_screenshot(
            article_url="http://localhost:4000/posts/abc.html",
            output_path=".preview/full.png",
        )
        assert result == ".preview/full.png"
        cmd = mock_run.call_args[0][0]
        assert "preview.js" in cmd[1]
        assert "http://localhost:4000/posts/abc.html" in cmd


def test_take_screenshot_with_selector():
    with patch("preview.preview.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="out.png", stderr="")
        take_screenshot(
            article_url="http://localhost:4000/posts/abc.html",
            output_path="out.png",
            section_selector="#section-2",
        )
        cmd = mock_run.call_args[0][0]
        assert "#section-2" in cmd
```

- [ ] **Step 4: 运行 preview 测试确认通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py -v -k "screenshot"`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add plugins/blog-writer/preview/
git commit -m "feat(blog-writer): preview tool (Puppeteer screenshot wrapper)"
```

---

### Task 6d: LangChain Tool 定义

**Files:**
- Create: `plugins/blog-writer/agent/tools.py`

- [ ] **Step 1: 实现 tools.py**

`plugins/blog-writer/agent/tools.py`：

```python
"""LangChain Tool 定义：preview, upload_image, publish。"""

from langchain_core.tools import tool

from preview.preview import take_screenshot
from uploader.github_upload import upload_to_github
from publisher.git_push import git_publish


def build_tools(config: dict) -> list:
    """根据配置构建工具列表。"""
    blog_repo = config.get("blog_repo_path", "")
    preview_cfg = config.get("preview", {})
    image_cfg = config.get("image_host", {})

    @tool
    def preview(article_path: str, mode: str = "full", section_index: int = 0) -> str:
        """生成文章预览截图。

        Args:
            article_path: 文章的 URL 路径（如 posts/abc123.html）
            mode: "full" 全页截图，"section" 截取指定段落
            section_index: mode=section 时，段落序号（从 1 开始）
        """
        port = preview_cfg.get("hexo_port", 4000)
        url = f"http://localhost:{port}/{article_path}"
        preview_dir = preview_cfg.get("preview_dir", ".preview")
        node_path = preview_cfg.get("node_path", "node")

        if mode == "section":
            selector = f"#section-{section_index}"
            output = f"{preview_dir}/section_{section_index}.png"
        else:
            selector = ""
            output = f"{preview_dir}/full.png"

        return take_screenshot(url, output, selector, node_path)

    @tool
    def upload_image(file_path: str) -> str:
        """上传图片到 GitHub 图床，返回 URL。

        Args:
            file_path: 本地图片文件路径
        """
        return upload_to_github(
            file_path=file_path,
            token=image_cfg.get("github_token", ""),
            user=image_cfg.get("github_user", ""),
            repo=image_cfg.get("github_repo", ""),
            branch=image_cfg.get("github_branch", "main"),
            upload_dir=image_cfg.get("upload_dir", "img"),
        )

    @tool
    def publish(commit_message: str = "") -> str:
        """提交并推送博文到 GitHub，触发自动部署。

        Args:
            commit_message: 提交信息，为空则自动生成
        """
        # file_path 由调用方从 state 中注入
        return "publish 需要在 agent._execute_tools 中注入 file_path"

    return [preview, upload_image, publish]
```

- [ ] **Step 2: 写 tools 集成测试**

追加到 `plugins/blog-writer/tests/test_tools.py`：

```python
from agent.tools import build_tools


def test_build_tools_returns_three():
    config = {
        "blog_repo_path": "/tmp/blog",
        "preview": {"hexo_port": 4000, "preview_dir": ".preview", "node_path": "node"},
        "image_host": {
            "github_token": "t",
            "github_user": "u",
            "github_repo": "r",
            "github_branch": "main",
            "upload_dir": "img",
        },
    }
    tools = build_tools(config)
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"preview", "upload_image", "publish"}
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py -v -k "build_tools"`

Expected: 1 passed

- [ ] **Step 4: Commit**

```bash
git add plugins/blog-writer/agent/tools.py
git commit -m "feat(blog-writer): LangChain tool definitions (preview/upload/publish)"
```

---

### Task 6e: 完整工具测试套件

- [ ] **Step 1: 运行全部工具测试**

Run: `cd plugins/blog-writer && python -m pytest tests/test_tools.py -v`

Expected: 7 passed

- [ ] **Step 2: 运行完整测试套件**

Run: `cd plugins/blog-writer && python -m pytest tests/ -v`

Expected: 18 passed（protocol 7 + state 4 + agent 4 + tools 7 = 22，部分可能需要 asyncio 标记）

若有失败，修复后重新运行。

- [ ] **Step 3: Commit（如有修复）**

```bash
git add plugins/blog-writer/tests/
git commit -m "test(blog-writer): complete tool test suite"
```

---

## Task 7: NcatBot 插件入口

**Files:**
- Create: `plugins/blog-writer/main.py`

- [ ] **Step 1: 实现 main.py**

`plugins/blog-writer/main.py`：

```python
"""Blog Writer NcatBot 插件入口。"""

from uuid import uuid4

from ncatbot.plugin import NcatBotPlugin
from ncatbot.core import registrar
from ncatbot.event.qq import GroupMessageEvent
from ncatbot.utils import get_log

from protocol import parse_protocol
from agent.core import create_agent
from agent.state import ArticleState

LOG = get_log("BlogWriter")


class BlogWriterPlugin(NcatBotPlugin):
    name = "blog_writer"
    version = "0.1.0"
    author = "huan-yp"
    description = "QQ 消息驱动的博文交互式写作系统"

    async def on_load(self):
        self.sessions: dict[str, ArticleState] = {}
        self.agent = create_agent(self.config.get("blog_writer", {}))
        self.allowed_users = set(
            str(u) for u in self.config.get("blog_writer", {}).get("allowed_users", [])
        )
        LOG.info("Blog Writer 插件已加载")

    async def on_close(self):
        LOG.info("Blog Writer 插件已卸载")

    @registrar.on_group_command("blog")
    async def on_blog_command(self, event: GroupMessageEvent, content: str = ""):
        """启动新写作会话。"""
        user_id = str(event.user_id)

        # 安全白名单检查
        if self.allowed_users and user_id not in self.allowed_users:
            return

        if not content.strip():
            await event.reply(text="用法: /blog <主题描述>")
            return

        session = ArticleState(
            session_id=str(uuid4()),
            user_id=user_id,
            group_id=str(event.group_id),
        )
        key = f"{event.group_id}_{user_id}"
        self.sessions[key] = session

        LOG.info(f"新写作会话: {key}, 主题: {content}")

        try:
            result = await self.agent.run(content.strip(), session)
            await self._send_protocol_messages(event.group_id, result)
        except Exception as e:
            LOG.error(f"Agent 调用失败: {e}")
            await event.reply(text=f"写作 Agent 出错了: {e}")

    @registrar.on_group_message()
    async def on_message(self, event: GroupMessageEvent):
        """处理写作会话中的后续消息。"""
        user_id = str(event.user_id)
        key = f"{event.group_id}_{user_id}"

        if key not in self.sessions:
            return

        text = event.text.strip() if event.text else ""
        if not text:
            return

        # /blog 命令由 on_blog_command 处理，这里跳过
        if text.startswith("/blog"):
            return

        session = self.sessions[key]

        # 特殊命令：结束会话
        if text in ("退出", "取消", "结束"):
            del self.sessions[key]
            await event.reply(text="写作会话已结束")
            return

        try:
            result = await self.agent.continue_session(text, session)
            await self._send_protocol_messages(event.group_id, result)
        except Exception as e:
            LOG.error(f"Agent 继续会话失败: {e}")
            await event.reply(text=f"继续会话出错: {e}")

        # 发布完成后清理会话
        if session.status == "published":
            del self.sessions[key]

    async def _send_protocol_messages(self, group_id, agent_output: str):
        """解析 agent 输出协议并发送 QQ 消息。"""
        messages = parse_protocol(agent_output)

        if not messages:
            # 兜底：解析失败时直接发文本
            await self.api.qq.post_group_msg(group_id, text=agent_output)
            return

        for msg in messages:
            if msg["type"] == "text":
                await self.api.qq.post_group_msg(group_id, text=msg["content"])
            elif msg["type"] == "image":
                await self.api.qq.send_group_image(group_id, msg["path"])
            elif msg["type"] == "confirm":
                await self.api.qq.post_group_msg(
                    group_id,
                    text=msg.get("content", "请回复确认"),
                )
```

- [ ] **Step 2: 语法检查**

Run: `cd plugins/blog-writer && python -c "import ast; ast.parse(open('main.py').read()); print('syntax ok')"`

Expected: `syntax ok`

- [ ] **Step 3: Commit**

```bash
git add plugins/blog-writer/main.py
git commit -m "feat(blog-writer): NcatBot plugin entry point with session management"
```

---

## Task 8: 安装 Node.js 依赖 + Puppeteer

**Files:**
- Create: `plugins/blog-writer/preview/package.json`

- [ ] **Step 1: 创建 package.json**

`plugins/blog-writer/preview/package.json`：

```json
{
  "name": "blog-writer-preview",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "puppeteer": "^24.0.0"
  }
}
```

- [ ] **Step 2: 安装依赖**

Run: `cd plugins/blog-writer/preview && npm install`

Expected: 安装完成，`node_modules/` 出现

- [ ] **Step 3: 添加 .gitignore**

`plugins/blog-writer/preview/.gitignore`：

```
node_modules/
```

- [ ] **Step 4: Commit**

```bash
git add plugins/blog-writer/preview/package.json plugins/blog-writer/preview/.gitignore
git commit -m "feat(blog-writer): puppeteer dependencies for preview tool"
```

---

## Task 9: 集成冒烟测试

这个 task 是端到端验证，不 mock LLM，而是用一个简单的回显 Agent 来测试整个消息流。

**Files:**
- Create: `plugins/blog-writer/tests/test_integration.py`

- [ ] **Step 1: 写集成测试**

`plugins/blog-writer/tests/test_integration.py`：

```python
"""集成冒烟测试：不连真实 LLM，验证消息流。"""

from unittest.mock import AsyncMock, patch
import pytest

from agent.state import ArticleState
from protocol import parse_protocol


@pytest.mark.asyncio
async def test_full_flow_protocol():
    """验证 state → markdown → protocol 解析 完整链路。"""
    state = ArticleState(session_id="s1", user_id="u1", group_id="g1")
    state.title = "测试文章"
    state.category = "技术"
    state.tags = ["Python"]
    state.sections = ["## 简介\n\n这是一篇测试文章。"]
    state.status = "writing"

    # 1. build markdown
    md = state.build_markdown()
    assert "title: 测试文章" in md
    assert "## 简介" in md

    # 2. 模拟 agent 输出
    agent_output = (
        "---MSG---\n"
        "type: text\n"
        "content: 第 1 段已写入，内容如下：\n"
        "## 简介\n"
        "这是一篇测试文章。\n"
        "---MSG---\n"
        "type: text\n"
        "content: 回复 ok 继续下一段"
    )

    # 3. 解析协议
    messages = parse_protocol(agent_output)
    assert len(messages) == 2
    assert messages[0]["type"] == "text"
    assert "第 1 段已写入" in messages[0]["content"]
    assert messages[1]["content"] == "回复 ok 继续下一段"


@pytest.mark.asyncio
async def test_state_generates_correct_file_path():
    """验证不同分类生成正确的文件路径。"""
    state = ArticleState(session_id="s1", user_id="u1", group_id="g1")
    state.title = "EM 算法笔记"
    state.category = "学术"
    path = state.generate_file_path()
    assert path == "source/_posts/学术/EM 算法笔记.md"


@pytest.mark.asyncio
async def test_markdown_no_mathjax_when_no_formula():
    """没有数学公式时不应添加 mathjax。"""
    state = ArticleState(session_id="s1", user_id="u1", group_id="g1")
    state.title = "纯文本"
    state.category = "生活"
    state.sections = ["## 随记\n\n今天天气不错。"]
    md = state.build_markdown()
    assert "mathjax" not in md
```

- [ ] **Step 2: 运行集成测试**

Run: `cd plugins/blog-writer && python -m pytest tests/test_integration.py -v`

Expected: 3 passed

- [ ] **Step 3: 运行全部测试**

Run: `cd plugins/blog-writer && python -m pytest tests/ -v`

Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add plugins/blog-writer/tests/test_integration.py
git commit -m "test(blog-writer): integration smoke tests"
```

---

## Task 10: 文档 + .gitignore + 最终检查

**Files:**
- Create: `plugins/blog-writer/README.md`
- Create: `plugins/blog-writer/.gitignore`

- [ ] **Step 1: 创建 .gitignore**

`plugins/blog-writer/.gitignore`：

```
__pycache__/
*.pyc
.preview/
.pytest_cache/
```

- [ ] **Step 2: 创建 README.md**

`plugins/blog-writer/README.md`：

```markdown
# Blog Writer

QQ 消息驱动的博文交互式写作系统（NcatBot 插件）。

## 安装

1. 将 `plugins/blog-writer/` 放入 NcatBot 的 `plugins/` 目录
2. 复制 `config_template.toml` 为你的配置文件，填写 LLM、图床、博客仓库路径
3. 安装 Python 依赖：`pip install langchain langchain-openai requests`
4. 安装 Puppeteer：`cd preview && npm install`

## 使用

QQ 群中发送：

- `/blog Docker 网络模式详解` — 开始写作
- `ok` — 确认当前段落
- `改 第二段太长了` — 修改反馈
- `预览` — 全文预览截图
- `发布` — git push 发布
- `退出` — 结束会话

## 开发

```bash
cd plugins/blog-writer
python -m pytest tests/ -v
```
```

- [ ] **Step 3: 最终测试 + 目录结构检查**

Run: `cd plugins/blog-writer && python -m pytest tests/ -v && echo "---" && find . -type f -not -path './preview/node_modules/*' -not -path './__pycache__/*' -not -name '*.pyc' | sort`

Expected: 全部测试通过，目录结构与设计文档一致

- [ ] **Step 4: Commit**

```bash
git add plugins/blog-writer/
git commit -m "feat(blog-writer): README + gitignore, v0.1.0 complete"
```

---

## 交付检查清单

完成所有 Task 后，用以下清单对照设计文档确认覆盖率：

| 设计文档章节 | 对应 Task | 状态 |
|-------------|----------|------|
| 架构（三层分工） | Task 5 (Agent) + Task 7 (Plugin) | |
| 项目结构 | Task 1 (骨架) | |
| 消息协议 | Task 2 (protocol.py) | |
| 工具定义 - preview | Task 6c + 6d | |
| 工具定义 - upload_image | Task 6b + 6d | |
| 工具定义 - publish | Task 6a + 6d | |
| 会话状态 | Task 3 (state.py) | |
| Skill 文档（写作策略+风格指南） | Task 4 | |
| NcatBot 插件入口 | Task 7 | |
| 配置项 | Task 1 (config_template.toml) | |
| 依赖 | Task 1 (manifest.toml) + Task 8 (puppeteer) | |
| 安全白名单 | Task 7 (allowed_users) | |
