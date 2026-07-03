import html

MAX_LEN = 4000
HEADER = "📡 <b>Startups radar</b>"


def html_escape(s: str) -> str:
    return html.escape(s, quote=False)


def _company_line(c: dict) -> str:
    line = f'• <a href="{c["url"]}">{html_escape(c["name"])}</a>'
    if c.get("one_liner"):
        line += f" — {html_escape(c['one_liner'])}"
    elif c.get("description"):
        line += f" — {html_escape(c['description'])}"
    if c.get("tags"):
        line += " " + " ".join("#" + html_escape(t) for t in c["tags"])
    return line


def compose(sections: list[tuple[str, list[dict]]], footer: str) -> list[str]:
    blocks: list[str] = [HEADER]
    if not sections:
        blocks.append("Nothing new today.")
    for source_name, companies in sections:
        blocks.append(f"<b>{html_escape(source_name)}</b>\n"
                      + "\n".join(_company_line(c) for c in companies))
    blocks.append(f"<i>{html_escape(footer)}</i>")

    messages, current = [], ""
    for block in blocks:
        for piece in block.split("\n"):
            if len(current) + len(piece) + 1 > MAX_LEN:
                messages.append(current.rstrip())
                current = ""
            current += piece + "\n"
        current += "\n"
    if current.strip():
        messages.append(current.rstrip())
    return messages
