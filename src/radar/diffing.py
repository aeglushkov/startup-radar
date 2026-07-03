from urllib.parse import urlsplit

from radar import db


def normalise_url(url: str) -> str:
    u = url.strip().lower()
    if "://" not in u:
        u = "//" + u
    parts = urlsplit(u)
    host = parts.netloc.removeprefix("www.")
    return (host + "/" + parts.path.strip("/")).rstrip("/")


def find_new(conn, source_id: int, scraped: list[dict]) -> list[dict]:
    known_urls, known_names = db.known_keys(conn, source_id)
    out, seen_urls, seen_names = [], set(), set()
    for c in scraped:
        nurl = normalise_url(c["url"])
        nname = c["name"].strip().lower()
        if (nurl in known_urls or nname in known_names
                or nurl in seen_urls or nname in seen_names):
            continue
        seen_urls.add(nurl)
        seen_names.add(nname)
        out.append({**c, "normalised_url": nurl})
    return out


def baseline(conn, source_id: int, scraped: list[dict]) -> int:
    rows = [{**c, "normalised_url": normalise_url(c["url"])} for c in scraped]
    db.insert_companies(conn, source_id, rows, posted_at="baseline")
    return len(rows)
