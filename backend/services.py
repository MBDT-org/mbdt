"""Unified gateway service clients (raw httpx).

All external requests (LLM, vision/OCR, TTS, STT) are routed through one
OpenAI-compatible gateway selected by `MBDT_PROVIDER`: Requesty
(https://router.requesty.ai/v1) or OpenRouter (https://openrouter.ai/api/v1).
Calls are made directly with httpx for granular control over headers, timeouts,
retries and error mapping. Nothing is streamed.

Structured output: `chat_json` prefers strict `json_schema` mode (decoding-level
constraint) when a schema is supplied, falling back to `json_object` mode when
the model or gateway rejects it.

See https://docs.requesty.ai and https://openrouter.ai/docs.
"""

from __future__ import annotations

import base64
import functools
import json
import logging
import math
import mimetypes
import random
import re
import time
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("mbdt.services")

# Transient statuses worth retrying. Both gateways honour Retry-After on 429;
# 5xx are usually transient upstream provider failures.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


# Map upstream HTTP statuses to stable, frontend-facing error codes.
_STATUS_CODES = {
    401: "auth_failed",
    402: "insufficient_credits",
    403: "model_not_approved",
    404: "model_not_found",
    429: "rate_limited",
}


def _code_for_status(status_code: int, detail: str) -> str:
    """Map an upstream HTTP status (and its detail text) to a stable code.

    Requesty answers a bad/invalid API key with 403 "Invalid authorization
    token" rather than 401, so a 403 whose detail mentions the token/key is an
    auth failure, not a model-approval problem. OpenRouter uses 401/402.
    """
    if status_code == 403 and any(k in detail.lower() for k in ("token", "api key", "apikey")):
        return "auth_failed"
    lower = detail.lower()
    # OpenRouter uses 404 when *no provider allowed for your account* can serve
    # the model, and 403 for regional blocks. Neither means "wrong model id".
    if "no allowed providers" in lower or "not available in your region" in lower:
        return "model_unavailable"
    return _STATUS_CODES.get(status_code, "upstream_error")


class ServiceError(RuntimeError):
    """Raised when an external gateway call fails."""

    def __init__(self, message: str, *, code: str | None = None, model: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.model = model


class _ChatHTTPError(ServiceError):
    """Chat call returned a non-200 status (carries the status code)."""

    def __init__(self, status_code: int, detail: str, *, model: str | None = None) -> None:
        super().__init__(detail, code=_code_for_status(status_code, detail), model=model)
        self.status_code = status_code


_client: httpx.Client | None = None
_client_provider: str | None = None


def client() -> httpx.Client:
    """Lazily build a singleton httpx client for the configured gateway."""
    global _client, _client_provider
    if _client is None or _client_provider != settings.provider:
        if _client is not None:
            _client.close()
            _client = None
        if not settings.api_key:
            raise ServiceError(
                f"{settings.api_key_env} is not set. Add it to backend/.env "
                "(see .env.example).",
                code="no_api_key",
            )
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "HTTP-Referer": "https://mbdt.local",
            "X-Title": "MBDT",
        }
        if settings.provider == "openrouter":
            headers["X-OpenRouter-Title"] = "MBDT"
        _client = httpx.Client(
            base_url=settings.base_url,
            headers=headers,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0),
        )
        _client_provider = settings.provider
    return _client


def reset_client() -> None:
    """Used by tests / config reloads."""
    global _client, _client_provider
    if _client is not None:
        _client.close()
    _client = None
    _client_provider = None


# ---------------------------------------------------------------------------
# Request plumbing
# ---------------------------------------------------------------------------


def _retry_after(resp: httpx.Response) -> float | None:
    """Parse a numeric Retry-After header (capped) if present."""
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(float(value), 30.0)
    except ValueError:
        return None  # HTTP-date form; fall through to backoff


def _error_detail(resp: httpx.Response) -> str:
    """Extract the gateway's {"error": {"origin"|"code", "message"}} shape."""
    try:
        body = resp.json()
        err = body.get("error") or {}
        if isinstance(err, str):
            return f"{resp.status_code}: {err[:200]}"
        origin = err.get("origin") or err.get("code") or settings.provider_label
        message = err.get("message") or str(resp.text[:200])
        return f"{resp.status_code} ({origin}): {message}"
    except ValueError:
        return f"{resp.status_code}: {str(resp.text[:200])}"


def _request(
    method: str,
    path: str,
    *,
    read_timeout: float,
    max_retries: int = 2,
    **kwargs: Any,
) -> httpx.Response:
    """One non-streaming request with retries on transient failures.

    Retries network errors and 408/425/429/5xx statuses, honouring Retry-After
    when present and exponential backoff with jitter otherwise. Returns the
    final response (retryable or not); the caller maps errors to ServiceError.
    """
    timeout = httpx.Timeout(connect=10.0, read=read_timeout, write=30.0, pool=10.0)
    backoff = 1.0
    for attempt in range(max_retries + 1):
        try:
            resp = client().request(method, path, timeout=timeout, **kwargs)
        except httpx.HTTPError as exc:
            if attempt >= max_retries:
                raise ServiceError(f"{settings.provider_label} request failed ({path}): {exc}", code="network_error") from exc
            logger.warning(
                "%s %s network error (attempt %d/%d): %s",
                settings.provider_label, path, attempt + 1, max_retries + 1, exc,
            )
        else:
            if resp.status_code not in _RETRYABLE_STATUS or attempt >= max_retries:
                return resp
            logger.warning(
                "%s %s returned %d (attempt %d/%d), retrying",
                settings.provider_label, path, resp.status_code, attempt + 1, max_retries + 1,
            )
            retry_after = _retry_after(resp)
            if retry_after is not None:
                time.sleep(retry_after)
                continue
        time.sleep(backoff + random.uniform(0.0, 0.5))
        backoff *= 2.0
    raise ServiceError(f"{settings.provider_label} request failed ({path}): exhausted retries", code="network_error")


# ---------------------------------------------------------------------------
# LLM (text + structured)
# ---------------------------------------------------------------------------


def chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
    read_timeout: float = 120.0,
    reasoning_effort: str | None = None,
    fallback_reasoning: bool = True,
) -> str:
    """Send a chat completion and return the assistant text (non-streaming).

    `reasoning_effort` (e.g. "none", "low", "high") is passed through to
    reasoning-capable models; leave it None for the provider default.
    `fallback_reasoning=False` stops the reasoning_content recovery, which
    matters for short deterministic answers (OCR) where chain-of-thought text
    must never be mistaken for the answer.
    """
    payload: dict[str, Any] = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if response_format is not None:
        payload["response_format"] = response_format
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    resp = _request("POST", "/chat/completions", json=payload, read_timeout=read_timeout)
    if resp.status_code != 200:
        detail = _error_detail(resp)
        logger.error("LLM chat failed (model=%s): %s", payload["model"], detail)
        raise _ChatHTTPError(
            resp.status_code,
            f"LLM chat failed (model={payload['model']}, {detail})",
            model=payload["model"],
        )
    data = resp.json()
    usage = data.get("usage") or {}
    logger.debug(
        "LLM chat ok (model=%s, cost=%.6f, tokens=%s)",
        payload["model"], usage.get("cost", 0.0), usage.get("total_tokens"),
    )
    choices = data.get("choices") or []
    if not choices:
        raise ServiceError(f"LLM chat returned no choices (model={payload['model']})", code="empty_response")
    choice = choices[0]
    message = choice.get("message") or {}
    content = (message.get("content") or "").strip()
    finish_reason = choice.get("finish_reason")
    if finish_reason == "length":
        raise ServiceError(
            f"LLM response truncated (finish_reason=length, model={payload['model']}); "
            "increase max_tokens",
            code="length_truncated",
        )
    if not content and fallback_reasoning:
        # Some reasoning models leave `content` empty and expose text via
        # `reasoning_content`; recover before failing.
        content = (message.get("reasoning_content") or "").strip()
    return content


def chat_json(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    schema: dict[str, Any] | None = None,
    schema_name: str = "Response",
) -> dict[str, Any]:
    """Chat expecting a JSON object response.

    When `schema` is supplied, requests strict `json_schema` structured output
    (the model is constrained at the decoding level to emit schema-valid JSON).
    Falls back to `json_object` mode if the gateway/model rejects the schema
    with HTTP 400. Parse errors still fall back to best-effort extraction.
    """
    used_model = model or settings.llm_model
    response_format: dict[str, Any] | None = None
    if schema is not None:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        }
    else:
        response_format = {"type": "json_object"}

    try:
        raw = chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
    except _ChatHTTPError as exc:
        if schema is not None and exc.status_code == 400:
            logger.warning(
                "json_schema rejected (model=%s); retrying with json_object", used_model
            )
            raw = chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        else:
            raise
    return _parse_json_object(raw, model=used_model)


def _parse_json_object(text: str, *, model: str) -> dict[str, Any]:
    """Parse a JSON object from raw model text (fence/prose tolerant)."""
    if text:
        candidate = _strip_code_fence(text)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        block = _first_json_object(candidate)
        if block is not None:
            try:
                parsed = json.loads(block)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as exc:
                logger.error("Model returned malformed JSON (model=%s)", model)
                raise ServiceError(f"Model returned malformed JSON: {exc}", code="bad_response") from exc
    logger.error(
        "Could not parse JSON from model response (model=%s): %s", model, text[:200]
    )
    raise ServiceError(f"Could not parse JSON from model response: {text[:200]}", code="bad_response")


def _strip_code_fence(text: str) -> str:
    """Remove a ```/```json code fence wrapping the whole payload."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def _first_json_object(text: str) -> str | None:
    """Return the first balanced top-level {...} block in `text`, if any."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


# ---------------------------------------------------------------------------
# Vision / OCR
# ---------------------------------------------------------------------------


_OCR_SENTINEL = "-"
# Refusals models sometimes emit instead of the sentinel.
_OCR_EMPTY_WORDS = frozenset({
    "none", "nil", "null", "nothing", "unknown", "illegible", "unreadable", "na",
})

_OCR_PROMPT = (
    "Transcribe the single handwritten or printed English word in this image. "
    "Reply with that word in lowercase only — no punctuation, no explanation. "
    f"If there is no clearly legible single word, reply with the single character {_OCR_SENTINEL}"
)


def _clean_ocr_text(raw: str) -> str:
    """Reduce a model reply to one plausible lowercase word.

    Vision models — especially reasoning ones — like to wrap the answer in
    quotes, punctuation or a sentence. The exercise asks for exactly one word,
    so: take the first line, keep letters/apostrophes/hyphens, and return the
    first token. The sentinel means "nothing legible" and becomes "".
    """
    text = (raw or "").strip()
    if not text:
        return ""
    # Drop markdown fences / leading labels.
    text = text.splitlines()[0]
    text = text.strip().strip("`*_\"' ")
    if text.rstrip(".") == _OCR_SENTINEL:
        return ""
    # Strip conversational lead-ins ("The word is: …", "Answer — …").
    text = re.sub(
        r"^(?:the\s+)?(?:word|answer|text|it)\s+(?:is|was|says?|reads?)?\s*[:\-\u2013]?\s*",
        "", text, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^A-Za-z'\- ]", " ", text).strip().lower()
    tokens = [t for t in cleaned.split() if t.strip("'-")]
    # A leading article is never the answer when more words follow.
    while len(tokens) > 1 and tokens[0] in {"a", "an", "the"}:
        tokens.pop(0)
    if not tokens:
        return ""
    word = tokens[0].strip("'-")
    if word in _OCR_EMPTY_WORDS:
        return ""
    return word[:32]


def ocr_from_image_data_url(data_url: str, *, prompt: str | None = None) -> str:
    """Run vision OCR on an image passed as a `data:` URL using the OCR model.

    Reasoning is switched off for this call: the answer is a single word, and
    chain-of-thought text must never leak into the learner's spelling answer.
    A sentinel prompt lets the model say "nothing legible" explicitly, which is
    surfaced to the caller as an empty string rather than a wrong answer.
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or _OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    try:
        raw = chat(
            messages,
            model=settings.ocr_model,
            temperature=0.0,
            max_tokens=16,
            read_timeout=60.0,
            reasoning_effort="none",
            fallback_reasoning=False,
        )
    except _ChatHTTPError as exc:
        # Not every vision model accepts `reasoning_effort`; retry plainly.
        if exc.status_code != 400:
            raise
        logger.info("OCR rejected reasoning_effort (model=%s); retrying without it", settings.ocr_model)
        raw = chat(
            messages,
            model=settings.ocr_model,
            temperature=0.0,
            max_tokens=16,
            read_timeout=60.0,
            fallback_reasoning=False,
        )
    return _clean_ocr_text(raw)


def image_to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    """Encode raw image bytes into a `data:` URL suitable for vision endpoints."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


def synthesize_speech(
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
    response_format: str | None = None,
    speed: float | None = None,
    instructions: str | None = None,
) -> bytes:
    """Synthesize speech audio bytes for a short string (single word or phrase).

    Voice configuration (voice id, playback speed, steering instructions,
    container format) defaults to the TTS settings; explicit args override.
    `instructions` is honoured by gpt-4o-mini-tts and ignored by other models.
    """
    return _synthesize_cached(
        settings.provider,
        text,
        voice or settings.tts_voice,
        model or settings.tts_model,
        response_format or settings.tts_format,
        speed if speed is not None else settings.tts_speed,
        instructions if instructions is not None else settings.tts_instructions,
    )


# In-process cache, restart clears; disk cache if it ever matters
@functools.lru_cache(maxsize=512)
def _synthesize_cached(
    provider: str,  # part of the cache key: audio is gateway/model specific
    text: str,
    voice: str,
    model: str,
    response_format: str,
    speed: float | None,
    instructions: str,
) -> bytes:
    payload: dict[str, Any] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": response_format,
    }
    if speed is not None:
        payload["speed"] = speed
    if instructions:
        payload["instructions"] = instructions
    resp = _request("POST", "/audio/speech", json=payload, read_timeout=60.0)
    if resp.status_code != 200:
        detail = _error_detail(resp)
        logger.error("TTS failed (model=%s): %s", model, detail)
        raise ServiceError(
            f"TTS failed (model={model}, {detail})",
            code=_code_for_status(resp.status_code, detail),
            model=model,
        )
    return resp.content


# ---------------------------------------------------------------------------
# STT
# ---------------------------------------------------------------------------


def _is_no_speech(segments: list[dict]) -> bool:
    """True when every reported segment looks like silence.

    Whisper reports `no_speech_prob` alongside `avg_logprob`. On a silent or
    failed microphone clip the model still emits text (usually "you" or
    "thank you"), so the probability is the only reliable signal. Models that
    do not return segments, or do not report the field, are treated as speech.
    """
    probs = [
        float(seg["no_speech_prob"])
        for seg in segments
        if seg.get("no_speech_prob") is not None
    ]
    return bool(probs) and min(probs) > 0.8


def transcribe(
    audio_bytes: bytes,
    *,
    filename: str = "audio.webm",
    model: str | None = None,
    language: str = "en",
) -> tuple[str, float | None]:
    """Transcribe audio bytes; return (text, confidence).

    Requests `verbose_json` so segment `avg_logprob` values come back when the
    model provides them. Whisper models report them on both gateways; the
    gpt-4o-transcribe family and mistral voxtral may return text without
    logprobs (some gateways expose a top-level `confidence` instead). Confidence is the geometric-mean per-token probability,
    `exp(mean(avg_logprob))`, in [0,1] — e.g. -0.35 nats -> 0.70. It is None
    when the model reports no logprobs, meaning "no signal" rather than "high
    confidence". Some models reject verbose_json entirely, in which case we
    retry with the default response format (also None).
    """
    stt_model = model or settings.stt_model
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    files = {"file": (filename, audio_bytes, mime)}
    data: dict[str, str] = {
        "model": stt_model,
        "language": language,
        "response_format": "verbose_json",
    }
    resp = _request(
        "POST", "/audio/transcriptions", data=data, files=files, read_timeout=60.0
    )
    if resp.status_code == 400:
        logger.warning(
            "STT verbose_json rejected (model=%s); retrying default", stt_model
        )
        data.pop("response_format")
        resp = _request(
            "POST", "/audio/transcriptions", data=data, files=files, read_timeout=60.0
        )
    if resp.status_code != 200:
        detail = _error_detail(resp)
        logger.error("STT failed (model=%s): %s", stt_model, detail)
        raise ServiceError(
            f"STT failed (model={stt_model}, {detail})",
            code=_code_for_status(resp.status_code, detail),
            model=stt_model,
        )

    body = resp.json()
    segments = body.get("segments") or []
    if _is_no_speech(segments):
        # Whisper hallucinates short words ("you", "thank you") on silence.
        # An empty transcript routes to the soft "didn't catch that" verdict
        # instead of a confident failure that penalises the learner's word.
        logger.debug("STT model %s heard no speech (no_speech_prob high)", stt_model)
        return "", None
    text = (body.get("text") or "").strip()
    logprobs = [
        float(seg["avg_logprob"])
        for seg in segments
        if seg.get("avg_logprob") is not None
    ]
    confidence: float | None = None
    if logprobs:
        confidence = math.exp(sum(logprobs) / len(logprobs))
    elif isinstance(body.get("confidence"), (int, float)):
        # Some gateways score the whole transcript instead of per-token logprobs.
        confidence = max(0.0, min(1.0, float(body["confidence"])))
    else:
        logger.debug(
            "STT model %s returned no avg_logprob; verdict confidence will use "
            "the similarity margin only",
            stt_model,
        )
    return text, confidence
