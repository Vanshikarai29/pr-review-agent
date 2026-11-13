"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    gemini_api_key: str = ""
    # Model names change over time. Override with GEMINI_MODEL if this one is retired.
    model: str = "gemini-2.5-flash"

    # Guardrails: keep every PR review bounded in cost and time.
    max_files: int = 25            # files reviewed per PR
    max_chunk_chars: int = 24_000  # diff characters sent per LLM call
    max_chunks: int = 4            # chunks reviewed per PR
    max_llm_calls: int = 14        # hard step limit per PR
    max_findings: int = 15         # findings shown in the final comment

    # Free-tier friendliness.
    request_delay: float = 6.0     # seconds between LLM calls (free tier is ~10 requests/min)
    max_retries: int = 4
    timeout_s: int = 60

    use_llm_summary: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", cls.model),
            max_files=_int("MAX_FILES", cls.max_files),
            max_chunk_chars=_int("MAX_CHUNK_CHARS", cls.max_chunk_chars),
            max_chunks=_int("MAX_CHUNKS", cls.max_chunks),
            max_llm_calls=_int("MAX_LLM_CALLS", cls.max_llm_calls),
            max_findings=_int("MAX_FINDINGS", cls.max_findings),
            request_delay=_float("REQUEST_DELAY_SECONDS", cls.request_delay),
            max_retries=_int("MAX_RETRIES", cls.max_retries),
            timeout_s=_int("LLM_TIMEOUT_SECONDS", cls.timeout_s),
            use_llm_summary=os.getenv("USE_LLM_SUMMARY", "1") != "0",
        )
