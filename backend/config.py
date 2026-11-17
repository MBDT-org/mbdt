"""Application configuration loaded from environment / .env file.

External traffic goes to one OpenAI-compatible gateway, selected with
``MBDT_PROVIDER``:
  - ``requesty``   (default) https://router.requesty.ai/v1
  - ``openrouter`` https://openrouter.ai/api/v1

Both gateways expose chat completions (including vision), speech synthesis and
transcription. Model ids are gateway-specific, so the defaults differ; set
``MBDT_LLM_MODEL`` / ``MBDT_OCR_MODEL`` / ``MBDT_STT_MODEL`` / ``MBDT_TTS_MODEL``
to override them. If only ``MBDT_OPENROUTER_API_KEY`` is set, OpenRouter is
selected automatically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _env(key: str, default: str) -> str:
    # An empty value in .env means "use the default", not "empty string".
    value = os.getenv(key)
    return value if value else default


def _env_float(key: str, default: float | None) -> float | None:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Gateway-specific defaults. Model ids are not portable between gateways.
_PROVIDER_DEFAULTS: dict[str, dict[str, object]] = {
    "requesty": {
        "base_url": "https://router.requesty.ai/v1",
        "llm": "fireworks/deepseek-v4.1-flash-1017",
        "ocr": "fireworks/deepseek-v4.1-flash-1017",
        "stt": "openai/whisper-1",
        "tts": "deepinfra/ResembleAI/chatterbox-turbo",
        "voice": "default",
        "speed": 0.9,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "llm": "deepseek/deepseek-v4.1-flash-1017",
        # The same model accepts image input, so one id covers text and OCR.
        "ocr": "deepseek/deepseek-v4.1-flash-1017",
        "stt": "openai/whisper-large-v3",
        "tts": "mistralai/voxtral-mini-tts-2603",
        "voice": "en_paul_neutral",
        # Not every TTS model supports speed; omit it unless the user opts in.
        "speed": None,
    },
}


def _pick_provider() -> str:
    raw = _env("MBDT_PROVIDER", "").strip().lower()
    if raw:
        if raw not in _PROVIDER_DEFAULTS:
            raise ValueError(
                f"MBDT_PROVIDER must be 'requesty' or 'openrouter', got {raw!r}"
            )
        return raw
    # No explicit choice: prefer Requesty unless only an OpenRouter key exists.
    if _env("MBDT_OPENROUTER_API_KEY", "").strip() and not _env(
        "MBDT_REQUESTY_API_KEY", ""
    ).strip():
        return "openrouter"
    return "requesty"


_PROVIDER = _pick_provider()
_DEFAULTS = _PROVIDER_DEFAULTS[_PROVIDER]


def _env_allow_empty(key: str, default: str) -> str:
    """Like _env, but an explicit empty value stays empty (used to disable text)."""
    value = os.getenv(key)
    return default if value is None else value


@dataclass(frozen=True)
class Settings:
    # --- Gateway selection ---
    provider: str = _PROVIDER
    requesty_base_url: str = field(
        default_factory=lambda: _env(
            "MBDT_REQUESTY_BASE_URL", str(_PROVIDER_DEFAULTS["requesty"]["base_url"])
        )
    )
    requesty_api_key: str = field(
        default_factory=lambda: _env("MBDT_REQUESTY_API_KEY", "")
    )
    openrouter_base_url: str = field(
        default_factory=lambda: _env(
            "MBDT_OPENROUTER_BASE_URL", str(_PROVIDER_DEFAULTS["openrouter"]["base_url"])
        )
    )
    openrouter_api_key: str = field(
        default_factory=lambda: _env("MBDT_OPENROUTER_API_KEY", "")
    )

    # Model ids as known by the selected gateway.
    llm_model: str = field(
        default_factory=lambda: _env("MBDT_LLM_MODEL", str(_DEFAULTS["llm"]))
    )
    # Vision model for handwriting OCR (Exercise 3); must accept image input.
    ocr_model: str = field(
        default_factory=lambda: _env("MBDT_OCR_MODEL", str(_DEFAULTS["ocr"]))
    )
    # whisper models report avg_logprob, which feeds verdict confidence.
    stt_model: str = field(
        default_factory=lambda: _env("MBDT_STT_MODEL", str(_DEFAULTS["stt"]))
    )

    # --- TTS voice configuration (which speech model + how it speaks) ---
    tts_model: str = field(
        default_factory=lambda: _env("MBDT_TTS_MODEL", str(_DEFAULTS["tts"]))
    )
    # Voice id understood by the TTS provider ("default" = chatterbox built-in;
    # OpenAI models use alloy/nova/...). Unknown ids fall back to default.
    tts_voice: str = field(
        default_factory=lambda: _env("MBDT_TTS_VOICE", str(_DEFAULTS["voice"]))
    )
    # Playback speed, 0.25-4.0 (unset = provider default).
    tts_speed: float | None = field(
        default_factory=lambda: _env_float("MBDT_TTS_SPEED", _DEFAULTS["speed"])  # type: ignore[arg-type]
    )
    # Steering prompt for voice models that support it (gpt-4o-mini-tts);
    # ignored by others. Empty string disables.
    tts_instructions: str = field(
        default_factory=lambda: _env_allow_empty(
            "MBDT_TTS_INSTRUCTIONS",
            "Speak clearly and warmly at a calm, unhurried pace, "
            "like a friendly teacher helping a young child learn to read.",
        )
    )
    # Audio container for the default gateway: mp3 | opus | aac | flac | wav | pcm.
    # OpenRouter currently accepts mp3 or pcm.
    tts_format: str = field(default_factory=lambda: _env("MBDT_TTS_FORMAT", "mp3"))

    # --- Local storage / runtime ---
    db_path: str = field(default_factory=lambda: _env("MBDT_DB_PATH", str(Path(__file__).resolve().parent / "mbdt.db")))
    cors_origins: str = field(
        default_factory=lambda: _env("MBDT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )
    # Initial admin password for demo tools (skip / reset). Seeds the DB hash on
    # first use; after that the stored hash wins until changed via the API.
    admin_password: str = field(default_factory=lambda: _env("MBDT_ADMIN_PASSWORD", "admin"))

    @property
    def api_key(self) -> str:
        return self.openrouter_api_key if self.provider == "openrouter" else self.requesty_api_key

    @property
    def base_url(self) -> str:
        return self.openrouter_base_url if self.provider == "openrouter" else self.requesty_base_url

    @property
    def provider_label(self) -> str:
        return "OpenRouter" if self.provider == "openrouter" else "Requesty"

    @property
    def api_key_env(self) -> str:
        return "MBDT_OPENROUTER_API_KEY" if self.provider == "openrouter" else "MBDT_REQUESTY_API_KEY"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def has_api_key() -> bool:
    return bool(settings.api_key)
