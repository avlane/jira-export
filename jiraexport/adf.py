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
    match kind:
        case "bulletList" | "orderedList":
            return _list(kind, children, int(attrs.get("order", 1)), depth)
        case "rule":
            return ["---"]
        case "paragraph" | "heading":
            return _inline(children).split("\n")
        case "codeBlock":
            return ["    " + line for line in _inline(children).split("\n")]
        case "blockquote":
            return ["> " + line for line in _blocks(children, depth)]
        case "panel":
            lines = _blocks(children, depth)
            if lines:
                lines[0] = "[{}] {}".format(attrs.get("panelType", "info"), lines[0])
            return lines
        case "table":
            return [" | ".join(_cell_text(cell) for cell in row.get("content") or []) for row in children]
        case "mediaSingle" | "mediaGroup":
            return [_inline(children)]
        case "expand" | "nestedExpand":
            return ([attrs["title"]] if attrs.get("title") else []) + _blocks(children, depth)
        case "taskList":
            return [_task(child) if child.get("type") == "taskItem" else line
                    for child in children for line in ([""] if child.get("type") == "taskItem" else _block(child, depth))]
        case "decisionList":
            return ["Decision{}: {}".format(" (open)" if (c.get("attrs") or {}).get("state") == "UNDECIDED" else "", _inline(c.get("content") or []))
                    for c in children]
        case "extension" | "bodiedExtension":
            label = attrs.get("text") or attrs.get("extensionKey", "extension")
            return ["[{}]".format(label)] + (_blocks(children, depth) if kind == "bodiedExtension" else [])
        case "text":
            return [_inline([node])]
        case _:
            # Containers and anything unknown: keep whatever text they hold.
            return _blocks(children, depth) if children else []


def _task(item):
    done = (item.get("attrs") or {}).get("state") == "DONE"
    return "[{}] {}".format("x" if done else " ", _inline(item.get("content") or []))


def _list(kind, items, number, depth):
    out = []
    for item in items:
        marker = "- " if kind == "bulletList" else "{}. ".format(number)
        number += 1
        inner = _blocks(item.get("content") or [], depth + 1)
        out.append("  " * depth + marker + (inner[0] if inner else ""))
        out.extend(inner[1:])
    return out


def _cell_text(cell):
    return " ".join(line.strip() for line in _blocks(cell.get("content") or [], 0) if line.strip())


def _inline(nodes):
    parts = []
    for node in nodes:
        attrs = node.get("attrs") or {}
        match node.get("type"):
            case "text":
                parts.append(_text_with_marks(node))
            case "hardBreak":
                parts.append("\n")
            case "mention":
                parts.append(attrs.get("text", "@someone"))
            case "emoji":
                parts.append(attrs.get("text") or attrs.get("shortName", ""))
            case "inlineCard":
                parts.append(attrs.get("url", ""))
            case "status":
                parts.append("[{}]".format(attrs.get("text", "")))
            case "date":
                parts.append(_date(attrs.get("timestamp")))
            case "media" | "mediaInline":
                parts.append("[media: {}]".format(attrs.get("alt") or attrs.get("id", "")))
            case "inlineExtension":
                parts.append("[{}]".format(attrs.get("text") or attrs.get("extensionKey", "extension")))
            case _:
                if node.get("content"):
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
