"""Remove personal data BEFORE anything is stored or sent to an external LLM."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_UPI = re.compile(r"\b[\w.-]{2,}@(?:ok\w+|ybl|ibl|axl|paytm|upi|apl|sbi|hdfc\w*|icici|axis\w*)\b", re.I)
_PHONE = re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b")
_CARD_OR_ACCOUNT = re.compile(r"\b\d(?:[ -]?\d){8,18}\b")  # starts and ends on a digit: keeps the next space
_OTP = re.compile(r"\b(otp|code|pin|password|cvv)(\D{0,15})\d{4,8}\b", re.I)


def redact(text: str) -> str:
    t = _UPI.sub("[UPI_ID]", text or "")
    t = _EMAIL.sub("[EMAIL]", t)
    t = _OTP.sub(lambda m: f"{m.group(1)}{m.group(2)}[CODE]", t)
    t = _PHONE.sub("[PHONE]", t)
    t = _CARD_OR_ACCOUNT.sub("[NUMBER]", t)
    return t


# Redacted training data says "[PHONE]", but live messages contain real digits. If we trained on the
# placeholders the model would learn a token it never sees in real use (training-serving skew), and
# rules like call_unknown_number could not fire. So before training/evaluating on redacted text we
# put back neutral dummy values that look like the real thing.
_DUMMY = {
    "[PHONE]": "9000000000", "[NUMBER]": "000000000000", "[CODE]": "000000",
    "[EMAIL]": "user@example.com", "[UPI_ID]": "user@okaxis", "[NAME]": "Amit",
}
_PLACEHOLDER = re.compile("|".join(re.escape(k) for k in _DUMMY))


def fill_placeholders(text: str) -> str:
    return _PLACEHOLDER.sub(lambda m: _DUMMY[m.group(0)], text or "")
