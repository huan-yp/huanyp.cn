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

    md = state.build_markdown()
    assert "title: 测试文章" in md
    assert "## 简介" in md

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
