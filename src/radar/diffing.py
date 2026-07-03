from urllib.parse import urlsplit

from radar import db


def normalise_url(url: str) -> str:
    parts = urlsplit(url.strip().lower())
    host = (parts.netloc or parts.path.split("/")[0]).removeprefix("www.")
    path = parts.path if parts.netloc else "/".join(parts.path.split("/")[1:])
    return (host + "/" + path.strip("/")).rstrip("/")


def find_new(conn, source_id: int, scraped: list[dict]) -> list[dict]:
    known_urls, known_names = db.known_keys(conn, source_id)
    out, seen = [], set()
    for c in scraped:
        nurl = normalise_url(c["url"])
        nname = c["name"].strip().lower()
        if nurl in known_urls or nname in known_names or nurl in seen:
            continue
        seen.add(nurl)
        out.append({**c, "normalised_url": nurl})
    return out


def baseline(conn, source_id: int, scraped: list[dict]) -> int:
    rows = [{**c, "normalised_url": normalise_url(c["url"])} for c in scraped]
    db.insert_companies(conn, source_id, rows, posted_at="baseline")
    return len(rows)
