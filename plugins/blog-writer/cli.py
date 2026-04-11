"""终端交互版 Blog Writer，复用全部真实工具，仅交互方式不同。

用法:
    python cli.py                          # 使用 config.toml
    python cli.py --config my_config.toml  # 指定配置文件
    python cli.py --debug                  # 显示调试信息
"""

import asyncio
import sys
import tomllib
from pathlib import Path
from uuid import uuid4

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI

from agent.core import create_agent
from agent.state import ArticleState
from protocol import parse_protocol

# ANSI 颜色
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def load_config(path: str = "config.toml") -> dict:
    p = Path(path)
    if not p.exists():
        print(f"配置文件不存在: {p.absolute()}")
        print(f"请复制 config_template.toml 为 {path} 并填写")
        sys.exit(1)
    with open(p, "rb") as f:
        return tomllib.load(f)


_DEBUG = False


def display_output(agent_output: str):
    """解析协议并终端渲染。"""
    if _DEBUG:
        print(f"{_DIM}[debug] raw output ({len(agent_output)} chars):{_RESET}")
        print(f"{_DIM}{agent_output[:500]}{_RESET}")
        if len(agent_output) > 500:
            print(f"{_DIM}... (truncated){_RESET}")
        print()

    messages = parse_protocol(agent_output)

    if _DEBUG:
        print(f"{_DIM}[debug] protocol parsed: {len(messages)} messages{_RESET}")
        if not messages:
            print(f"{_DIM}[debug] NO ---MSG--- found, using fallback{_RESET}")

    if not messages:
        # 兜底：直接输出原文
        print(f"{_GREEN}{agent_output}{_RESET}")
        return

    for msg in messages:
        if msg["type"] == "text":
            print(f"{_GREEN}{msg['content']}{_RESET}")
        elif msg["type"] == "image":
            img_path = Path(msg["path"]).resolve()
            print(f"{_YELLOW}[图片] {img_path}{_RESET}")
            if img_path.exists():
                print(f"{_DIM}      文件大小: {img_path.stat().st_size} bytes{_RESET}")
            else:
                print(f"{_DIM}      (文件不存在){_RESET}")
        elif msg["type"] == "confirm":
            print(f"{_YELLOW}[确认] {msg.get('content', '请回复确认')}{_RESET}")
        print()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Blog Writer 终端交互版")
    parser.add_argument("--config", default="config.toml", help="配置文件路径")
    parser.add_argument("--debug", action="store_true", help="显示调试信息")
    args = parser.parse_args()

    global _DEBUG
    _DEBUG = args.debug

    raw_config = load_config(args.config)
    config = raw_config.get("blog_writer", raw_config)
    agent = create_agent(config)
    agent.debug = args.debug

    session = PromptSession()

    print(f"{_CYAN}=== Blog Writer CLI ==={_RESET}")
    print(f"{_DIM}输入主题开始写作，输入 '退出' 结束{_RESET}")
    print()

    topic = (await session.prompt_async(ANSI(f"{_CYAN}主题> {_RESET}"))).strip()
    if not topic:
        print("需要一个主题")
        return

    state = ArticleState(
        session_id=str(uuid4()),
        user_id="cli",
        group_id="cli",
    )

    print()
    result = await agent.run(topic, state)
    display_output(result)

    # 交互循环
    while state.status != "published":
        try:
            user_input = (await session.prompt_async(ANSI(f"{_CYAN}回复> {_RESET}"))).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出")
            break

        if not user_input:
            continue
        if user_input in ("退出", "取消", "结束"):
            print("写作会话已结束")
            break

        print()
        result = await agent.continue_session(user_input, state)
        display_output(result)

    # 写完后保存 markdown 到本地
    if state.sections:
        md = state.build_markdown()
        path = state.generate_file_path()
        blog_repo = config.get("blog_repo_path", ".")
        full_path = Path(blog_repo) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(md, encoding="utf-8")
        print(f"\n{_GREEN}文章已保存: {full_path}{_RESET}")


if __name__ == "__main__":
    asyncio.run(main())
