"""
Rule engine: well-known scam tricks, written as regex patterns (English + Hinglish).

Why rules if we have ML?  A brand-new scam can appear tomorrow; a rule catches it
on day one, while the model needs data. Rules also give clear, human reasons.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    weight: float  # how strongly this pushes the score towards "scam" (0-1)
    reason: str
    pattern: re.Pattern


def _r(id_: str, weight: float, reason: str, *patterns: str) -> Rule:
    return Rule(id_, weight, reason, re.compile("|".join(patterns), re.I))


RULES: list[Rule] = [
    _r("otp_request", 0.45, "Asks you to share an OTP, PIN, CVV or password. Real banks and companies never ask for these.",
       r"(share|send|tell|batao|batayein|bhejo|give|provide|reply with|enter)\b.{0,40}\b(otp|pin|cvv|password|card number)",
       r"\b(otp|cvv|pin)\b.{0,30}\b(share|batao|batayein|bhejo|executive|agent)"),
    _r("account_block", 0.30, "Threatens that your account, card, SIM or connection will be blocked or suspended.",
       r"\b(block(ed)?|suspend(ed)?|deactivat\w*|disconnect\w*|band ho|kaat|expire[sd]?|locked|terminated)\b.{0,60}\b(account|card|sim|number|connection|kyc|service|khata)",
       r"\b(account|card|sim|number|connection|kyc|khata)\b.{0,60}\b(block(ed)?|suspend(ed)?|deactivat\w*|disconnect\w*|band ho|kaat|locked)"),
    _r("kyc_update", 0.30, "Asks you to update KYC / PAN / Aadhaar through a message or link.",
       r"\b(kyc|pan card|aadhaar|aadhar)\b.{0,40}\b(update|link|verify|pending|incomplete|expire)",
       r"\b(update|verify|link)\b.{0,30}\b(kyc|pan|aadhaar|aadhar)\b"),
    _r("urgency", 0.20, "Creates panic or urgency (\"immediately\", \"within 24 hours\", \"tonight\") so you act without thinking.",
       r"\b(urgent(ly)?|immediately|turant|jaldi|final notice|last chance|act now|within \d+ ?(hours?|hrs?|minutes?)|today itself|tonight)\b"),
    _r("prize_lottery", 0.40, "Promises a prize, lottery, lucky draw or free gift you never entered for.",
       r"\b(lottery|lucky draw|jackpot|inaam|you (have )?won|congratulations.{0,40}(won|selected|winner)|kbc|claim your (prize|reward|gift))\b"),
    _r("advance_fee", 0.40, "Asks you to pay a fee first (registration, processing, GST, delivery, customs) to receive money, a job or a gift.",
       r"\b(pay|deposit|jama)\b.{0,40}\b(fee|charge|gst|tax|registration|processing|clearance)\b",
       r"\b(registration|processing|clearance|file|delivery|redelivery) (fee|charge)s?\b"),
    _r("job_task_scam", 0.40, "Offers easy money for simple online tasks (likes, reviews, 'prepaid tasks'). This is a common task scam.",
       r"\b(earn|income|kamaye?n?)\b.{0,40}\b(per day|daily|per review|per like|from home)\b",
       r"\b(like|rate|review)\b.{0,30}\b(youtube|videos|hotels|google maps)\b.{0,40}\b(earn|rs|₹|paid)",
       r"\b(part[- ]time job|work from home|prepaid task|telegram task)\b"),
    _r("upi_collect", 0.45, "Asks you to accept a collect/payment request or scan a QR code to *receive* money. You never need to do this to receive money.",
       r"\b(accept|approve)\b.{0,40}\b(collect|payment|upi) request",
       r"\bscan\b.{0,30}\bqr\b.{0,40}\b(receive|get|cashback|refund)"),
    _r("authority_threat", 0.45, "Pretends to be police, CBI, customs, courts or government and threatens arrest or legal action.",
       r"\b(digital arrest|cbi|narcotics|cyber ?cell|customs department|money laundering|arrest warrant|legal action|court case)\b"),
    _r("investment_promise", 0.35, "Promises guaranteed or unrealistic investment returns.",
       r"\b(guaranteed|100%)\b.{0,30}\b(profit|return)s?\b",
       r"\b(double|triple) your money\b",
       r"\binvest\b.{0,40}\bget\b.{0,20}(rs|₹|\d)"),
    _r("family_emergency", 0.30, "Claims to be a family member with a new number asking for money urgently.",
       r"\b(new number|lost my phone|changed my number)\b.{0,80}\b(send|transfer|need)\b"),
    _r("remote_access_app", 0.40, "Asks you to install a screen-sharing app or an APK file, which can give scammers control of your phone.",
       r"\b(anydesk|teamviewer|quick ?support|rustdesk)\b", r"\.apk\b"),
    _r("call_unknown_number", 0.15, "Pushes you to call or WhatsApp an unknown personal number instead of an official helpline.",
       r"\b(call|contact|whatsapp|message)\b.{0,30}(\+?91[\s-]?)?[6-9]\d{9}\b"),
    _r("bank_details_request", 0.35, "Asks for bank details, card number or net-banking login.",
       r"\b(send|share|submit|enter|provide)\b.{0,40}\b(bank details|account number|card details|card number|net ?banking|login credentials)\b"),
]

URL_SIGNAL_TEXT = {
    "suspicious_tld": "The link uses a domain ending often used by scammers (like .xyz, .top, .online).",
    "is_shortener": "The link is shortened, which hides where it really goes.",
    "free_hosting": "The link is on a free website-hosting service, not on an official company domain.",
    "brand_in_subdomain_or_path": "The link mentions a well-known brand, but the real website is someone else's.",
    "brand_typosquat": "The website name looks like a famous brand but is spelled slightly differently (look-alike domain).",
    "has_ip": "The link uses a raw IP address instead of a website name.",
    "has_at": "The link contains an '@' symbol, a trick to hide the real destination.",
    "has_punycode": "The link uses special characters that can imitate real letters.",
    "not_https": "The link is not using a secure (https) connection.",
}


def match_rules(text: str) -> list[Rule]:
    return [r for r in RULES if r.pattern.search(text or "")]
