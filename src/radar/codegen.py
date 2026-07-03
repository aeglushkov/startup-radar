import logging
import os
import pathlib
import subprocess
from dataclasses import dataclass

from radar import db
from radar.config import Config
from radar.diffing import find_new
from radar.runner import ScraperError, run_scraper

log = logging.getLogger(__name__)
CODEX_TIMEOUT = 600


def _repo_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get("APP_ROOT") or pathlib.Path(__file__).parents[2])


@dataclass
class GenResult:
    ok: bool
    count: int
    error: str | None


def render_prompt(name: str, url: str, slug: str, scrapers_dir: str,
                  feedback: str = "") -> str:
    root = _repo_root()
    template = (root / "prompts" / "scraper_prompt.md").read_text()
    return template.format(
        name=name, url=url, slug=slug, scrapers_dir=scrapers_dir,
        exemplar=(root / "scrapers" / "y-combinator.py").read_text(),
        feedback=feedback,
    )


def _invoke_codex(prompt: str, cfg: Config) -> None:
    subprocess.run(
        ["codex", "exec", "--full-auto", prompt],
        cwd=_repo_root(), capture_output=True, text=True,
        timeout=CODEX_TIMEOUT, check=True,
    )


def _git_commit(path: str, slug: str) -> None:
    for cmd in (
        ["git", "add", path],
        ["git", "commit", "-m", f"feat: add generated scraper for {slug}"],
    ):
        proc = subprocess.run(cmd, cwd=_repo_root(), capture_output=True, text=True)
        if proc.returncode != 0:
            log.warning("git %s failed for %s: %s", cmd[1], slug, proc.stderr.strip())


def _attempt(cfg: Config, slug: str, prompt: str) -> tuple[list[dict] | None, str | None]:
    path = pathlib.Path(cfg.scrapers_dir) / f"{slug}.py"
    try:
        _invoke_codex(prompt, cfg)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "")[-500:]
        return None, f"codex invocation failed: {e}\nstderr: {stderr}"
    except (subprocess.SubprocessError, OSError) as e:
        return None, f"codex invocation failed: {e}"
    if not path.exists():
        return None, f"codex did not create {path}"
    try:
        companies = run_scraper(str(path))
    except ScraperError as e:
        return None, str(e)
    if not companies:
        return None, "self-test returned 0 companies"
    return companies, None


def _enable(conn, slug: str, source_id: int, companies: list[dict]) -> GenResult:
    new = find_new(conn, source_id, companies)
    db.insert_companies(conn, source_id, new, posted_at="baseline")
    db.update_source_after_run(conn, slug, len(companies))
    db.set_source_status(conn, slug, "active")
    return GenResult(ok=True, count=len(companies), error=None)


def generate_and_enable(cfg: Config, slug: str, name: str, url: str) -> GenResult:
    conn = db.get_conn(cfg.db_path)
    try:
        source_id = db.get_source(conn, slug)["id"]

        path_obj = pathlib.Path(cfg.scrapers_dir) / f"{slug}.py"
        if path_obj.exists():
            try:
                companies = run_scraper(str(path_obj))
            except ScraperError:
                companies = None  # broken existing file: fall through to regeneration
            else:
                if not companies:
                    db.set_source_status(conn, slug, "failed")
                    return GenResult(
                        ok=False, count=0,
                        error="existing scraper returned 0 companies — check its configuration "
                              "(e.g. API key), then /retry",
                    )
                return _enable(conn, slug, source_id, companies)

        path = str(path_obj)
        prompt = render_prompt(name, url, slug, cfg.scrapers_dir)
        companies, error = _attempt(cfg, slug, prompt)

        if companies is None:
            retry_prompt = render_prompt(
                name, url, slug, cfg.scrapers_dir,
                feedback=f"\nA previous attempt failed its self-test with this error — fix it:\n{error}",
            )
            companies, error = _attempt(cfg, slug, retry_prompt)

        if companies is None:
            db.set_source_status(conn, slug, "failed")
            return GenResult(ok=False, count=0, error=error)

        result = _enable(conn, slug, source_id, companies)
        _git_commit(path, slug)
        return result
    finally:
        conn.close()
