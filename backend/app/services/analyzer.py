"""
The heart of the system: combines ML models + rules into one verdict.

Pipeline: text -> find URLs -> text model + URL model + rules -> fuse -> explain
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import settings
from ..core.features import extract_urls, url_features
from ..core.privacy import redact
from ..core.rules import URL_SIGNAL_TEXT, match_rules
from .explainer import ADVICE, detect_language, explain
from .model_registry import registry

STRONG_URL_SIGNALS = {"brand_typosquat": 0.55, "brand_in_subdomain_or_path": 0.5, "has_ip": 0.45,
                      "has_at": 0.45, "has_punycode": 0.4}
MEDIUM_URL_SIGNALS = {"suspicious_tld": 0.25, "free_hosting": 0.2, "is_shortener": 0.2, "not_https": 0.1}


@dataclass
class UrlCheck:
    url: str
    score: float
    signals: list[str] = field(default_factory=list)


@dataclass
class Result:
    verdict: str
    risk_score: float
    text_score: float | None
    url_score: float | None
    reasons: list[str]
    explanation: str
    advice: list[str]
    urls: list[UrlCheck]
    language: str
    redacted_input: str
    model_version: str


def _url_signals(url: str) -> tuple[list[str], float]:
    f = url_features(url)
    active = [k for k in list(STRONG_URL_SIGNALS) + list(MEDIUM_URL_SIGNALS) if k != "not_https" and f.get(k)]
    if not f["is_https"]:
        active.append("not_https")
    heuristic = 1.0
    for k in active:
        heuristic *= 1 - {**STRONG_URL_SIGNALS, **MEDIUM_URL_SIGNALS}[k]
    return active, 1 - heuristic  # "noisy-OR": each signal independently adds risk


def check_urls(urls: list[str]) -> list[UrlCheck]:
    model_scores = registry.predict_urls(urls)
    out = []
    for i, u in enumerate(urls):
        signals, heuristic = _url_signals(u)
        f = url_features(u)
        if f["brand_is_domain"] and not f["brand_typosquat"] and f["is_https"]:
            heuristic = 0.0  # the real official brand domain
        score = heuristic if model_scores is None else max(model_scores[i], heuristic)
        out.append(UrlCheck(u, round(score, 4), signals))
    return out


MIN_VOCAB_COVERAGE = 0.5  # below this share of known words, the text model is not fully trusted


def fuse(text_score: float | None, url_score: float | None, rule_weights: list[float]) -> float:
    base = max([s for s in (text_score, url_score) if s is not None], default=0.0)
    keep = 1.0
    for w in rule_weights:
        keep *= 1 - w
    rule_boost = 1 - keep
    return min(1.0, base + rule_boost * (1 - base))


def verdict_for(score: float) -> str:
    if score >= settings.scam_threshold:
        return "scam"
    if score >= settings.suspicious_threshold:
        return "suspicious"
    return "safe"


async def analyze(text: str, only_url: bool = False) -> Result:
    text = (text or "").strip()[: settings.max_text_chars]
    lang = detect_language(text)
    urls = extract_urls(text)
    url_checks = check_urls(urls)
    url_score = max((u.score for u in url_checks), default=None)

    text_score = None if only_url else registry.predict_text(text)
    if text_score is not None:
        # If the model knows fewer than half the words, scale its score down so a guess
        # (e.g. a Hindi sentence where only a number is familiar) can't decide the verdict alone.
        coverage = registry.text_coverage(text)
        if coverage < MIN_VOCAB_COVERAGE:
            text_score *= coverage / MIN_VOCAB_COVERAGE
    rules = [] if only_url else match_rules(text)

    risk = round(fuse(text_score, url_score, [r.weight for r in rules]), 4)  # one rounded value everywhere
    verdict = verdict_for(risk)

    reasons: list[str] = [r.reason for r in sorted(rules, key=lambda r: -r.weight)]
    for uc in url_checks:
        if uc.score >= settings.suspicious_threshold:
            reasons.extend(URL_SIGNAL_TEXT[s] for s in uc.signals if URL_SIGNAL_TEXT[s] not in reasons)
            if not uc.signals:
                reasons.append("Our link-checking model found this website address similar to known phishing links.")
    if text_score is not None and text_score >= 0.7 and not rules:
        reasons.append("The wording is very similar to scam messages our AI model was trained on.")

    redacted = redact(text)
    explanation = await explain(redacted, verdict, risk, reasons, lang)
    return Result(
        verdict=verdict, risk_score=round(risk, 4),
        text_score=None if text_score is None else round(text_score, 4),
        url_score=None if url_score is None else round(url_score, 4),
        reasons=reasons, explanation=explanation, advice=ADVICE[lang][verdict], urls=url_checks,
        language=lang, redacted_input=redacted, model_version=registry.version_string,
    )
