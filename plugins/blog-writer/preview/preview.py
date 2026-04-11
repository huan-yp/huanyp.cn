"""Puppeteer 截图的 Python 封装。"""

import subprocess
from pathlib import Path


_SCRIPT_PATH = Path(__file__).parent / "preview.js"


def take_screenshot(
    article_url: str,
    output_path: str,
    section_selector: str = "",
    node_path: str = "node",
) -> str:
    """调用 Puppeteer 截图并返回截图路径。

    Args:
        article_url: 文章的完整 URL
        output_path: 截图保存路径
        section_selector: CSS 选择器，空则全页截图
        node_path: node 可执行文件路径

    Returns:
        截图文件路径
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [node_path, str(_SCRIPT_PATH), article_url, output_path]
    if section_selector:
        cmd.append(section_selector)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"截图失败: {result.stderr}")

    return output_path
