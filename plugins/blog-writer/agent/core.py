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

        self._debug(f"[invoke] 发送 {len(lc_messages)} 条消息给 LLM")
        response = await self.llm_with_tools.ainvoke(lc_messages)
        self._debug(f"[invoke] LLM 返回 content 长度={len(response.content or '')}, tool_calls={len(response.tool_calls)}")

        # 处理工具调用（最多 3 轮）
        for round_i in range(3):
            if not response.tool_calls:
                break
            self._debug(f"[invoke] 工具调用第 {round_i + 1} 轮: {[c['name'] for c in response.tool_calls]}")
            tool_results = await self._execute_tools(response.tool_calls, state)
            state.messages.append({"role": "assistant", "content": response.content or ""})
            tool_summary = "\n".join(
                f"工具 {r['name']} 返回: {r['result']}" for r in tool_results
            )
            state.messages.append({"role": "user", "content": tool_summary})
            lc_messages.append(AIMessage(content=response.content or ""))
            lc_messages.append(HumanMessage(content=tool_summary))
            response = await self.llm_with_tools.ainvoke(lc_messages)
            self._debug(f"[invoke] 第 {round_i + 1} 轮后 LLM 返回 content 长度={len(response.content or '')}")

        result = response.content or ""
        state.messages.append({"role": "assistant", "content": result})
        self._debug(f"[invoke] 最终输出前 200 字: {result[:200]!r}")
        return result

    def _debug(self, msg: str):
        """输出调试信息（仅 debug=True 时）。"""
        if getattr(self, 'debug', False):
            print(f"\033[2m{msg}\033[0m")

    async def _execute_tools(
        self, tool_calls: list, state: ArticleState
    ) -> list[dict]:
        """执行 LLM 请求的工具调用。"""
        # 注入 state 到工具上下文
        if hasattr(self.tools, '_ctx'):
            self.tools._ctx["state"] = state

        tool_map = {t.name: t for t in self.tools}
        results = []
        for call in tool_calls:
            tool = tool_map.get(call["name"])
            if tool is None:
                self._debug(f"[tool] 未找到工具: {call['name']}")
                results.append({"name": call["name"], "result": "工具不存在"})
                continue
            args = call.get("args", {})
            self._debug(f"[tool] 调用 {call['name']}({args})")
            try:
                result = await tool.ainvoke(args)
                self._debug(f"[tool] {call['name']} 返回: {str(result)[:200]}")
                results.append({"name": call["name"], "result": str(result)})
            except Exception as e:
                self._debug(f"[tool] {call['name']} 异常: {e}")
                results.append({"name": call["name"], "result": f"错误: {e}"})
        return results
