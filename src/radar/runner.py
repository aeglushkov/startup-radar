import ast
import json
import os
import subprocess
import sys

BOOT = os.path.join(os.path.dirname(__file__), "_boot.py")
ALLOWED_THIRD_PARTY = {"httpx", "bs4"}
SCRAPER_TIMEOUT = 120


class ScraperError(Exception):
    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"[{stage}] {message}")


def check_imports(path: str) -> list[str]:
    tree = ast.parse(open(path).read())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return sorted(
        r for r in roots
        if r not in sys.stdlib_module_names and r not in ALLOWED_THIRD_PARTY
    )


def run_scraper(path: str, timeout: int = SCRAPER_TIMEOUT) -> list[dict]:
    bad = check_imports(path)
    if bad:
        raise ScraperError("imports", f"disallowed imports: {bad}")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": "/tmp", "LANG": "C.UTF-8"}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", BOOT, path],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        raise ScraperError("timeout", f"exceeded {timeout}s")
    if proc.returncode != 0:
        raise ScraperError("exec", proc.stderr[-2000:])
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ScraperError("schema", f"stdout is not JSON: {e}")
    return _validate(raw)


def _validate(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise ScraperError("schema", "output is not a list")
    out = []
    for i, c in enumerate(raw):
        if not isinstance(c, dict):
            raise ScraperError("schema", f"item {i} is not a dict")
        name, url = c.get("name"), c.get("url")
        if not (isinstance(name, str) and name.strip()):
            raise ScraperError("schema", f"item {i}: missing/empty name")
        if not (isinstance(url, str) and url.strip()):
            raise ScraperError("schema", f"item {i}: missing/empty url")
        desc = c.get("description")
        if desc is not None and not isinstance(desc, str):
            raise ScraperError("schema", f"item {i}: description must be str|null")
        extra = c.get("extra")
        if extra is not None and not isinstance(extra, dict):
            raise ScraperError("schema", f"item {i}: extra must be dict|null")
        out.append({"name": name.strip(), "url": url.strip(),
                    "description": desc, "extra": extra})
    return out
