from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _small_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_api_style: str
    llm_timeout_seconds: float
    llm_max_attempts: int

    @classmethod
    def from_env(cls) -> "Settings":
        style = os.getenv("LLM_API_STYLE", "responses").strip().lower()
        if style not in {"responses", "chat_completions"}:
            raise ValueError("LLM_API_STYLE must be responses or chat_completions")

        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", "gpt-5.6-luna").strip(),
            llm_api_style=style,
            llm_timeout_seconds=_positive_float("LLM_TIMEOUT_SECONDS", 18.0),
            llm_max_attempts=_small_int("LLM_MAX_ATTEMPTS", 2, 1, 3),
        )
