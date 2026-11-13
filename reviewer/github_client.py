"""Minimal GitHub REST client: fetch a PR diff, post or update the bot's comment."""
from __future__ import annotations

import requests

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, repo: str, timeout: int = 30):
        self.repo = repo
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "pr-review-agent",
            }
        )

    def get_pr_diff(self, pr_number: int) -> str:
        r = self.session.get(
            f"{API}/repos/{self.repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.text

    def upsert_comment(self, pr_number: int, body: str, marker: str) -> str:
        """Update the bot's existing comment on the PR if there is one, else create it."""
        base = f"{API}/repos/{self.repo}/issues/{pr_number}/comments"
        for page in range(1, 6):
            r = self.session.get(base, params={"per_page": 100, "page": page}, timeout=self.timeout)
            r.raise_for_status()
            comments = r.json()
            for c in comments:
                if marker in (c.get("body") or ""):
                    u = self.session.patch(c["url"], json={"body": body}, timeout=self.timeout)
                    u.raise_for_status()
                    return u.json()["html_url"]
            if len(comments) < 100:
                break
        p = self.session.post(base, json={"body": body}, timeout=self.timeout)
        p.raise_for_status()
        return p.json()["html_url"]
