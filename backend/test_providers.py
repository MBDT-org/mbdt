"""Gateway-provider self-checks (offline).

Covers the OpenRouter path without a live key:
  - provider selection and per-gateway defaults (fresh subprocesses)
  - explicit provider with a missing key fails with a clear message
  - request/response handling for chat, structured JSON, TTS and STT against a
    mocked OpenRouter transport
  - the real client is built with the OpenRouter base URL and headers
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import subprocess
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent
REPO = BACKEND.parent

BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith("MBDT_")}
# backend/.env exists on a developer machine; blank values stop load_dotenv
# from filling the real keys into these subprocesses.
for _key in (
    "MBDT_PROVIDER", "MBDT_REQUESTY_API_KEY", "MBDT_REQUESTY_BASE_URL",
    "MBDT_OPENROUTER_API_KEY", "MBDT_OPENROUTER_BASE_URL", "MBDT_LLM_MODEL",
    "MBDT_OCR_MODEL", "MBDT_STT_MODEL", "MBDT_TTS_MODEL", "MBDT_TTS_VOICE",
    "MBDT_TTS_SPEED", "MBDT_TTS_INSTRUCTIONS", "MBDT_TTS_FORMAT", "MBDT_DB_PATH",
    "MBDT_CORS_ORIGINS", "MBDT_ADMIN_PASSWORD",
):
    BASE_ENV[_key] = ""


def run_config(extra_env: dict[str, str]) -> dict:
    """Import config in a fresh process and return selected settings."""
    env = {**BASE_ENV, **extra_env}
    code = (
        "import json; from config import settings, has_api_key; "
        "print(json.dumps({'provider': settings.provider, "
        "'base_url': settings.base_url, 'api_key_env': settings.api_key_env, "
        "'key': has_api_key(), 'llm': settings.llm_model, "
        "'ocr': settings.ocr_model, 'stt': settings.stt_model, "
        "'tts': settings.tts_model, 'voice': settings.tts_voice, "
        "'speed': settings.tts_speed}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_openrouter_is_selected_from_its_key_alone():
    cfg = run_config({"MBDT_OPENROUTER_API_KEY": "sk-or-v1-test"})
    assert cfg["provider"] == "openrouter", cfg
    assert cfg["base_url"] == "https://openrouter.ai/api/v1", cfg
    assert cfg["api_key_env"] == "MBDT_OPENROUTER_API_KEY", cfg
    assert cfg["key"] is True, cfg
    assert cfg["llm"] == "deepseek/deepseek-v4.1-flash-1017", cfg
    assert cfg["ocr"] == "deepseek/deepseek-v4.1-flash-1017", cfg
    assert cfg["stt"] == "openai/whisper-large-v3", cfg
    assert cfg["tts"] == "mistralai/voxtral-mini-tts-2603", cfg
    assert cfg["voice"] == "en_paul_neutral", cfg
    assert cfg["speed"] is None, cfg


def test_requesty_stays_the_default_with_both_keys():
    cfg = run_config({
        "MBDT_REQUESTY_API_KEY": "sk-test",
        "MBDT_OPENROUTER_API_KEY": "sk-or-v1-test",
    })
    assert cfg["provider"] == "requesty", cfg
    assert cfg["base_url"] == "https://router.requesty.ai/v1", cfg
    assert cfg["llm"] == "fireworks/deepseek-v4.1-flash-1017", cfg
    assert cfg["stt"] == "openai/whisper-1", cfg


def test_explicit_provider_and_model_override():
    cfg = run_config({
        "MBDT_PROVIDER": "openrouter",
        "MBDT_REQUESTY_API_KEY": "sk-test",
        "MBDT_LLM_MODEL": "openai/gpt-5.2",
        "MBDT_TTS_SPEED": "1.1",
    })
    assert cfg["provider"] == "openrouter", cfg
    assert cfg["llm"] == "openai/gpt-5.2", cfg
    assert cfg["speed"] == 1.1, cfg


def test_missing_selected_key_is_reported_clearly():
    env = {**BASE_ENV, "MBDT_PROVIDER": "openrouter", "MBDT_REQUESTY_API_KEY": "sk-test"}
    code = (
        "import services\n"
        "from services import ServiceError\n"
        "try:\n"
        "    services.client()\n"
        "except ServiceError as exc:\n"
        "    print(exc.code)\n"
        "    print(str(exc))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "no_api_key" in proc.stdout, proc.stdout
    assert "MBDT_OPENROUTER_API_KEY" in proc.stdout, proc.stdout


def test_invalid_provider_is_rejected():
    env = {**BASE_ENV, "MBDT_PROVIDER": "somewhere-else"}
    proc = subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "MBDT_PROVIDER must be 'requesty' or 'openrouter'" in proc.stderr, proc.stderr


def test_gateway_availability_errors_are_classified():
    import services

    # OpenRouter returns 404 when provider settings block a model, and 403 for
    # regional restrictions; neither should read as "model id does not exist".
    assert services._code_for_status(
        404, "No allowed providers are available for the selected model"
    ) == "model_unavailable"
    assert services._code_for_status(
        403, "This model is not available in your region."
    ) == "model_unavailable"
    assert services._code_for_status(404, "model not found") == "model_not_found"
    assert services._code_for_status(403, "Invalid authorization token") == "auth_failed"


# ---------------------------------------------------------------------------
# Mocked OpenRouter transport (no live key needed)
# ---------------------------------------------------------------------------


def test_openrouter_http_handling():
    import config
    import services

    # The mocked 400 fallback intentionally logs an error; keep test output tidy.
    log = logging.getLogger("mbdt.services")
    previous_level = log.level
    log.setLevel(logging.CRITICAL)

    or_settings = dataclasses.replace(
        config.settings,
        provider="openrouter",
        openrouter_api_key="test-or-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        llm_model="deepseek/deepseek-v4.1-flash-1017",
        ocr_model="deepseek/deepseek-v4.1-flash-1017",
        stt_model="openai/whisper-large-v3",
        tts_model="mistralai/voxtral-mini-tts-2603",
        tts_voice="en_paul_neutral",
        tts_speed=None,
    )
    services.settings = or_settings
    services.reset_client()
    services._synthesize_cached.cache_clear()

    # The real client builder must point at OpenRouter and send its headers.
    client = services.client()
    assert str(client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"
    assert client.headers["authorization"] == "Bearer test-or-key"
    assert client.headers["x-openrouter-title"] == "MBDT"
    services.reset_client()

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            fmt = (body.get("response_format") or {}).get("type")
            if fmt == "json_schema":
                return httpx.Response(
                    400, json={"error": {"code": 400, "message": "schema unsupported"}}
                )
            if fmt == "json_object":
                return httpx.Response(200, json={
                    "choices": [{"finish_reason": "stop", "message": {
                        "role": "assistant", "content": '{"answer": "ok"}'}}],
                })
            return httpx.Response(200, json={
                "choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": "hello"}}],
            })
        if request.url.path.endswith("/audio/speech"):
            return httpx.Response(
                200, content=b"ID3-fake-mp3", headers={"content-type": "audio/mpeg"}
            )
        if request.url.path.endswith("/audio/transcriptions"):
            body = request.content
            if b"audio.mp3" in body:
                # No segments, but the gateway scored the whole transcript.
                return httpx.Response(200, json={"text": "dog", "confidence": 0.9})
            return httpx.Response(200, json={
                "text": "cat",
                "segments": [{"avg_logprob": -0.2, "no_speech_prob": 0.01}],
            })
        return httpx.Response(404, json={"error": {"message": "unexpected path"}})

    mock = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=or_settings.base_url,
        headers={"Authorization": "Bearer test-or-key"},
    )
    services.client = lambda: mock

    assert services.chat([{"role": "user", "content": "hi"}]) == "hello"

    # json_schema is rejected -> automatic json_object fallback.
    assert services.chat_json(
        [{"role": "user", "content": "json please"}],
        schema={"type": "object", "properties": {"answer": {"type": "string"}}},
    ) == {"answer": "ok"}

    audio = services.synthesize_speech("cat")
    assert audio == b"ID3-fake-mp3"

    text, confidence = services.transcribe(b"fake-webm")
    assert text == "cat"
    assert confidence is not None and math.isclose(confidence, math.exp(-0.2), rel_tol=1e-9)

    # Gateways without logprobs can return a whole-transcript confidence.
    text2, confidence2 = services.transcribe(b"fake-webm", filename="audio.mp3")
    assert text2 == "dog"
    assert confidence2 is not None and math.isclose(confidence2, 0.9)

    stt_bodies = [r.content for r in seen if r.url.path.endswith("/audio/transcriptions")]
    assert any(b"openai%2Fwhisper-large-v3" in b or b"openai/whisper-large-v3" in b
               for b in stt_bodies), "model id missing from STT multipart body"
    chat_paths = [r.url.path for r in seen if r.url.path.endswith("/chat/completions")]
    assert len(chat_paths) >= 3, chat_paths  # chat + two chat_json attempts

    for request in seen:
        assert request.url.host == "openrouter.ai", request.url
        assert request.headers["authorization"] == "Bearer test-or-key", request.headers

    mock.close()
    services.reset_client()
    log.setLevel(previous_level)


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print("all gateway-provider self-checks passed")


if __name__ == "__main__":
    main()
