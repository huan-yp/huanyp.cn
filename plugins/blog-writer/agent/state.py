"""写作会话状态。"""

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ArticleState:
    """一次写作会话的状态。"""

    session_id: str
    user_id: str
    group_id: str

    title: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    outline: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)

    current_index: int = 0
    status: str = "init"

    file_path: str = ""

    messages: list[dict] = field(default_factory=list)

    def generate_file_path(self) -> str:
        category = self.category or "uncategorized"
        title = self.title or "untitled"
        self.file_path = f"source/_posts/{category}/{title}.md"
        return self.file_path

    def build_markdown(self) -> str:
        today = date.today().isoformat()
        content = "\n\n".join(self.sections)
        has_math = bool(re.search(r"\$.*?\$", content))

        front = [
            "---",
            f"title: {self.title}",
            f"date: {today}",
        ]
        if has_math:
            front.append("mathjax: true")
        if self.category:
            front.append("categories:")
            front.append(f"- {self.category}")
        if self.tags:
            front.append("tags:")
            for tag in self.tags:
                front.append(f"- {tag}")
        front.append("---")

        return "\n".join(front) + "\n\n" + content + "\n"
