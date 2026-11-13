"""Coordinates the review: parse diff -> chunk -> run agents -> validate -> merge -> summarize."""
from __future__ import annotations

import logging

from .agents import AGENTS, LLM, basic_summary, run_agent, summarize
from .config import Config
from .diff_utils import chunk_files, parse_diff, should_review, split_file
from .llm import LLMError
from .models import Finding, ReviewResult

log = logging.getLogger(__name__)


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Merge duplicates: same file+line+title, or same file+line+category (keep the worst)."""
    best: dict[tuple, Finding] = {}
    for f in sorted(findings, key=lambda x: x.severity_rank):
        keys = [(f.file, f.line, f.title.lower()), (f.file, f.line, f.category)]
        if any(k in best for k in keys):
            continue
        for k in keys:
            best[k] = f
    unique = {id(f): f for f in best.values()}.values()
    return sorted(unique, key=lambda f: (f.severity_rank, f.file, f.line))


def review_diff(diff_text: str, llm: LLM, cfg: Config) -> ReviewResult:
    result = ReviewResult()
    files = parse_diff(diff_text)

    reviewable = [f for f in files if should_review(f)]
    result.files_skipped = [f.path for f in files if not should_review(f)]
    if len(reviewable) > cfg.max_files:
        result.files_skipped += [f.path for f in reviewable[cfg.max_files:]]
        reviewable = reviewable[: cfg.max_files]
        result.truncated = True

    pieces = [p for f in reviewable for p in split_file(f, cfg.max_chunk_chars)]
    chunks = chunk_files(pieces, cfg.max_chunk_chars)
    if len(chunks) > cfg.max_chunks:
        skipped_paths = {fd.path for chunk in chunks[cfg.max_chunks:] for fd in chunk}
        result.files_skipped += sorted(skipped_paths)
        chunks = chunks[: cfg.max_chunks]
        result.truncated = True

    found: list[Finding] = []
    for chunk in chunks:
        for spec in AGENTS:
            if result.llm_calls >= cfg.max_llm_calls:  # hard step limit
                result.truncated = True
                break
            result.llm_calls += 1
            try:
                found.extend(run_agent(llm, spec, chunk))
            except LLMError as e:  # one failing agent must not sink the whole review
                msg = f"{spec.name} agent failed: {e}"
                log.error(msg)
                result.errors.append(msg)
        result.files_reviewed += [fd.path for fd in chunk if fd.path not in result.files_reviewed]

    findings = dedupe(found)[: cfg.max_findings]
    result.findings = findings

    if findings and cfg.use_llm_summary and result.llm_calls < cfg.max_llm_calls:
        result.llm_calls += 1
        result.summary = summarize(llm, findings)
    else:
        result.summary = basic_summary(findings)
    return result
