"""Command-line entry point.

In GitHub Actions:  python -m reviewer.main
Locally on a diff:  python -m reviewer.main --diff-file my.diff --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .config import Config
from .orchestrator import review_diff
from .report import MARKER, render_markdown

log = logging.getLogger("reviewer")


def resolve_pr_number(arg: int | None) -> int | None:
    if arg:
        return arg
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if event_path and os.path.exists(event_path):
        with open(event_path, encoding="utf-8") as f:
            event = json.load(f)
        return (event.get("pull_request") or {}).get("number") or event.get("number")
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Review a pull request with Gemini agents.")
    p.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"), help="owner/name")
    p.add_argument("--pr", type=int, help="pull request number (auto-detected in Actions)")
    p.add_argument("--diff-file", help="review a local unified diff instead of calling GitHub")
    p.add_argument("--dry-run", action="store_true", help="print the review, do not post it")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    cfg = Config.from_env()

    if not cfg.gemini_api_key:
        # Pull requests from forks do not receive repository secrets. Skip quietly.
        log.warning("GEMINI_API_KEY is not set; skipping review.")
        return 0

    local = bool(args.diff_file)
    if local:
        with open(args.diff_file, encoding="utf-8") as f:
            diff_text = f.read()
        gh = None
        pr_number = None
    else:
        token = os.getenv("GITHUB_TOKEN")
        pr_number = resolve_pr_number(args.pr)
        if not (token and args.repo and pr_number):
            log.error("Need GITHUB_TOKEN, --repo (or GITHUB_REPOSITORY) and --pr, or use --diff-file.")
            return 2
        from .github_client import GitHubClient

        gh = GitHubClient(token, args.repo)
        diff_text = gh.get_pr_diff(pr_number)

    from .llm import GeminiClient

    result = review_diff(diff_text, GeminiClient(cfg), cfg)
    body = render_markdown(result, cfg.model)

    if args.dry_run or local:
        print(body)
        return 0

    url = gh.upsert_comment(pr_number, body, MARKER)  # type: ignore[union-attr]
    log.info("Posted review: %s", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
