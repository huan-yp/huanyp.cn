"""LangChain Tool 定义：preview, upload_image, publish。"""

import re
import subprocess
from pathlib import Path

from langchain_core.tools import tool

from preview.preview import take_screenshot
from uploader.github_upload import upload_to_github
from publisher.git_push import git_publish


class ToolList(list):
    """可挂载 _ctx 的 list 子类。"""
    pass


def _write_state_to_disk(state, blog_repo: str) -> str:
    """把 state 的 markdown 写入磁盘，返回文件相对路径。"""
    md = state.build_markdown()
    file_path = state.file_path or state.generate_file_path()
    full_path = Path(blog_repo) / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(md, encoding="utf-8")
    return file_path


def _hexo_generate(blog_repo: str) -> None:
    """运行 hexo generate 让 abbrlink 生成。"""
    subprocess.run(
        ["npx", "hexo", "generate"],
        cwd=blog_repo,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _read_abbrlink(blog_repo: str, file_path: str) -> str:
    """从文件 front-matter 读取 hexo-abbrlink 生成的 abbrlink。"""
    full_path = Path(blog_repo) / file_path
    content = full_path.read_text(encoding="utf-8")
    m = re.search(r"^abbrlink:\s*(\S+)", content, re.MULTILINE)
    if m:
        return m.group(1)
    return ""


def build_tools(config: dict) -> list:
    """根据配置构建工具列表。

    工具通过闭包访问 config 和 _ctx。
    _ctx 是一个可变 dict，由 BlogWriterAgent._execute_tools 在调用前注入 state。
    """
    blog_repo = config.get("blog_repo_path", "")
    preview_cfg = config.get("preview", {})
    image_cfg = config.get("image_host", {})

    # 运行时上下文，由 _execute_tools 注入
    _ctx: dict = {}

    @tool
    def preview(mode: str = "full", section_index: int = 0) -> str:
        """生成当前文章的预览截图。URL 自动从 hexo abbrlink 推导，无需手动指定。

        Args:
            mode: "full" 全页截图，"section" 截取指定段落
            section_index: mode=section 时，段落序号（从 1 开始）
        """
        state = _ctx.get("state")
        if not state or not state.sections:
            return "错误: 当前没有内容可预览"

        # 1. 写入磁盘
        file_path = _write_state_to_disk(state, blog_repo)

        # 2. hexo generate 让 abbrlink 生成
        _hexo_generate(blog_repo)

        # 3. 读回 abbrlink
        abbrlink = _read_abbrlink(blog_repo, file_path)
        if not abbrlink:
            return f"错误: hexo generate 后未找到 abbrlink，文件: {file_path}"

        # 4. 构造 URL 并截图
        port = preview_cfg.get("hexo_port", 4000)
        url = f"http://localhost:{port}/posts/{abbrlink}.html"
        preview_dir = preview_cfg.get("preview_dir", ".preview")
        node_path = preview_cfg.get("node_path", "node")

        if mode == "section":
            selector = f"#section-{section_index}"
            output = f"{preview_dir}/section_{section_index}.png"
        else:
            selector = ""
            output = f"{preview_dir}/full.png"

        result = take_screenshot(url, output, selector, node_path)
        return f"截图已保存: {result} (URL: {url})"

    @tool
    def upload_image(file_path: str) -> str:
        """上传图片到 GitHub 图床，返回 URL。

        Args:
            file_path: 本地图片文件路径
        """
        return upload_to_github(
            file_path=file_path,
            token=image_cfg.get("github_token", ""),
            user=image_cfg.get("github_user", ""),
            repo=image_cfg.get("github_repo", ""),
            branch=image_cfg.get("github_branch", "main"),
            upload_dir=image_cfg.get("upload_dir", "img"),
        )

    @tool
    def save_draft(title: str, category: str, tags: str, content: str) -> str:
        """保存当前草稿内容。每次写完一段新内容后必须调用此工具保存，preview 和 publish 才能读取到最新内容。

        Args:
            title: 文章标题
            category: 分类（如 技术、生活、科普、学术、OI）
            tags: 标签，用英文逗号分隔（如 SSH,Linux,网络）
            content: 文章正文的完整 Markdown 内容（不含 front-matter），包含已写好的所有段落
        """
        state = _ctx.get("state")
        if not state:
            return "错误: 没有活跃的写作会话"
        state.title = title
        state.category = category
        state.tags = [t.strip() for t in tags.split(",") if t.strip()]
        state.sections = [content]
        file_path = _write_state_to_disk(state, blog_repo)
        return f"草稿已保存: {file_path}"

    @tool
    def publish(commit_message: str = "") -> str:
        """提交并推送博文到 GitHub，触发自动部署。

        Args:
            commit_message: 提交信息，为空则自动生成
        """
        state = _ctx.get("state")
        file_path = ""
        if state:
            file_path = _write_state_to_disk(state, blog_repo)
            state.status = "published"
        return git_publish(
            repo_path=blog_repo,
            file_path=file_path,
            commit_message=commit_message,
        )

    tools = ToolList([save_draft, preview, upload_image, publish])
    # 把 _ctx 挂到列表上，让 core.py 能更新它
    tools._ctx = _ctx
    return tools
