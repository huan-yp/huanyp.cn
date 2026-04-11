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

        if text.startswith("/blog"):
            return

        session = self.sessions[key]

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

        if session.status == "published":
            del self.sessions[key]

    async def _send_protocol_messages(self, group_id, agent_output: str):
        """解析 agent 输出协议并发送 QQ 消息。"""
        messages = parse_protocol(agent_output)

        if not messages:
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
