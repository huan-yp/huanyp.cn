"""消息协议解析器。

将 Agent 输出的 ---MSG--- 分隔的文本解析为消息列表。
每个消息是一个 dict，包含 type 和对应字段（content/path/options）。
解析失败时返回空列表，由调用方执行兜底策略。
"""

_SEPARATOR = "---MSG---"


def parse_protocol(raw: str) -> list[dict]:
    if _SEPARATOR not in raw:
        return []

    blocks = raw.split(_SEPARATOR)
    messages = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        msg = _parse_block(block)
        if msg is not None:
            messages.append(msg)

    return messages


def _parse_block(block: str) -> dict | None:
    lines = block.split("\n")
    if not lines:
        return None

    first_line = lines[0].strip()
    if not first_line.startswith("type:"):
        return None

    msg_type = first_line.split(":", 1)[1].strip()
    if not msg_type:
        return None

    msg = {"type": msg_type}

    i = 1
    while i < len(lines):
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if key == "content":
                remaining = [value] + [l for l in lines[i + 1 :]]
                msg["content"] = "\n".join(remaining).rstrip()
                break
            else:
                msg[key] = value
        i += 1

    return msg
