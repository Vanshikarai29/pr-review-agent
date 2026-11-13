"""Measure the reviewer on seeded bugs.

    python -m evaluation.run_eval

Prints a results table and writes evaluation/results.json. Use the numbers on your resume.
Makes roughly 3 Gemini calls per case, so the free tier is enough (it just takes a few minutes).
"""
from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from reviewer.config import Config
from reviewer.llm import GeminiClient
from reviewer.orchestrator import review_diff

from .cases import CASES

LINE_TOLERANCE = 2  # a finding within +-2 lines of the seeded bug counts as a detection


def build_new_file_diff(path: str, source: str) -> str:
    lines = source.splitlines()
    header = [
        f"diff --git a/{path} b/{path}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{path}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    return "\n".join(header + [f"+{l}" for l in lines]) + "\n"


def bug_line(source: str, needle: str) -> int:
    for i, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return i
    raise ValueError(f"{needle!r} not found in case source")


def main() -> None:
    cfg = replace(Config.from_env(), use_llm_summary=False)
    llm = GeminiClient(cfg)

    rows, detected, buggy, false_pos, clean = [], 0, 0, 0, 0
    total_calls, started = 0, time.monotonic()

    for case in CASES:
        diff = build_new_file_diff(case["path"], case["source"])
        result = review_diff(diff, llm, cfg)
        total_calls += result.llm_calls

        if case["bug_contains"]:
            buggy += 1
            target = bug_line(case["source"], case["bug_contains"])
            hit = any(
                f.file == case["path"] and abs(f.line - target) <= LINE_TOLERANCE
                for f in result.findings
            )
            detected += hit
            rows.append((case["id"], "bug", "HIT" if hit else "MISS", len(result.findings)))
        else:
            clean += 1
            fps = [f for f in result.findings if f.severity in ("critical", "high", "medium")]
            false_pos += bool(fps)
            rows.append((case["id"], "clean", "FALSE POSITIVE" if fps else "ok", len(result.findings)))
        print(f"{rows[-1][0]:<28}{rows[-1][1]:<7}{rows[-1][2]:<16}findings={rows[-1][3]}")

    elapsed = time.monotonic() - started
    summary = {
        "model": cfg.model,
        "seeded_bug_cases": buggy,
        "detected": detected,
        "detection_rate_pct": round(100 * detected / max(buggy, 1), 1),
        "clean_cases": clean,
        "clean_cases_with_false_positive": false_pos,
        "model_calls": total_calls,
        "seconds_total": round(elapsed, 1),
        "cases": [dict(zip(("id", "type", "result", "findings"), r)) for r in rows],
    }
    out = Path(__file__).with_name("results.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"\nDetected {detected}/{buggy} seeded bugs ({summary['detection_rate_pct']}%), "
        f"{false_pos}/{clean} clean files flagged, {total_calls} model calls, {elapsed:.0f}s."
    )
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
