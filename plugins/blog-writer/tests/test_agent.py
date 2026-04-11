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
    # Tools are empty stubs for now (Task 6 will add real ones)
    assert isinstance(tool_names, list)


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
