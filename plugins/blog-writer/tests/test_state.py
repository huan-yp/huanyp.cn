from agent.state import ArticleState


def test_create_default():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    assert s.title == ""
    assert s.status == "init"
    assert s.sections == []
    assert s.messages == []


def test_file_path_generation():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    s.title = "Docker 实践"
    s.category = "技术"
    path = s.generate_file_path()
    assert path == "source/_posts/技术/Docker 实践.md"


def test_build_markdown():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    s.title = "测试文章"
    s.category = "技术"
    s.tags = ["Python", "测试"]
    s.sections = ["## 第一节\n\n内容一", "## 第二节\n\n内容二"]

    md = s.build_markdown()
    assert "title: 测试文章" in md
    assert "categories:" in md
    assert "- 技术" in md
    assert "- Python" in md
    assert "## 第一节" in md
    assert "## 第二节" in md


def test_build_markdown_with_mathjax():
    s = ArticleState(session_id="abc", user_id="123", group_id="456")
    s.title = "公式文章"
    s.category = "学术"
    s.tags = ["数学"]
    s.sections = ["## 定义\n\n$E=mc^2$"]

    md = s.build_markdown()
    assert "mathjax: true" in md
