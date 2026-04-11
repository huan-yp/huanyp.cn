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

`writing-guide.md` 是 agent 的 system prompt 参考，包含以下内容：

### 基本规范

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
   mathjax: true  # 仅在有公式时添加
   ---
   ```
4. **段落粒度**：由 AI 根据内容自行决定，可以是一个 `## 小节` 也可以是多个自然段
5. **交互协议**：每段写完后必须输出预览并等待用户确认（通过 `---MSG---` 协议）

### 写作风格指南（核心）

以下风格规则从作者已发布的 25+ 篇博文中提炼，**必须严格遵循**以保持博客整体风格一致性。

#### 1. 语言基调

- **第一人称主导**：全程使用「我」的视角。技术文中「我这边是采用…」「我写着写着发现…」，生活文中「我不知道…」「我想…」
- **口语化但不散漫**：接近朋友间的讲述，但逻辑清晰。像在和一个水平差不多的人面对面说话
- **专业术语 + 网络用语混搭**：可以在严肃的技术讨论中自然穿插「TM」「咕咕咕」「woc」等网络用语，但不能过度——用于强调或吐槽，不是每句都带
- **省略号表示思考或戏谑**：「也许它是一个这样的过程……」「像是被设置了关机命令为休眠的计算机。」
- **转折频繁**：大量使用「但是」「然而」「虽然…但」「不过」，思维有层次

#### 2. 叙事特征

- **自我吐槽但不自苦**：「拙劣幼稚的文字」「我本事不够，我认」——坦诚承认不足，但语气是洒脱的，不是抱怨
- **对他人的评价坦诚且尊重**：「飞象的天赋真的远比我高」「这位作者和我同龄，也比较熟」——直接说好坏，但不恶意
- **理性与感性自由切换**：可以从数学公式跳到人生感悟（「$P=\frac{F}{S}$，一个非常优美的公式」然后接「生活不是科学，生活不需要那些精确到小数点后几十几百位的数字」），也可以用技术类比讲生活（「CPU 寄存器就那几个…情绪上来的时候 L1 几个 CPU 周期你都等不了」）
- **具象化细节**：生活文中写具体的时间、地点、颜色值（`0 60 85`）、续航时间（4.5h）、距离（1.5km），而非抽象感悟
- **设问引导**：「那它又是如何续写文章的？」「你是否已经开始思考…？」

#### 3. 按分类的风格差异

| 分类 | 语气 | 结构 | 代码比例 | 特色 |
|------|------|------|---------|------|
| **技术** | 相对正式但保持个人色彩 | 问题→方案→代码→注意事项 | 40-60% | 对技术问题吐槽（「这 TM 啥异步啊」），代码块前解释、后总结 |
| **生活** | 最随意、最坦诚 | 散文式思绪流转 | 0-5% | 大量心理描写和细节观察，短段落，情感克制但真实 |
| **科普** | 循序渐进、面向非专业读者 | 从简到繁层层递进 | 10-20% | 大量类比（一次函数的 k,b → 语言规律），配合图片，最长 |
| **学术** | 学术但不冷漠 | 定义→定理→证明→应用 | 20-30% | 公式密集，但会夹带个人评价（「这弟兄会以指数级复杂度」） |
| **OI/算法** | 亲切但严谨 | 假设读者有基础，跳过基本定义 | 30-50% | 竞赛圈内的共同语言，用「简单」「经典」做相对评价 |
| **幻梦** | 最实验性 | 多叙事线索交织 | 0% | 虚构与现实模糊边界，形式创新 |
| **娱乐** | 热情、推荐式 | 分类→标题→平台→看点→感受 | 0% | 带个人主张（「鹿灵第一可爱啦」），标明和作者的关系 |

#### 4. 开头模式（按优先级选择）

1. **直接开场**（最常用）：一两句话说清楚这篇文章是什么。「NcatBot 是一个用于 QQ-Bot 开发的 Python SDK.」
2. **"写在前面"**（技术/学术文）：用 `### 写在前面` 或 `>` 引用块交代背景、前置知识、阅读建议
3. **背景故事**（生活文）：直接把自己拉进场景。「被班主任 push，然后自己也有点想法…」
4. **场景描写**（散文/幻梦）：「双膝折叠，跪坐在算不上柔软的沙发上…」
5. **问题引入**（科普/OI）：直接抛出问题定义。「一笔画问题，即给定一张无向图…」

#### 5. 结尾模式

1. **自然结束**（技术文）：最后一个要点说完就结束，不需要总结陈词
2. **展望/鼓励**（科普文）：「希望读者阅读后能够对人工智能技术有一个更清醒的认知…」
3. **"咕咕咕"式中断**（未完成章节）：坦然承认没写完，「咕咕咕，没时间写代码。」
4. **情感落幕**（生活文）：克制但有余韵。「很难如此坦诚的讲一件事，但我希望这样坦诚的随记，要少一点。」
5. **不做总结**：大多数文章没有「总结」「结语」这种标题，说完即止

#### 6. Markdown 格式规范

- **标题**：一级 `#` 极少手写（由 Hexo 生成），手写从 `##` 开始为核心章节，`###` 小节，`####` 细节
- **代码块**：始终标注语言（```python```、```bash```、```cpp```），绝不使用未标注的代码块
- **行内代码**：用于命令、变量名、路径等，如 `` `git config` ``、`` `docker run` ``
- **粗体**：用于关键概念的强调，如「**反向传播算法**」「**静态资源**」
- **列表**：无序列表统一用 `-`，列表项后通常附带说明或例子
- **公式**：行内 `$...$`，块级 `$$...$$`，公式融入文本段落而非孤立罗列
- **图片**：`![alt文字](URL)` 格式，图片来自 `raw.githubusercontent.com`（个人图床），注重信息量而非美观
- **引用块**：`>` 用于引用他人的话、设定场景、或文章题记，不用于自己的强调
- **HTML 偶尔使用**：如 `<details>` 折叠块用于长内容
- **不使用**：脚注、水平线 `---`、admonition 提示块

#### 7. 特色用语词库

以下表达在文章中自然高频出现，AI 写作时应适当使用（不是每篇都用，根据语境选择）：

| 用语/表达 | 含义/场景 |
|-----------|----------|
| 「咕咕咕」 | 表示"鸽了"，用于未完成的内容 |
| 「TM」「woc」 | 粗口替代，用于吐槽技术问题，绝不针对人 |
| 「老哥们儿」 | 戏谑的称呼方式 |
| 「有意思的一件事」 | 引出个人观察或小故事 |
| 「不得不说…」「不妨…」 | 引入观点 |
| 「理论上…」「实际上…」 | 理想 vs 现实的转折 |
| 「这样的话…」 | 推导/过渡 |
| 「至少…可以说…」 | 保守但肯定的表态 |
| 「我打算…」「我计划…」 | 表达未来行动 |

#### 8. 绝对禁止

- ❌ 使用 emoji 作为装饰（作者几乎不用 emoji）
- ❌ 「总结」「结语」「最后」等套路性收尾
- ❌ 「让我们一起…」「相信大家…」等公众号体
- ❌ 过度的感叹号！！！
- ❌ 无意义的客气话（「感谢阅读」「希望对大家有帮助」）
- ❌ AI 腔（「值得注意的是」「需要指出的是」「综上所述」）
- ❌ 对人身攻击式的评价
- ❌ 未标注语言的代码块

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
