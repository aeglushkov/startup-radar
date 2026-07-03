import logging
import pathlib
import subprocess
from dataclasses import dataclass

from radar import db
from radar.config import Config
from radar.diffing import baseline
from radar.runner import ScraperError, run_scraper

log = logging.getLogger(__name__)
REPO_ROOT = pathlib.Path(__file__).parents[2]
PROMPT_PATH = REPO_ROOT / "prompts" / "scraper_prompt.md"
EXEMPLAR_PATH = REPO_ROOT / "scrapers" / "ycombinator.py"
CODEX_TIMEOUT = 600


@dataclass
class GenResult:
    ok: bool
    count: int
    error: str | None


def render_prompt(name: str, url: str, slug: str, scrapers_dir: str,
                  feedback: str = "") -> str:
    template = PROMPT_PATH.read_text()
    return template.format(
        name=name, url=url, slug=slug, scrapers_dir=scrapers_dir,
        exemplar=EXEMPLAR_PATH.read_text(),
        feedback=feedback,
    )


def _invoke_codex(prompt: str, cfg: Config) -> None:
    subprocess.run(
        ["codex", "exec", "--full-auto", prompt],
        cwd=REPO_ROOT, capture_output=True, text=True,
        timeout=CODEX_TIMEOUT, check=True,
    )


def _git_commit(path: str, slug: str) -> None:
    subprocess.run(["git", "add", path], cwd=REPO_ROOT, check=False)
    subprocess.run(["git", "commit", "-m", f"feat: add generated scraper for {slug}"],
                   cwd=REPO_ROOT, check=False)


def _attempt(cfg: Config, slug: str, prompt: str) -> tuple[list[dict] | None, str | None]:
    path = pathlib.Path(cfg.scrapers_dir) / f"{slug}.py"
    try:
        _invoke_codex(prompt, cfg)
    except (subprocess.SubprocessError, OSError) as e:
        return None, f"codex invocation failed: {e}"
    if not path.exists():
        return None, f"codex did not create {path}"
    try:
        return run_scraper(str(path)), None
    except ScraperError as e:
        return None, str(e)


def generate_and_enable(cfg: Config, slug: str, name: str, url: str) -> GenResult:
    conn = db.get_conn(cfg.db_path)
    path = str(pathlib.Path(cfg.scrapers_dir) / f"{slug}.py")
    prompt = render_prompt(name, url, slug, cfg.scrapers_dir)
    companies, error = _attempt(cfg, slug, prompt)

    if companies is None:
        retry_prompt = render_prompt(
            name, url, slug, cfg.scrapers_dir,
            feedback=f"\nA previous attempt failed its self-test with this error — fix it:\n{error}",
        )
        companies, error = _attempt(cfg, slug, retry_prompt)

    if companies is None or len(companies) == 0:
        db.set_source_status(conn, slug, "failed")
        return GenResult(ok=False, count=0,
                         error=error or "self-test returned 0 companies")

    src = db.get_source(conn, slug)
    n = baseline(conn, src["id"], companies)
    db.update_source_after_run(conn, slug, n)
    db.set_source_status(conn, slug, "active")
    _git_commit(path, slug)
    return GenResult(ok=True, count=n, error=None)
