"""FastAPI application: HTTP layer for MBDT.

All learner data stays local (SQLite). External requests are routed through the
configured gateway (Requesty or OpenRouter) by `services.py`. Routes are grouped
by exercise plus a small set of learner / guardian / dashboard endpoints.

Note: Pydantic request models MUST be module-level for FastAPI to detect them
as request bodies (defining them inside `create_app()` no longer works on
recent FastAPI/Pydantic 2 builds).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

import db, repository as repo
import exercises as ex
import services
from config import settings, has_api_key
from services import ServiceError


def _svc_error(e: ServiceError) -> HTTPException:
    """Map a ServiceError to a 503 carrying structured {code, message, model}."""
    detail: object = str(e)
    if getattr(e, "code", None):
        detail = {"code": e.code, "message": str(e), "model": e.model}
    return HTTPException(503, detail)


# --------------------------------------------------------------------- schemas
# Audio container -> HTTP media type (TTS format is configurable).
_AUDIO_MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


def _audio_media_type() -> str:
    return _AUDIO_MEDIA_TYPES.get(settings.tts_format, "audio/mpeg")


class LearnerIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be empty")
        return value


class GuardianIn(BaseModel):
    word_set: str | None = Field(default=None, description="e.g. phonics-starter")
    interests: str | None = Field(default=None, description="comma-separated")
    safety_categories: str | None = Field(default=None)
    confidence_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_model: str | None = Field(default=None, description="LLM override; empty clears")


class Ex3SpellCheckIn(BaseModel):
    word_id: int
    submitted: str | None = None
    image_data_url: str | None = None


class Ex3CategorizeIn(BaseModel):
    phoneme: str
    selected_word_ids: list[int]
    option_word_ids: list[int]


class Ex5AnswerIn(BaseModel):
    question: str
    expected: str
    given: str


class Ex5CheckIn(BaseModel):
    story_id: int
    answers: list[Ex5AnswerIn]


class PasswordIn(BaseModel):
    password: str


class AdminPasswordChangeIn(BaseModel):
    current: str
    new: str


def _admin_auth_failed() -> HTTPException:
    return HTTPException(403, {"code": "admin_auth_failed", "message": "Wrong admin password"})


# ---------------------------------------------------------------------- app
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="MBDT", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ meta
    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "api_key_configured": has_api_key(),
            "provider": settings.provider,
            "provider_label": settings.provider_label,
            "models": {
                "llm": settings.llm_model,
                "ocr": settings.ocr_model,
                "tts": settings.tts_model,
                "stt": settings.stt_model,
            },
        }

    # --------------------------------------------------------------- learners
    @app.post("/api/learners")
    def create_learner(body: LearnerIn) -> dict:
        lid = repo.ensure_learner(body.name)
        return {"id": lid, "name": body.name}

    @app.get("/api/learners")
    def list_learners() -> list[dict]:
        return repo.list_learners()

    @app.get("/api/learners/{learner_id}")
    def get_learner(learner_id: int) -> dict:
        l = repo.get_learner(learner_id)
        if not l:
            raise HTTPException(404, "learner not found")
        l["composite_score"] = repo.composite(learner_id)
        l["word_accuracy"] = round(repo.word_accuracy(learner_id), 3)
        l["comprehension_accuracy"] = round(repo.comprehension_accuracy(learner_id), 3)
        l["guardian"] = repo.get_guardian_settings(learner_id)
        return l

    @app.get("/api/learners/{learner_id}/dashboard")
    def get_dashboard(learner_id: int) -> dict:
        d = repo.learner_dashboard(learner_id)
        if d is None:
            raise HTTPException(404, "learner not found")
        return d

    # -------------------------------------------------------- guardian config
    @app.put("/api/learners/{learner_id}/guardian")
    def update_guardian(learner_id: int, body: GuardianIn) -> dict:
        if body.word_set:
            repo.set_guardian_word_set(learner_id, body.word_set)
        repo.update_guardian_settings(
            learner_id,
            interests=body.interests,
            safety_categories=body.safety_categories,
            confidence_floor=body.confidence_floor,
            llm_model=body.llm_model,
        )
        return {"ok": True, "guardian": repo.get_guardian_settings(learner_id)}

    @app.get("/api/word-sets")
    def list_word_sets() -> dict:
        from data import SET_LABELS, SETS
        return {
            "sets": [
                {"id": key, "label": SET_LABELS.get(key, key)} for key in SETS
            ]
        }

    # --------------------------------------------------- Exercise 1: speaking
    def _require_learner(learner_id: int) -> None:
        if not repo.get_learner(learner_id):
            raise HTTPException(404, "learner not found")

    @app.get("/api/exercise1/{learner_id}/round")
    def ex1_round(learner_id: int, n: int = 8) -> dict:
        _require_learner(learner_id)
        round_ = ex.exercise1.build_round(learner_id, n=n)
        return {
            "items": [
                {
                    "word_id": it.word_id,
                    "text": it.text,
                    "phoneme": it.phoneme,
                    "font": it.font,
                }
                for it in round_.items
            ],
            "confidence_floor": round_.confidence_floor,
        }

    @app.get("/api/exercise1/{word}/audio")
    def ex1_audio(word: str) -> Response:
        try:
            audio = ex.exercise1.generate_pronunciation_audio(word)
        except ServiceError as e:
            raise _svc_error(e) from e
        return Response(
            content=audio,
            media_type=_audio_media_type(),
            headers={"Cache-Control": "public, max-age=86400"},  # word audio is deterministic
        )

    @app.post("/api/exercise1/{learner_id}/check")
    async def ex1_check(
        learner_id: int,
        word_id: int = Form(...),
        font: str = Form(...),
        audio: UploadFile = File(...),
    ) -> dict:
        _require_learner(learner_id)
        audio_bytes = await audio.read()
        try:
            # Blocking STT round trip -> threadpool so the event loop stays live.
            return await run_in_threadpool(
                ex.exercise1.check_pronunciation,
                learner_id, word_id, font, audio_bytes,
                filename=audio.filename or "audio.webm",
            )
        except ServiceError as e:
            raise _svc_error(e) from e
        except ValueError as e:
            raise HTTPException(400, str(e))

    # --------------------------------------------------- Exercise 3: writing
    @app.get("/api/exercise3/{learner_id}/spell")
    def ex3_spell_round(learner_id: int, n: int = 6) -> dict:
        _require_learner(learner_id)
        r = ex.exercise3.build_spell_round(learner_id, n=n)
        return {
            "items": [
                {"word_id": it.word_id, "phoneme": it.phoneme} for it in r.items
            ]
        }

    @app.get("/api/exercise3/word/{word}/audio")
    def ex3_word_audio(word: str) -> Response:
        try:
            audio = ex.exercise3.render_word_audio(word)
        except ServiceError as e:
            raise _svc_error(e) from e
        return Response(
            content=audio,
            media_type=_audio_media_type(),
            headers={"Cache-Control": "public, max-age=86400"},  # word audio is deterministic
        )

    @app.get("/api/exercise3/learner/{learner_id}/word-id/{word_id}/audio")
    def ex3_word_audio_by_id(learner_id: int, word_id: int) -> Response:
        """TTS-render a word by id, without exposing the text to the client.

        Used by the spell-from-sound task so the answer is never in the DOM.
        """
        word = repo.load_word(learner_id, word_id)
        if not word:
            raise HTTPException(404, "word not found")
        try:
            audio = ex.exercise3.render_word_audio(word.text)
        except ServiceError as e:
            raise _svc_error(e) from e
        return Response(
            content=audio,
            media_type=_audio_media_type(),
            headers={"Cache-Control": "public, max-age=86400"},  # word audio is deterministic
        )

    @app.post("/api/exercise3/{learner_id}/spell/check")
    def ex3_spell_check(learner_id: int, body: Ex3SpellCheckIn) -> dict:
        _require_learner(learner_id)
        try:
            return ex.exercise3.check_spelling(
                learner_id, body.word_id, body.submitted or "",
                image_data_url=body.image_data_url,
            )
        except ServiceError as e:
            raise _svc_error(e) from e
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/exercise3/{learner_id}/categorize")
    def ex3_categorize_round(learner_id: int, n_options: int = 6) -> dict:
        _require_learner(learner_id)
        try:
            r = ex.exercise3.build_categorize_round(learner_id, n_options=n_options)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {
            "phoneme": r.phoneme,
            "options": [
                {"word_id": o.word_id, "text": o.text} for o in r.options
            ],
        }

    @app.post("/api/exercise3/{learner_id}/categorize/check")
    def ex3_categorize_check(learner_id: int, body: Ex3CategorizeIn) -> dict:
        _require_learner(learner_id)
        try:
            return ex.exercise3.check_categorization(
                learner_id,
                body.phoneme,
                body.selected_word_ids,
                body.option_word_ids,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    # --------------------------------------------------- Exercise 5: reading
    @app.get("/api/exercise5/{learner_id}/story")
    def ex5_story(learner_id: int, n_words: int = 8) -> dict:
        _require_learner(learner_id)
        try:
            r = ex.exercise5.build_story(learner_id, n_words=n_words)
        except ServiceError as e:
            raise _svc_error(e) from e
        return {
            "story_id": r.story_id,
            "text": r.text,
            "target_words": r.target_words,
            "questions": [
                {"question": q.question, "expected": q.expected} for q in r.questions
            ],
        }

    @app.post("/api/exercise5/{learner_id}/check")
    def ex5_check(learner_id: int, body: Ex5CheckIn) -> dict:
        _require_learner(learner_id)
        try:
            return ex.exercise5.check_comprehension(
                learner_id, body.story_id,
                [a.model_dump() for a in body.answers],
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ------------------------------------------------------------- TTS helper
    @app.get("/api/tts")
    def tts(text: str, voice: str | None = None) -> Response:
        if not text.strip():
            raise HTTPException(400, "text is required")
        try:
            audio = services.synthesize_speech(text, voice=voice)
        except ServiceError as e:
            raise _svc_error(e) from e
        return Response(
            content=audio,
            media_type=_audio_media_type(),
            headers={"Cache-Control": "public, max-age=86400"},  # word audio is deterministic
        )

    # ------------------------------------------- daily session & admin tools
    @app.get("/api/daily/{learner_id}/status")
    def daily_status(learner_id: int) -> dict:
        _require_learner(learner_id)
        return repo.daily_status(learner_id)

    @app.post("/api/daily/{learner_id}/complete")
    def daily_complete(learner_id: int) -> dict:
        _require_learner(learner_id)
        repo.mark_daily_complete(learner_id)
        return repo.daily_status(learner_id)

    @app.post("/api/daily/{learner_id}/skip")
    def daily_skip(learner_id: int, body: PasswordIn) -> dict:
        _require_learner(learner_id)
        if not repo.verify_admin_password(body.password):
            raise _admin_auth_failed()
        repo.mark_daily_skipped(learner_id)
        return repo.daily_status(learner_id)

    @app.post("/api/daily/{learner_id}/reset")
    def daily_reset(learner_id: int, body: PasswordIn) -> dict:
        _require_learner(learner_id)
        if not repo.verify_admin_password(body.password):
            raise _admin_auth_failed()
        repo.reset_daily(learner_id)
        return repo.daily_status(learner_id)

    @app.post("/api/admin/verify")
    def admin_verify(body: PasswordIn) -> dict:
        if not repo.verify_admin_password(body.password):
            raise _admin_auth_failed()
        return {"ok": True}

    @app.post("/api/admin/password")
    def admin_password_change(body: AdminPasswordChangeIn) -> dict:
        if not repo.verify_admin_password(body.current):
            raise _admin_auth_failed()
        if len(body.new.strip()) < 4:
            raise HTTPException(400, "new password must be at least 4 characters")
        repo.set_admin_password(body.new.strip())
        return {"ok": True}

    return app


app = create_app()
