"""Automated tests. Run:  pytest -q"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DATABASE_URL"] = "sqlite:///" + (ROOT / "test_scamshield.db").as_posix()
os.environ["LLM_API_KEY"] = ""  # never call a real LLM in tests

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.features import extract_urls, url_features  # noqa: E402
from app.core.privacy import redact  # noqa: E402
from app.core.rules import match_rules  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    from app.db import engine
    engine.dispose()  # release the SQLite file (Windows locks open files)
    (ROOT / "test_scamshield.db").unlink(missing_ok=True)


# ---------- unit tests ----------
def test_redact_removes_personal_data():
    out = redact("Call 9876543210, mail a.b@gmail.com, OTP is 482913, card 4111 1111 1111 1111, upi raj@okaxis")
    for secret in ["9876543210", "a.b@gmail.com", "482913", "4111", "raj@okaxis"]:
        assert secret not in out


def test_extract_urls():
    urls = extract_urls("visit http://sbi-kyc.xyz/login or bit.ly/abc now")
    assert "http://sbi-kyc.xyz/login" in urls
    assert any("bit.ly/abc" in u for u in urls)


def test_typosquat_feature():
    assert url_features("https://store.steamcommunite.com/gift")["brand_typosquat"] == 1
    assert url_features("https://www.amazon.in/orders")["brand_typosquat"] == 0


def test_rules_hinglish():
    ids = {r.id for r in match_rules("Aapka bank khata band ho jayega. Apna OTP batayein turant")}
    assert {"otp_request", "urgency"} <= ids


# ---------- API tests ----------
def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_scam_message_detected(client):
    r = client.post("/api/analyze/text", json={
        "text": "Dear customer your SBI account will be blocked today. Update KYC immediately "
                "at http://sbi-kyc-update.xyz/login and share OTP"})
    assert r.status_code == 200
    d = r.json()
    assert d["verdict"] == "scam"
    assert d["reasons"]


def test_normal_message_safe(client):
    d = client.post("/api/analyze/text", json={"text": "Hi, are we still meeting at 5 pm near the library?"}).json()
    assert d["verdict"] == "safe"


def test_official_url_not_scam(client):
    d = client.post("/api/analyze/url", json={"url": "https://www.amazon.in/gp/css/order-history"}).json()
    assert d["verdict"] != "scam"


def test_phishing_url(client):
    d = client.post("/api/analyze/url", json={"url": "http://secure-paypal-verify.com.login-check.ru/signin"}).json()
    assert d["verdict"] in ("scam", "suspicious")


def test_pii_not_stored_and_feedback(client):
    d = client.post("/api/analyze/text", json={"text": "Send money to 9876543210 now"}).json()
    from app.db import SessionLocal
    from app.models import Analysis
    with SessionLocal() as db:
        assert "9876543210" not in db.get(Analysis, d["analysis_id"]).redacted_input
    assert client.post("/api/feedback", json={"analysis_id": d["analysis_id"], "is_correct": True}).status_code == 200
    stats = client.get("/api/stats").json()
    assert stats["feedback_count"] >= 1


def test_validation(client):
    assert client.post("/api/analyze/text", json={"text": ""}).status_code == 422
    assert client.post("/api/feedback", json={"analysis_id": "nope", "is_correct": True}).status_code == 404
