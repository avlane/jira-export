"""Convert Atlassian Document Format (the JSON Jira Cloud v3 uses for rich text) to plain text."""
import datetime


def to_text(node):
    """Plain text for an ADF document. Strings pass through; None becomes an empty string."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    return "\n".join(_blocks(node.get("content") or [], 0)).strip("\n")


def _blocks(nodes, depth):
    lines = []
    for node in nodes:
        lines.extend(_block(node, depth))
    return lines


def _block(node, depth):
    kind = node.get("type")
    children = node.get("content") or []
    attrs = node.get("attrs") or {}
    if kind in ("bulletList", "orderedList"):
        out = []
        number = int(attrs.get("order", 1))
        for item in children:
            marker = "- " if kind == "bulletList" else "{}. ".format(number)
            number += 1
            inner = _blocks(item.get("content") or [], depth + 1)
            first = inner[0] if inner else ""
            out.append("  " * depth + marker + first)
            out.extend(inner[1:])
        return out
    if kind == "rule":
        return ["---"]
    if kind in ("paragraph", "heading"):
        return _inline(children).split("\n")
    if kind == "codeBlock":
        return ["    " + line for line in _inline(children).split("\n")]
    if kind == "blockquote":
        return ["> " + line for line in _blocks(children, depth)]
    if kind == "panel":
        lines = _blocks(children, depth)
        if lines:
            lines[0] = "[{}] {}".format(attrs.get("panelType", "info"), lines[0])
        return lines
    if kind == "table":
        return [" | ".join(_cell_text(cell) for cell in row.get("content") or []) for row in children]
    if kind in ("mediaSingle", "mediaGroup"):
        return [_inline(children)]
    if kind in ("expand", "nestedExpand"):
        return ([attrs["title"]] if attrs.get("title") else []) + _blocks(children, depth)
    # Containers and anything unknown: keep whatever text they hold.
    if children:
        return _blocks(children, depth)
    return [_inline([node])] if kind == "text" else []


def _cell_text(cell):
    return " ".join(line.strip() for line in _blocks(cell.get("content") or [], 0) if line.strip())


def _inline(nodes):
    parts = []
    for node in nodes:
        kind = node.get("type")
        attrs = node.get("attrs") or {}
        if kind == "text":
            parts.append(_text_with_marks(node))
        elif kind == "hardBreak":
            parts.append("\n")
        elif kind == "mention":
            parts.append(attrs.get("text", "@someone"))
        elif kind == "emoji":
            parts.append(attrs.get("text") or attrs.get("shortName", ""))
        elif kind == "inlineCard":
            parts.append(attrs.get("url", ""))
        elif kind == "status":
            parts.append("[{}]".format(attrs.get("text", "")))
        elif kind == "date":
            parts.append(_date(attrs.get("timestamp")))
        elif kind == "media":
            parts.append("[media: {}]".format(attrs.get("alt") or attrs.get("id", "")))
        elif node.get("content"):
            parts.append(_inline(node["content"]))
    return "".join(parts)


def _text_with_marks(node):
    value = node.get("text", "")
    for mark in node.get("marks") or []:
        if mark.get("type") == "link":
            href = (mark.get("attrs") or {}).get("href", "")
            if href and href != value:
                return "{} ({})".format(value, href)
    return value


def _date(timestamp):
    try:
        moment = datetime.datetime.fromtimestamp(int(timestamp) / 1000, tz=datetime.timezone.utc)
    except (TypeError, ValueError):
        return ""
    return moment.strftime("%Y-%m-%d")
