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

        if resp.status_code == 422:
            continue

        resp.raise_for_status()

    raise RuntimeError(f"上传失败，尝试 3 次仍然冲突: {filename}")
