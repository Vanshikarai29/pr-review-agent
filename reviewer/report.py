"""Render a ReviewResult as a GitHub-flavoured markdown comment."""
from __future__ import annotations

from .models import SEVERITIES, ReviewResult

# Hidden marker so the bot can find and UPDATE its own comment instead of posting duplicates.
MARKER = "<!-- pr-review-agent -->"
ICONS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
GITHUB_COMMENT_LIMIT = 60_000


def render_markdown(result: ReviewResult, model: str = "gemini") -> str:
    lines = [MARKER, "## 🤖 Automated PR Review", ""]
    if result.summary:
        lines += [result.summary, ""]

    n_files = len(result.files_reviewed)
    if not result.findings:
        if result.errors and not result.files_reviewed:
            lines.append("⚠️ The review could not be completed. See notes below.")
        else:
            lines.append(f"✅ No issues found in {n_files} reviewed file(s).")
    else:
        counts = {s: sum(1 for f in result.findings if f.severity == s) for s in SEVERITIES}
        lines.append("| " + " | ".join(f"{ICONS[s]} {s}" for s in SEVERITIES) + " |")
        lines.append("|" + "---|" * len(SEVERITIES))
        lines.append("| " + " | ".join(str(counts[s]) for s in SEVERITIES) + " |")
        lines.append("")
        for f in result.findings:
            lines.append(
                f"- {ICONS.get(f.severity, '•')} **{f.severity.upper()}** · "
                f"`{f.file}:{f.line}` · _{f.category}_ — **{f.title}**"
            )
            if f.explanation:
                lines.append(f"  {f.explanation}")
            if f.suggestion:
                lines.append(f"  💡 {f.suggestion}")
        lines.append("")

    notes = []
    if result.truncated:
        notes.append("Some files were not reviewed because size or call limits were reached.")
    notes += [f"{e}" for e in result.errors]
    if notes:
        lines += ["<details><summary>Notes</summary>", ""] + [f"- {n}" for n in notes] + ["", "</details>", ""]

    lines.append(
        f"<sub>Reviewed {n_files} file(s) with {model} · {result.llm_calls} model call(s) · "
        "AI-generated, so verify before acting.</sub>"
    )
    body = "\n".join(lines)
    if len(body) > GITHUB_COMMENT_LIMIT:
        body = body[:GITHUB_COMMENT_LIMIT] + "\n\n_…truncated_"
    return body
