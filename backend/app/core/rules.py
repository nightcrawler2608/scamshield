"""
Rule engine: well-known scam tricks, written as regex patterns (English, Hinglish and Hindi script).

Why rules if we have ML?  A brand-new scam can appear tomorrow; a rule catches it
on day one, while the model needs data. Rules also give clear, human reasons.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Rule:
    id: str
    weight: float  # how strongly this pushes the score towards "scam" (0-1)
    reason: str
    pattern: re.Pattern
    needs_you: bool = False  # only counts if the message is addressed to the reader ("your", "aapka")


def _r(id_: str, weight: float, reason: str, *patterns: str, needs_you: bool = False) -> Rule:
    return Rule(id_, weight, reason, re.compile("|".join(patterns), re.I), needs_you)


# Scams threaten YOUR account. "Mera account block ho gaya" (someone talking about their own
# account) is not a threat, so rules marked needs_you only count when the reader is addressed.
YOU = re.compile(r"\b(you|your|yours|aap|aapka|aapke|aapki|apka|apke|apki|apna|apne|tumhara|tumhare|tera|tere)\b"
                 r"|आप|अपना|अपने|तुम्हारा|तेरा", re.I)


RULES: list[Rule] = [
    _r("otp_request", 0.45, "Asks you to share an OTP, PIN, CVV or password. Real banks and companies never ask for these.",
       r"(share|send|tell|batao|batayein|bhejo|give|provide|reply with|enter)\b.{0,40}\b(otp|pin|cvv|password|card number)",
       r"\b(otp|cvv|pin)\b.{0,30}\b(share|batao|batayein|bhejo|executive|agent)"),
    _r("account_block", 0.30, "Threatens that your account, card, SIM or connection will be blocked or suspended.",
       r"\b(block(ed)?|suspend(ed)?|deactivat\w*|disconnect\w*|band ho|kaat|expire[sd]?|locked|terminated)\b.{0,60}\b(account|card|sim|number|connection|kyc|service|khata)",
       r"\b(account|card|sim|number|connection|kyc|khata)\b.{0,60}\b(block(ed)?|suspend(ed)?|deactivat\w*|disconnect\w*|band ho|kaat|locked)", needs_you=True),
    _r("kyc_update", 0.30, "Asks you to update KYC / PAN / Aadhaar through a message or link.",
       r"\b(kyc|pan card|aadhaar|aadhar)\b.{0,40}\b(update|link|verify|pending|incomplete|expire)",
       r"\b(update|verify|link)\b.{0,30}\b(kyc|pan|aadhaar|aadhar)\b", needs_you=True),
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
       r"\b(new number|lost my phone|changed my number)\b.{0,80}\b(send|transfer|need)\b",
       r"\b(naya number|number badal (gaya|liya)|phone (kho|gir|toot) gaya)\b.{0,80}\b(bhej\w*|send|transfer|paise|zarurat|urgent)\b",
       r"\b(bhej\w*|send|transfer)\b.{0,100}\b(naya number|new number)\b"),
    _r("mistaken_payment", 0.40, "Claims money was sent to you 'by mistake' and asks you to send it back. This is a common trick: the first payment is often fake, or a collect request.",
       r"\b(by mistake|mistakenly|wrongly|accidentally|galti se|galati se)\b.{0,100}\b(send (it |the money )?back|return|refund|wapas|vapas)\b"),
    _r("remote_access_app", 0.40, "Asks you to install a screen-sharing app or an APK file, which can give scammers control of your phone.",
       r"\b(anydesk|teamviewer|quick ?support|rustdesk)\b", r"\.apk\b"),
    _r("call_unknown_number", 0.15, "Pushes you to call or WhatsApp an unknown personal number instead of an official helpline.",
       # (?<!\d) stops a toll-free number like 18002586161 from matching on its last 10 digits
       r"\b(call|contact|whatsapp|message)\b.{0,30}(?<!\d)(\+?91[\s-]?)?[6-9]\d{9}\b"),
    _r("bank_details_request", 0.35, "Asks for bank details, card number or net-banking login.",
       r"\b(send|share|submit|enter|provide)\b.{0,40}\b(bank details|account number|card details|card number|net ?banking|login credentials)\b"),
]

# ---------- Hindi (Devanagari script) patterns ----------
# Scammers also write fully in Hindi. These patterns are added to the rules above.
# No \b here: Python treats Hindi vowel signs (like ा, े) as non-word characters,
# so word boundaries would break in the middle of Hindi words.
HI_SECRET = r"(OTP|ओटीपी|पिन|सीवीवी|CVV|पासवर्ड)"
HI_TELL = r"(बताएं|बताएँ|बताइए|बताओ|बताये|बतायें|शेयर|भेजें|भेजो|भेजिए|दें|दीजिए)"
HI_ACCOUNT = r"(खाता|खाते|अकाउंट|कार्ड|सिम|कनेक्शन|बिजली|नंबर|केवाईसी|KYC)"
HI_BLOCKED = r"(बंद|ब्लॉक|निलंबित|सस्पेंड|काट)"

HINDI_PATTERNS: dict[str, list[str]] = {
    "otp_request": [HI_SECRET + r".{0,30}" + HI_TELL, r"(बताएं|शेयर करें|भेजें).{0,30}" + HI_SECRET],
    "account_block": [HI_ACCOUNT + r".{0,40}" + HI_BLOCKED, HI_BLOCKED + r".{0,40}" + HI_ACCOUNT],
    "kyc_update": [r"(केवाईसी|KYC|पैन|आधार).{0,40}(अपडेट|लिंक|सत्यापित|वेरिफाई|अधूरा|अधूरी|लंबित)"],
    "urgency": [r"(तुरंत|तुरन्त|फौरन|फ़ौरन|जल्द से जल्द|आज ही|आज रात|घंटे के अंदर|घंटों में|अंतिम चेतावनी|अंतिम मौका)"],
    "prize_lottery": [r"(लॉटरी|इनाम|ईनाम|पुरस्कार|लकी ड्रॉ|केबीसी|जीत लिए|जीते हैं|जीता है|आपने जीता)"],
    "advance_fee": [r"(शुल्क|फीस|फ़ीस|चार्ज|जीएसटी|टैक्स).{0,30}(जमा|भुगतान|भरें|पे करें)",
                    r"(जमा करें|भुगतान करें).{0,30}(शुल्क|फीस|फ़ीस|चार्ज)",
                    r"(पंजीकरण|रजिस्ट्रेशन|प्रोसेसिंग) (शुल्क|फीस|फ़ीस)"],
    "job_task_scam": [r"(कमाएं|कमाएँ|कमाइए|कमाओ|कमाई).{0,40}(प्रतिदिन|प्रति दिन|रोज़|रोज|हर दिन|घर बैठे)",
                      r"(पार्ट टाइम जॉब|घर बैठे काम|वर्क फ्रॉम होम|टेलीग्राम टास्क)"],
    "upi_collect": [r"(कलेक्ट रिक्वेस्ट|पेमेंट रिक्वेस्ट).{0,30}(स्वीकार|अप्रूव)",
                    r"(QR|क्यूआर).{0,30}स्कैन.{0,40}(पैसे|कैशबैक|रिफंड|प्राप्त)"],
    "authority_threat": [r"(डिजिटल अरेस्ट|डिजिटल गिरफ्तारी|गिरफ्तार|गिरफ़्तार|सीबीआई|मनी लॉन्ड्रिंग|कानूनी कार्रवाई|अरेस्ट वारंट|नशीले पदार्थ)"],
    "investment_promise": [r"(गारंटी|गारंटीड|100%).{0,30}(मुनाफा|मुनाफ़ा|रिटर्न|लाभ)", r"(पैसा|पैसे|रकम) (दोगुना|डबल)"],
    "family_emergency": [r"(नया नंबर|फोन खो गया|फ़ोन खो गया|नंबर बदल).{0,80}(भेज|ट्रांसफर|पैसे|ज़रूरत|जरूरत)"],
    "remote_access_app": [r"(एनीडेस्क|टीमव्यूअर)"],
    "mistaken_payment": [r"(गलती से|ग़लती से).{0,100}(वापस)"],
    "call_unknown_number": [r"(कॉल|संपर्क|व्हाट्सएप).{0,30}(?<!\d)(\+?91[\s-]?)?[6-9]\d{9}"],
    "bank_details_request": [r"(खाता संख्या|अकाउंट नंबर|कार्ड नंबर|बैंक विवरण|नेट ?बैंकिंग).{0,40}(भेजें|बताएं|शेयर|दें|दर्ज)"],
}

RULES = [
    replace(r, pattern=re.compile(r.pattern.pattern + "|" + "|".join(HINDI_PATTERNS[r.id]), re.I))
    if r.id in HINDI_PATTERNS else r
    for r in RULES
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


# Safety warnings ("never share your OTP", "OTP किसी को न बताएं") are what GENUINE banks send.
# We blank out those clauses before matching, so the warning itself doesn't trigger the OTP rule.
# A scam that also says "share it with our executive" is still caught by the rest of the text.
SAFETY_WARNING = re.compile(
    # the clause stops at . ! , or before "but / except / only", where a scam can continue
    r"\b(never|do not|don't|dont|not to)\s+(share|disclose|tell|give|reveal)\b(?:(?!\b(?:but|except|only)\b)[^.!,\n])*"
    r"|(OTP|ओटीपी|पिन|पासवर्ड)[^।.!\n]{0,40}(न करें|ना करें|न दें|न बताएं|मत)",
    re.I)


def match_rules(text: str) -> list[Rule]:
    text = SAFETY_WARNING.sub(" ", text or "")
    addressed_to_you = bool(YOU.search(text))
    return [r for r in RULES if r.pattern.search(text) and (addressed_to_you or not r.needs_you)]
