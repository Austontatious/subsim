from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class CodexStandardsConfig:
    """Small typed config surface for cross-repo LLM/eval plumbing."""

    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_retries: int
    llm_temperature: float
    llm_max_tokens: int
    tracing_enabled: bool
    tracing_backend: str
    tracing_jsonl_path: str
    eval_pass_threshold: float
    eval_dataset_glob: str
    prompt_root: str

    @classmethod
    def from_env(cls, *, prefix: str = "CODEX_") -> "CodexStandardsConfig":
        return cls(
            llm_base_url=os.getenv(f"{prefix}LLM_BASE_URL", "https://api.openai.com/v1").strip(),
            llm_api_key=os.getenv(f"{prefix}LLM_API_KEY", "").strip(),
            llm_model=os.getenv(f"{prefix}LLM_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
            llm_timeout_seconds=_env_float(f"{prefix}LLM_TIMEOUT_SECONDS", 30.0),
            llm_max_retries=_env_int(f"{prefix}LLM_MAX_RETRIES", 2),
            llm_temperature=_env_float(f"{prefix}LLM_TEMPERATURE", 0.2),
            llm_max_tokens=_env_int(f"{prefix}LLM_MAX_TOKENS", 800),
            tracing_enabled=_env_bool(f"{prefix}TRACING_ENABLED", False),
            tracing_backend=os.getenv(f"{prefix}TRACING_BACKEND", "noop").strip() or "noop",
            tracing_jsonl_path=os.getenv(
                f"{prefix}TRACING_JSONL_PATH",
                ".codex-traces/llm-trace.jsonl",
            ).strip(),
            eval_pass_threshold=_env_float(f"{prefix}EVAL_PASS_THRESHOLD", 1.0),
            eval_dataset_glob=os.getenv(f"{prefix}EVAL_DATASET_GLOB", "evals/cases/**/*.json").strip()
            or "evals/cases/**/*.json",
            prompt_root=os.getenv(f"{prefix}PROMPT_ROOT", "prompts").strip() or "prompts",
        )
