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
