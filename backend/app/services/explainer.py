"""
Turns the model's decision into a short, friendly explanation.

* If LLM_API_KEY is set, we call a free OpenAI-compatible LLM API (e.g. Groq).
* If not (or the call fails), we build the explanation from a template.
The LLM never decides the verdict - it only explains it. Only REDACTED text is sent.
"""
from __future__ import annotations

import logging
import re

import httpx

from ..config import settings

log = logging.getLogger("scamshield.explainer")

ADVICE = {
    "en": {
        "scam": [
            "Do not click any link or call any number in this message.",
            "Never share OTP, PIN, CVV or passwords with anyone.",
            "Block and report the sender. In India, report at cybercrime.gov.in or call 1930.",
        ],
        "suspicious": [
            "Do not act in a hurry. Verify using the official app or website you already trust.",
            "Call the company only on the number printed on its official website or your card.",
        ],
        "safe": [
            "No strong scam signs found, but stay alert. Never share OTPs or passwords.",
        ],
    },
    "hi": {
        "scam": [
            "इस मैसेज के किसी भी लिंक पर क्लिक न करें और दिए गए नंबर पर कॉल न करें।",
            "OTP, PIN, CVV या पासवर्ड किसी के साथ साझा न करें।",
            "भेजने वाले को ब्लॉक करें और cybercrime.gov.in पर या 1930 पर शिकायत करें।",
        ],
        "suspicious": [
            "जल्दबाज़ी न करें। केवल आधिकारिक ऐप या वेबसाइट से जांच करें।",
            "कंपनी को केवल उसकी आधिकारिक वेबसाइट पर दिए नंबर पर कॉल करें।",
        ],
        "safe": ["कोई बड़ा खतरा नहीं मिला, फिर भी सावधान रहें। OTP या पासवर्ड कभी साझा न करें।"],
    },
}

VERDICT_TEXT = {
    "en": {"scam": "This looks like a SCAM.", "suspicious": "This looks SUSPICIOUS.", "safe": "This looks SAFE."},
    "hi": {"scam": "यह एक धोखाधड़ी (SCAM) लगता है।", "suspicious": "यह संदिग्ध (SUSPICIOUS) लगता है।",
           "safe": "यह सुरक्षित (SAFE) लगता है।"},
}


def detect_language(text: str) -> str:
    return "hi" if re.search(r"[ऀ-ॿ]", text or "") else "en"


SUMMARY = {
    "en": {"scam": "We found {n} strong warning sign(s). Do not reply, click, call or pay.",
           "suspicious": "We found {n} warning sign(s). Check with the official source before you act.",
           "safe": "We did not find known scam patterns."},
    "hi": {"scam": "हमें {n} बड़े खतरे के संकेत मिले। जवाब न दें, क्लिक न करें, कॉल या भुगतान न करें।",
           "suspicious": "हमें {n} चेतावनी संकेत मिले। कुछ भी करने से पहले आधिकारिक स्रोत से जांच करें।",
           "safe": "हमें कोई जाना-पहचाना धोखाधड़ी पैटर्न नहीं मिला।"},
}


def risk_pct(score: float) -> int:
    return min(99, round(score * 100))  # never claim 100% certainty


def template_explanation(verdict: str, score: float, reasons: list[str], lang: str) -> str:
    head = f"{VERDICT_TEXT[lang][verdict]} ({risk_pct(score)}% risk)"
    return f"{head} {SUMMARY[lang][verdict].format(n=len(reasons))}"


async def explain(redacted_text: str, verdict: str, score: float, reasons: list[str], lang: str) -> str:
    if not settings.llm_api_key:
        return template_explanation(verdict, score, reasons, lang)

    language = "simple Hindi" if lang == "hi" else "simple English"
    system = ("You are a cyber-safety assistant for ordinary people in India. Explain in "
              f"{language}, in at most 3 short sentences, why a message is risky or safe. "
              "Do not change the verdict. Do not invent facts. No markdown.")
    user = (f"Verdict: {verdict} ({risk_pct(score)}% risk)\n"
            f"Detected signals: {'; '.join(reasons) or 'none'}\n"
            f"Message (personal data removed):\n{redacted_text[:1500]}")
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            r = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": settings.llm_model, "temperature": 0.2, "max_tokens": 180,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            return text or template_explanation(verdict, score, reasons, lang)
    except Exception as exc:
        log.warning("LLM explanation failed, using template: %s", exc)
        return template_explanation(verdict, score, reasons, lang)
