"""
Feature engineering shared by TRAINING (ml/*.py) and SERVING (backend).

Keeping one copy of this code is important: if training and serving computed
features differently, the live model would silently give wrong answers
(this bug is called "training/serving skew").
"""
from __future__ import annotations

import math
import re
from collections import Counter
from urllib.parse import urlsplit

import tldextract

# Offline extractor: uses the public-suffix list bundled with the package (no network call).
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())

URL_REGEX = re.compile(
    r"""(?xi)
    \b(
      (?:https?://|www\.)[^\s<>"']+            # http://..., https://..., www....
      |
      (?:[a-z0-9-]+\.)+(?:com|in|net|org|co|io|xyz|top|info|ly|me|link|site|online|app|tk|ml|ga|cf|gq|ru|cn|club|shop|live|icu|buzz)
      (?:/[^\s<>"']*)?                          # bare domains like sbi-kyc.xyz/login
    )""",
)

BRANDS = [
    "paypal", "apple", "icloud", "amazon", "microsoft", "office365", "outlook", "netflix",
    "google", "gmail", "facebook", "instagram", "whatsapp", "telegram", "steam", "roblox",
    "sbi", "onlinesbi", "hdfc", "icici", "axis", "kotak", "pnb", "paytm", "phonepe", "gpay",
    "flipkart", "myntra", "airtel", "jio", "irctc", "uidai", "aadhaar", "incometax", "epfo",
    "dhl", "fedex", "indiapost", "bluedart", "coinbase", "binance", "metamask", "bank",
]
SUSPICIOUS_TLDS = {
    "tk", "ml", "ga", "cf", "gq", "xyz", "top", "club", "online", "site", "icu", "buzz",
    "live", "shop", "info", "ru", "cn", "work", "rest", "fit", "click", "link", "cyou",
    "sbs", "vip", "monster", "quest", "support", "cam", "mom", "lol",
}
SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "cutt.ly", "rb.gy", "ow.ly",
    "shorturl.at", "tiny.cc", "buff.ly", "rebrand.ly", "t.ly", "s.id", "v.gd", "rbx.tg",
}
FREE_HOSTING = {
    "firebaseapp.com", "web.app", "weebly.com", "wixsite.com", "000webhostapp.com",
    "github.io", "netlify.app", "vercel.app", "pages.dev", "glitch.me", "blogspot.com",
    "duckdns.org", "ngrok.io", "ngrok-free.app", "herokuapp.com", "repl.co", "square.site",
    "godaddysites.com", "sites.google.com", "workers.dev", "r2.dev", "ipfs.io",
}
SENSITIVE_WORDS = [
    "login", "signin", "sign-in", "verify", "verification", "account", "update", "secure",
    "security", "banking", "confirm", "password", "wallet", "kyc", "otp", "unlock",
    "suspend", "billing", "payment", "refund", "reward", "gift", "free", "bonus", "claim",
]

URL_FEATURE_NAMES = [
    "url_length", "host_length", "path_length", "query_length", "num_dots", "num_hyphens",
    "num_digits", "digit_ratio", "num_special", "num_subdomains", "has_at", "has_ip",
    "is_https", "has_port", "double_slash_in_path", "suspicious_tld", "is_shortener",
    "free_hosting", "brand_in_subdomain_or_path", "brand_typosquat", "brand_is_domain",
    "sensitive_word_count", "host_entropy", "domain_length", "domain_digit_count",
    "domain_hyphen_count", "path_depth", "has_punycode", "num_params", "has_encoded_chars",
    "tld_length", "longest_token",
]


def normalize_url(url: str) -> str:
    url = url.strip().strip(".,;:!?)(]['\"")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        url = "http://" + url
    return url


def extract_urls(text: str) -> list[str]:
    found = [m.group(1) for m in URL_REGEX.finditer(text or "")]
    seen, out = set(), []
    for u in found:
        n = normalize_url(u)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:10]


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in counts.values())


def _edit_distance(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def url_parts(url: str):
    url = normalize_url(url)
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        parts, host, port = urlsplit("http://invalid"), "", None
    ext = _EXTRACT(host)
    registered = ".".join(p for p in [ext.domain, ext.suffix] if p)
    return url, parts, host, port, ext, registered


def url_features(url: str) -> dict[str, float]:
    url, parts, host, port, ext, registered = url_parts(url)
    path, query = parts.path or "", parts.query or ""
    domain = ext.domain.lower()
    sub = ext.subdomain.lower()
    sub_clean = re.sub(r"^www\d*\.?", "", sub)
    lower = url.lower()

    brand_elsewhere = any(b in (sub_clean + path.lower()) for b in BRANDS) and not any(
        b == domain for b in BRANDS
    )
    typosquat = any(
        0 < _edit_distance(domain, b) <= 2 and len(b) >= 5 for b in BRANDS
    ) or any(b in domain and b != domain and len(b) >= 4 for b in BRANDS)

    tokens = re.split(r"[./?=&_\-:]+", lower)
    return {
        "url_length": len(url),
        "host_length": len(host),
        "path_length": len(path),
        "query_length": len(query),
        "num_dots": url.count("."),
        "num_hyphens": url.count("-"),
        "num_digits": sum(c.isdigit() for c in url),
        "digit_ratio": sum(c.isdigit() for c in url) / max(len(url), 1),
        "num_special": sum(c in "~!$%^*+|;,'\"<>" for c in url),
        "num_subdomains": len([s for s in sub_clean.split(".") if s]),
        "has_at": float("@" in url),
        "has_ip": float(bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host))),
        "is_https": float(parts.scheme == "https"),
        "has_port": float(port is not None),
        "double_slash_in_path": float("//" in path),
        "suspicious_tld": float(ext.suffix.split(".")[-1] in SUSPICIOUS_TLDS),
        "is_shortener": float(host.removeprefix("www.") in SHORTENERS),
        "free_hosting": float(any(host == h or host.endswith("." + h) for h in FREE_HOSTING)),
        "brand_in_subdomain_or_path": float(brand_elsewhere),
        "brand_typosquat": float(typosquat),
        "brand_is_domain": float(domain in BRANDS),
        "sensitive_word_count": sum(w in lower for w in SENSITIVE_WORDS),
        "host_entropy": _entropy(host),
        "domain_length": len(domain),
        "domain_digit_count": sum(c.isdigit() for c in domain),
        "domain_hyphen_count": domain.count("-"),
        "path_depth": len([p for p in path.split("/") if p]),
        "has_punycode": float("xn--" in host),
        "num_params": len([q for q in query.split("&") if q]),
        "has_encoded_chars": float("%" in url),
        "tld_length": len(ext.suffix),
        "longest_token": max((len(t) for t in tokens), default=0),
    }


def url_feature_vector(url: str) -> list[float]:
    f = url_features(url)
    return [float(f[name]) for name in URL_FEATURE_NAMES]


def normalize_text(text: str) -> str:
    """Light cleanup before the text model (same at train and serve time)."""
    t = (text or "").lower()
    t = URL_REGEX.sub(" urltoken ", t)
    t = re.sub(r"(?:rs\.?|inr|₹)\s*[\d,]+", " moneytoken ", t)
    t = re.sub(r"\d{5,}", " longnumtoken ", t)
    t = re.sub(r"\d+", " numtoken ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()
