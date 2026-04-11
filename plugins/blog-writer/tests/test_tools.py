import subprocess
from unittest.mock import patch, MagicMock
import pytest

from publisher.git_push import git_publish
from uploader.github_upload import upload_to_github
from preview.preview import take_screenshot
from agent.tools import build_tools


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


def test_upload_to_github():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "content": {
            "download_url": "https://raw.githubusercontent.com/user/repo/main/img/test.png"
        }
    }

    with patch("uploader.github_upload.requests.put", return_value=mock_response):
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
    mock_409.status_code = 422
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


def test_build_tools_returns_four():
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
    assert len(tools) == 4
    names = {t.name for t in tools}
    assert names == {"save_draft", "preview", "upload_image", "publish"}
