"""Shared data types."""
from __future__ import annotations

from dataclasses import dataclass, field

SEVERITIES = ("critical", "high", "medium", "low")  # most to least severe


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    category: str   # which specialist agent raised it: bug / security / style
    title: str
    explanation: str
    suggestion: str = ""

    @property
    def severity_rank(self) -> int:
        return SEVERITIES.index(self.severity) if self.severity in SEVERITIES else len(SEVERITIES)


@dataclass
class ReviewResult:
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    files_reviewed: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    llm_calls: int = 0
    truncated: bool = False  # True if limits stopped part of the PR from being reviewed
