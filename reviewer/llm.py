"""Thin wrapper around the Gemini API (google-genai SDK).

Responsibilities: JSON-only output, timeouts, retries with backoff, and a delay between
calls so the free tier's requests-per-minute limit is not exceeded.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from .config import Config

log = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the model cannot return a usable answer after all retries."""


def extract_json(text: str) -> Any:
    """Parse JSON from model output, tolerating ```json fences."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class GeminiClient:
    def __init__(self, cfg: Config):
        if not cfg.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        # Imported here so the rest of the package (and the unit tests) work without the SDK.
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=cfg.gemini_api_key,
            http_options=types.HttpOptions(timeout=cfg.timeout_s * 1000),
        )
        self._cfg = cfg
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = self._cfg.request_delay - (time.monotonic() - self._last_call)
        if self._last_call and wait > 0:
            time.sleep(wait)

    def generate_json(self, system: str, prompt: str) -> Any:
        last_err: Exception | None = None
        for attempt in range(1, self._cfg.max_retries + 1):
            self._throttle()
            try:
                resp = self._client.models.generate_content(
                    model=self._cfg.model,
                    contents=prompt,
                    config=self._types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                self._last_call = time.monotonic()
                if not resp.text:
                    raise ValueError("empty response (possibly blocked by safety filters)")
                return extract_json(resp.text)
            except Exception as e:  # network errors, 429s, bad JSON, empty output
                self._last_call = time.monotonic()
                last_err = e
                backoff = min(60, 2 ** attempt * 2)
                log.warning("LLM call failed (attempt %d/%d): %s", attempt, self._cfg.max_retries, e)
                if attempt < self._cfg.max_retries:
                    time.sleep(backoff)
        raise LLMError(f"gave up after {self._cfg.max_retries} attempts: {last_err}")
