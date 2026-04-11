# Blog Writer — 博文交互式写作系统设计

日期：2026-04-11

## 概述

一个通过 QQ 消息驱动的博文交互式写作系统。用户在 QQ 中提供关键词/大纲，后端 Agent 逐段展开内容，生成预览图片发送给用户确认，支持分段修改和全文预览，最终一键发布到 Hexo 博客。

## 架构

```
┌─────────────┐    消息     ┌──────────────┐    指令     ┌──────────────┐
│  QQ 用户    │ ◄────────► │  NcatBot     │ ◄────────► │  Agent       │
│             │            │  插件层       │            │  (LangChain) │
└─────────────┘            └──────────────┘            └──────┬───────┘
                                                              │
                                    ┌─────────────────────────┼───────────────┐
                                    │                         │               │
                              ┌─────▼──────┐  ┌──────────────▼┐  ┌──────────▼──────┐
                              │ File Edit  │  │ Preview Tool  │  │ Upload / Publish│
                              │ (Markdown) │  │ (Puppeteer)   │  │ (GitHub)        │
                              └────────────┘  └───────────────┘  └─────────────────┘
```

### 三层分工

| 层 | 职责 | 技术 |
|---|------|------|
| QQ 交互层 | 接收用户消息、解析 agent 输出指令、调用 NcatBot API 发送消息 | NcatBot 插件 |
| Agent 层 | 管理写作会话、调用 LLM 写内容、直接编辑 .md 文件、调用工具 | LangChain + OpenAI-compatible API |
| 工具层 | 确定性操作：预览截图、图床上传、git push 发布 | Puppeteer / Python 脚本 |

## 项目结构

```
plugins/blog-writer/
├── manifest.toml              # NcatBot 插件清单
├── __init__.py                # 插件入口：QQ 消息处理 + 协议解析
├── protocol.py                # 消息协议解析器（agent 输出 → NcatBot 调用）
├── agent/
│   ├── __init__.py
│   ├── core.py                # LangChain Agent 初始化 + 会话管理
│   ├── tools.py               # 3 个确定性工具定义
│   ├── state.py               # 会话状态（文章结构、进度）
│   └── skills/
│       └── writing-guide.md   # 写作策略 Skill 文档（agent system prompt）
├── preview/
│   ├── preview.js             # Puppeteer 截图脚本
│   └── preview.py             # Python 封装
├── uploader/
│   └── github_upload.py       # GitHub 图床上传
├── publisher/
│   └── git_push.py            # git add + commit + push
└── config_template.toml       # 配置模板
```

## 消息协议

### Agent → 插件（输出协议）

Agent 的每次输出是一段包含多个消息块的文本，用 `---MSG---` 分隔：

```
---MSG---
type: text
content: 📋 大纲如下：
1. Docker 网络模式概览
2. bridge 模式详解
---MSG---
type: image
path: .preview/section_1.png
---MSG---
type: text
content: 第 1 段已写入。回复 "ok" 继续
```

### 支持的消息类型

| type | 字段 | 对应 NcatBot 调用 |
|------|------|-------------------|
| `text` | `content` | `post_group_msg(gid, text=content)` |
| `image` | `path` (本地路径或 URL) | `send_group_image(gid, path)` |
| `confirm` | `options` (可选) | 发文本 + 设置状态机等待回复 |

### 兜底策略

如果 `---MSG---` 解析失败，将 agent 的完整原始输出作为纯文本消息发送。

### 用户 → Agent（输入映射）

| 用户消息 | Agent 收到的指令 |
|---------|----------------|
| `/blog <主题描述>` | 启动新写作会话，主题为 `<主题描述>` |
| `ok` | 确认当前段落，继续下一段 |
| `改 <反馈>` | 对当前段落给出修改意见 |
| `插图 <URL或路径>` | 在当前段落位置插入图片 |
| `预览` 或 `预览全文` | 生成全文预览截图 |
| `预览 N` | 生成第 N 段预览截图 |
| `发布` | 执行 git push 发布 |
| 其他自然语言 | 作为对当前上下文的补充说明传给 agent |

## 工具定义

### 1. preview

生成文章预览截图。

- **输入**：
  - `mode`: `"section"` | `"full"`
  - `section_index`: 段落序号（mode=section 时必需）
  - `article_path`: 文章在 Hexo 中的 URL 路径
- **流程**：
  1. 确保 hexo server 在运行（端口 4000）
  2. 写入最新 .md 内容
  3. Puppeteer 打开 `http://localhost:4000/<article_path>/`
  4. 如果是单段：通过 CSS 选择器定位到目标 `<h2>` 或 `<h3>` 下的内容区域，截取该区域
  5. 如果是全文：full page screenshot
  6. 保存到 `.preview/` 目录
- **输出**：截图的本地路径

### 2. upload_image

上传图片到 GitHub 图床。

- **输入**：`file_path`（本地文件路径）
- **流程**：
  1. 读取文件，Base64 编码
  2. 调用 GitHub API `PUT /repos/{owner}/{repo}/contents/{path}`
  3. 返回 raw.githubusercontent.com URL
- **输出**：图片 URL
- **配置**：token、仓库名、分支等从插件配置中读取

### 3. publish

提交并推送博文到 GitHub，触发自动部署。

- **输入**：`commit_message`（可选，默认自动生成）
- **流程**：
  1. `git add <article_file>`
  2. `git commit -m "post: <article_title>"`
  3. `git push origin main`
- **输出**：文章预期 URL

## 会话状态

```python
@dataclass
class ArticleState:
    """一次写作会话的状态"""
    session_id: str              # 会话唯一标识
    user_id: str                 # QQ 用户 ID
    group_id: str                # QQ 群 ID（或私聊标识）
    
    # 文章内容
    title: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    outline: list[str] = field(default_factory=list)    # 大纲标题列表
    sections: list[str] = field(default_factory=list)    # 每段 Markdown 内容
    
    # 进度
    current_index: int = 0       # 当前进行到第几段
    status: str = "init"         # "init" | "outlining" | "writing" | "reviewing" | "published"
    
    # 文件
    file_path: str = ""          # .md 文件在 source/_posts/ 下的路径
    
    # 对话历史（传给 LLM 的上下文）
    messages: list[dict] = field(default_factory=list)
```

## Skill 文档（写作策略）

`writing-guide.md` 是 agent 的 system prompt 参考，指导：

1. **大纲生成**：根据主题提取 3-7 个要点，每个要点作为 `##` 级标题
2. **段落展开**：每段 200-500 字，适合博客阅读节奏
3. **front-matter 规范**：
   ```yaml
   ---
   title: <标题>
   date: <YYYY-MM-DD>
   categories:
   - <分类>
   tags:
   - <标签1>
   - <标签2>
   ---
   ```
4. **段落粒度**：由 AI 根据内容自行决定，可以是一个 `## 小节` 也可以是多个自然段
5. **写作风格**：技术文章简洁直接，生活文允许抒情，学术文严谨
6. **交互协议**：每段写完后必须输出预览并等待用户确认（通过 `---MSG---` 协议）

## NcatBot 插件入口

```python
class BlogWriterPlugin(NcatBotPlugin):
    name = "blog_writer"
    version = "1.0.0"

    async def on_load(self):
        self.sessions: dict[str, ArticleState] = {}
        self.agent = create_agent(self.get_config("llm"))
    
    @registrar.on_group_command("blog")
    async def on_blog_command(self, event: GroupMessageEvent):
        """启动新写作会话"""
        topic = event.text.replace("/blog", "").strip()
        session = ArticleState(
            session_id=str(uuid4()),
            user_id=str(event.user_id),
            group_id=str(event.group_id),
        )
        self.sessions[f"{event.group_id}_{event.user_id}"] = session
        
        result = await self.agent.run(topic, session)
        await self._send_protocol_messages(event.group_id, result)
    
    @registrar.on_group_message()
    async def on_message(self, event: GroupMessageEvent):
        """处理会话中的后续消息"""
        key = f"{event.group_id}_{event.user_id}"
        if key not in self.sessions:
            return
        
        session = self.sessions[key]
        result = await self.agent.continue_session(event.text, session)
        await self._send_protocol_messages(event.group_id, result)
    
    async def _send_protocol_messages(self, group_id, agent_output: str):
        """解析 agent 输出协议并发送 QQ 消息"""
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
                    text=msg.get("content", "请回复确认")
                )
```

## 配置项

```toml
[blog_writer]
# 博客仓库路径
blog_repo_path = "/path/to/huanyp.cn"

# LLM 配置（OpenAI 兼容格式）
[blog_writer.llm]
base_url = "https://api.openai.com/v1"
api_key = "sk-..."
model = "gpt-4o"

# 图床配置
[blog_writer.image_host]
github_token = "ghp_..."
github_user = "huan-yp"
github_repo = "image_space"
github_branch = "master"
upload_dir = "img"

# 预览配置
[blog_writer.preview]
hexo_port = 4000
preview_dir = ".preview"
```

## 依赖

| 包 | 用途 |
|---|------|
| `ncatbot` | QQ Bot 框架 |
| `langchain` + `langchain-openai` | Agent 框架 + LLM 调用 |
| `puppeteer` (Node.js) | 浏览器截图 |
| `requests` | GitHub API 调用 |

## 开发顺序

1. 先搭 NcatBot 插件骨架 + 消息协议解析器
2. 实现 Agent 核心 + Skill 文档
3. 实现 preview tool（Puppeteer 截图）
4. 实现 upload_image tool（图床上传）
5. 实现 publish tool（git push）
6. 集成测试
