"""
Phase 2: turn the messages you collected into clean, redacted train/test files.

    python ml/prepare_real_data.py

Reads   ml/data/collect/*.csv  (your raw batches; never committed - see .gitignore)
Writes  ml/data/real_train.csv  and  ml/data/real_test.csv  (redacted; safe to commit)

Steps: check columns/labels -> redact personal data -> flag rows that still look personal ->
drop exact and near duplicates -> drop anything already in our other datasets -> stable 80/20 split.
Guide: docs/PHASE2_COLLECTION.md
"""
from __future__ import annotations

import hashlib
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.features import normalize_text  # noqa: E402
from app.core.privacy import redact  # noqa: E402

DATA = ROOT / "ml" / "data"
COLLECT = DATA / "collect"
NEAR_DUP = 0.90       # similarity at which two messages count as copies of each other
TEST_SHARE = 5        # 1 in 5 messages -> test set (20%)
MIN_CHARS = 10
COLUMNS = ["text", "label", "kind", "language", "source", "notes"]
KINDS = {
    # scam
    "kyc", "bank_block", "otp", "parcel", "electricity", "challan", "lottery", "job", "investment", "loan",
    "digital_arrest", "mistaken_payment", "family_emergency", "refund", "reward", "free_offer", "sextortion",
    # safe
    "bank_alert", "otp_genuine", "delivery", "recharge", "bill", "personal", "college", "official_warning",
    "promo_genuine",
    "other",
}
LABELS = {"scam": "scam", "1": "scam", "spam": "scam", "safe": "safe", "0": "safe", "ham": "safe"}
LANGS = {"en", "hi", "hinglish"}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
STILL_PERSONAL = re.compile(r"(?<!\d)(?!1800|1860)\d{6,}|@|\b(a/?c|account)\s*(no\.?)?\s*:?\s*\d{4,}", re.I)
# Existing datasets: a collected message that is already in one of these is dropped, so the
# trial/stress test sets stay untouched and nothing leaks between training and testing.
EXISTING = ["seed_messages.csv", "seed_service_messages.csv", "user_trials.csv", "stress_test.csv"]


def key(text: str) -> str:
    """Fingerprint used for duplicates and the split: links, numbers and punctuation ignored."""
    return re.sub(r"[^\wऀ-ॿ ]+", "", normalize_text(text)).strip()


def is_test(k: str) -> bool:
    # Decided by the message itself, not a random shuffle: adding new messages later never
    # moves an old message from train to test (or back).
    return int(hashlib.md5(k.encode("utf-8")).hexdigest(), 16) % TEST_SHARE == 0


def load_batches() -> tuple[pd.DataFrame, list[str]]:
    frames, errors = [], []
    files = sorted(p for p in COLLECT.glob("*.csv") if p.name.upper() != "TEMPLATE.CSV")
    if not files:
        sys.exit(f"No batch files found. Copy {COLLECT / 'TEMPLATE.csv'} to e.g. batch1.csv and fill it in.")
    for path in files:
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            errors.append(f"{path.name}: not UTF-8. In Excel use 'Save As -> CSV UTF-8'.")
            continue
        df.columns = [c.strip().lower() for c in df.columns]
        missing = {"text", "label"} - set(df.columns)
        if missing:
            errors.append(f"{path.name}: missing column(s) {sorted(missing)}")
            continue
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df["file"] = path.name
        df["row"] = df.index + 2  # +2 = header line + 1-based, matches Excel row numbers
        frames.append(df[COLUMNS + ["file", "row"]])
        print(f"  read {path.name}: {len(df)} rows")
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)), errors


def main() -> None:
    print("Reading batches from", COLLECT)
    df, errors = load_batches()
    warnings: list[str] = []
    kept = []
    for r in df.itertuples():
        where = f"{r.file} row {r.row}"
        text = " ".join(str(r.text).split())
        label = LABELS.get(str(r.label).strip().lower())
        if len(text) < MIN_CHARS:
            warnings.append(f"{where}: text empty or too short - skipped")
            continue
        if label is None:
            errors.append(f"{where}: label '{r.label}' must be scam or safe")
            continue
        kind = str(r.kind).strip().lower() or "other"
        if kind not in KINDS:
            warnings.append(f"{where}: unknown kind '{kind}' - saved as 'other'")
            kind = "other"
        lang = str(r.language).strip().lower()
        if lang not in LANGS:
            if lang:
                warnings.append(f"{where}: unknown language '{lang}' - guessed")
            lang = "hi" if DEVANAGARI.search(text) else "en"
        clean = redact(text)
        if STILL_PERSONAL.search(clean.replace("[UPI_ID]", "").replace("[EMAIL]", "")):
            warnings.append(f"{where}: may still contain personal data, check by hand -> {clean[:70]}")
        kept.append({"text": clean, "label": label, "kind": kind, "language": lang,
                     "source": str(r.source).strip().lower() or "unknown", "where": where})

    if errors:
        print("\nERRORS (fix these, then run again):")
        print("\n".join("  - " + e for e in errors))
        sys.exit(1)

    # ---- duplicates -------------------------------------------------------------------------
    existing = set()
    for name in EXISTING:
        p = DATA / name
        if p.exists():
            existing |= {key(t) for t in pd.read_csv(p)["text"].dropna()}
    unique, seen = [], []
    dropped_existing = dropped_dup = conflicts = 0
    for row in kept:
        k = key(row["text"])
        if k in existing:
            dropped_existing += 1
            continue
        twin = next((s for s in seen if s["key"] == k or (
            abs(len(s["key"]) - len(k)) < 0.2 * max(len(k), 1)
            and SequenceMatcher(None, s["key"], k).ratio() >= NEAR_DUP)), None)
        if twin:
            dropped_dup += 1
            if twin["label"] != row["label"]:
                conflicts += 1
                warnings.append(f"{row['where']}: same message as {twin['where']} but labelled differently "
                                f"({row['label']} vs {twin['label']}) - kept the first, please check")
            continue
        row["key"] = k
        seen.append(row)
        unique.append(row)

    out = pd.DataFrame(unique, columns=["key", "text", "label", "kind", "language", "source"])
    if out.empty:
        sys.exit("Nothing left after cleaning.")
    out.insert(0, "id", ["R" + hashlib.md5(k.encode("utf-8")).hexdigest()[:8] for k in out["key"]])
    out["split"] = ["test" if is_test(k) else "train" for k in out["key"]]
    cols = ["id", "text", "label", "kind", "language", "source"]
    train, test = out[out.split == "train"][cols], out[out.split == "test"][cols]
    train.to_csv(DATA / "real_train.csv", index=False, encoding="utf-8")
    test.to_csv(DATA / "real_test.csv", index=False, encoding="utf-8")

    # ---- report -----------------------------------------------------------------------------
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        print("\n".join("  - " + w for w in warnings))
    print(f"\nRead {len(df)} rows -> kept {len(out)} "
          f"(dropped {dropped_dup} duplicates, {dropped_existing} already in our datasets)")
    print(f"Saved ml/data/real_train.csv ({len(train)}) and ml/data/real_test.csv ({len(test)})\n")
    print(pd.crosstab(out["language"], [out["split"], out["label"]], margins=True).to_string())
    print("\nBy kind:\n" + out.groupby(["label", "kind"]).size().to_string())

    # what to collect next
    tips = []
    if len(out) < 200:
        tips.append(f"{200 - len(out)} more messages to reach the 200 target")
    for lab in ("scam", "safe"):
        if (out.label == lab).sum() < 0.35 * len(out):
            tips.append(f"more {lab} messages (only {(out.label == lab).mean():.0%})")
    if (out.language != "en").mean() < 0.4:
        tips.append("more Hindi / Hinglish messages (under 40%)")
    if not ((out.label == "safe") & out.kind.isin(["bank_alert", "otp_genuine", "delivery"])).any():
        tips.append("genuine bank alerts / OTPs / delivery SMS (the hard 'safe' cases)")
    if test.label.nunique() < 2:
        tips.append("test set has only one class - collect more so both appear")
    if tips:
        print("\nCollect next: " + "; ".join(tips))


if __name__ == "__main__":
    main()
