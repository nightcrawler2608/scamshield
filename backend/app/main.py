"""
ScamShield API.  Run locally:
    uvicorn app.main:app --reload --app-dir backend
Then open http://127.0.0.1:8000  (web app)  or  http://127.0.0.1:8000/docs  (API docs)
"""
from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, init_db
from .models import Analysis, Feedback
from .schemas import AnalysisOut, FeedbackIn, StatsOut, TextIn, UrlIn, UrlResult
from .services.analyzer import Result, analyze
from .services.model_registry import registry
from .services.ocr import OCRUnavailable, image_to_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    registry.load()
    yield


app = FastAPI(title="ScamShield API", version="1.0.0",
              description="AI-powered scam & phishing detection. Model decides, LLM explains.",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

# ---- very small in-memory rate limiter (protects free-tier hosting from abuse) ----
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/analyze"):
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
        now, q = time.time(), _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return JSONResponse({"detail": "Too many requests. Please wait a minute."}, status_code=429)
        q.append(now)
    return await call_next(request)


def _save(db: Session, r: Result, input_type: str, channel: str) -> str:
    row = Analysis(channel=channel, input_type=input_type, redacted_input=r.redacted_input, verdict=r.verdict,
                   risk_score=r.risk_score, text_score=r.text_score, url_score=r.url_score,
                   reasons=r.reasons, language=r.language, model_version=r.model_version)
    db.add(row)
    db.commit()
    return row.id


def _out(analysis_id: str, r: Result, extracted: str | None = None) -> AnalysisOut:
    return AnalysisOut(
        analysis_id=analysis_id, verdict=r.verdict, risk_score=r.risk_score, text_score=r.text_score,
        url_score=r.url_score, reasons=r.reasons, explanation=r.explanation, advice=r.advice,
        urls=[UrlResult(url=u.url, score=u.score, signals=u.signals) for u in r.urls],
        language=r.language, model_version=r.model_version, extracted_text=extracted)


@app.get("/api/health")
def health():
    return {"status": "ok", "models": registry.versions, "llm_enabled": bool(settings.llm_api_key)}


@app.post("/api/analyze/text", response_model=AnalysisOut)
async def analyze_text(body: TextIn, db: Session = Depends(get_db)):
    r = await analyze(body.text)
    return _out(_save(db, r, "text", body.channel), r)


@app.post("/api/analyze/url", response_model=AnalysisOut)
async def analyze_url(body: UrlIn, db: Session = Depends(get_db)):
    r = await analyze(body.url, only_url=True)
    if not r.urls:
        raise HTTPException(422, "That does not look like a valid link.")
    return _out(_save(db, r, "url", body.channel), r)


@app.post("/api/analyze/image", response_model=AnalysisOut)
async def analyze_image(file: UploadFile = File(...), channel: str = Form("web"), db: Session = Depends(get_db)):
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Please upload a PNG, JPG or WEBP screenshot.")
    data = await file.read()
    if len(data) > settings.max_image_mb * 1024 * 1024:
        raise HTTPException(413, f"Image too large (max {settings.max_image_mb} MB).")
    try:
        text = image_to_text(data)
    except OCRUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    if len(text) < 5:
        raise HTTPException(422, "Could not read any text in this image.")
    r = await analyze(text)
    ch = channel if channel in {"web", "telegram", "extension", "api"} else "api"
    return _out(_save(db, r, "image", ch), r, extracted=r.redacted_input)


@app.post("/api/feedback")
def feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    if not db.get(Analysis, body.analysis_id):
        raise HTTPException(404, "Unknown analysis_id")
    db.add(Feedback(analysis_id=body.analysis_id, is_correct=body.is_correct,
                    correct_label=body.correct_label, comment=body.comment))
    db.commit()
    return {"status": "thanks"}


@app.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    counts = dict(db.query(Analysis.verdict, func.count()).group_by(Analysis.verdict).all())
    fb_total = db.query(func.count(Feedback.id)).scalar() or 0
    fb_correct = db.query(func.count(Feedback.id)).filter(Feedback.is_correct.is_(True)).scalar() or 0
    reason_counter: Counter = Counter()
    for (reasons,) in db.query(Analysis.reasons).order_by(Analysis.created_at.desc()).limit(500):
        reason_counter.update((reasons or [])[:3])
    return StatsOut(
        total_checks=sum(counts.values()), scams_detected=counts.get("scam", 0),
        suspicious=counts.get("suspicious", 0), safe=counts.get("safe", 0), feedback_count=fb_total,
        accuracy_from_feedback=round(fb_correct / fb_total, 4) if fb_total else None,
        top_reasons=reason_counter.most_common(5),
        models={k: {"version": registry.versions.get(k), **{m: v for m, v in registry.metrics.get(k, {}).items()
                                                           if m in ("precision", "recall", "f1", "roc_auc")}}
                for k in ("text", "url")},
    )


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC / "dashboard.html")
