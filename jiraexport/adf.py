"""Convert Atlassian Document Format (the JSON Jira Cloud v3 uses for rich text) to plain text."""


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
    if kind in ("bulletList", "orderedList"):
        out = []
        number = int((node.get("attrs") or {}).get("order", 1))
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
    # Containers and anything unknown: keep whatever text they hold.
    if children:
        return _blocks(children, depth)
    return [_inline([node])] if kind == "text" else []


def _inline(nodes):
    parts = []
    for node in nodes:
        kind = node.get("type")
        if kind == "text":
            parts.append(node.get("text", ""))
        elif kind == "hardBreak":
            parts.append("\n")
        elif kind == "mention":
            parts.append((node.get("attrs") or {}).get("text", "@someone"))
        elif node.get("content"):
            parts.append(_inline(node["content"]))
    return "".join(parts)
