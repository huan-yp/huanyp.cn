from protocol import parse_protocol


def test_parse_single_text():
    raw = "---MSG---\ntype: text\ncontent: hello world"
    result = parse_protocol(raw)
    assert result == [{"type": "text", "content": "hello world"}]


def test_parse_multiple_messages():
    raw = (
        "---MSG---\n"
        "type: text\n"
        "content: 大纲如下：\n"
        "1. 第一节\n"
        "2. 第二节\n"
        "---MSG---\n"
        "type: image\n"
        "path: .preview/section_1.png\n"
        "---MSG---\n"
        "type: text\n"
        "content: 回复 ok 继续"
    )
    result = parse_protocol(raw)
    assert len(result) == 3
    assert result[0]["type"] == "text"
    assert "大纲如下" in result[0]["content"]
    assert "1. 第一节" in result[0]["content"]
    assert result[1] == {"type": "image", "path": ".preview/section_1.png"}
    assert result[2]["type"] == "text"


def test_parse_confirm():
    raw = "---MSG---\ntype: confirm\ncontent: 确认发布？"
    result = parse_protocol(raw)
    assert result == [{"type": "confirm", "content": "确认发布？"}]


def test_fallback_no_separator():
    raw = "这是一段没有协议格式的纯文本"
    result = parse_protocol(raw)
    assert result == []


def test_fallback_empty():
    result = parse_protocol("")
    assert result == []


def test_multiline_content():
    raw = (
        "---MSG---\n"
        "type: text\n"
        "content: 第一行\n"
        "第二行\n"
        "第三行"
    )
    result = parse_protocol(raw)
    assert result[0]["content"] == "第一行\n第二行\n第三行"


def test_content_with_colon():
    raw = "---MSG---\ntype: text\ncontent: 时间：2026-04-11"
    result = parse_protocol(raw)
    assert result[0]["content"] == "时间：2026-04-11"
