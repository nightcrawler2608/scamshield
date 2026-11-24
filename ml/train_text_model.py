"""
Step 2: train the TEXT scam classifier.

Model: TF-IDF (word 1-2 grams + character 2-5 grams) -> Logistic Regression.
  * word n-grams learn phrases like "kyc update", "claim prize"
  * char n-grams handle spelling tricks ("fr33", "acc0unt") and Hinglish

Run:  python ml/train_text_model.py
Output: models/text_model.joblib, models/text_metrics.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.features import normalize_text  # noqa: E402  (shared with the backend)
from app.core.privacy import fill_placeholders  # noqa: E402

DATA = ROOT / "ml" / "data"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)
SEED_WEIGHT = 3.0  # hand-written Indian scam examples are rare, so give them more weight
WEIGHTED = ["seed", "real"]  # Indian-context sources that get SEED_WEIGHT


def load_real(path: Path) -> pd.DataFrame:
    """Redacted collected messages -> model input. [PHONE] etc. become dummy values like the real
    thing, so the model sees the same kind of text it will see live (no training-serving skew)."""
    r = pd.read_csv(path, dtype=str, keep_default_na=False)
    r["text"] = r["text"].map(fill_placeholders)
    r["label"] = (r["label"] == "scam").astype(int)
    return r


def load_data() -> pd.DataFrame:
    sms = pd.read_csv(DATA / "raw" / "sms_spam" / "SMSSpamCollection", sep="\t", header=None,
                      names=["label", "text"], quoting=3, encoding="utf-8")
    sms["label"] = (sms["label"] == "spam").astype(int)
    sms["source"] = "uci_sms"

    # The UCI "spam" class is mostly company/promotional SMS and its "ham" class is personal chat,
    # so on its own the model learns "sounds like a company = scam" and flags real bank alerts,
    # OTPs and delivery updates. seed_service_messages.csv adds genuine service SMS (label 0)
    # next to company-style scams (label 1) so the model must learn what the message ASKS for.
    seed = pd.concat([pd.read_csv(DATA / "seed_messages.csv"),
                      pd.read_csv(DATA / "seed_service_messages.csv")], ignore_index=True)
    seed["source"] = "seed"

    frames = [sms, seed]
    real = DATA / "real_train.csv"  # optional: Phase 2 collected messages (ml/prepare_real_data.py)
    if real.exists():
        r = load_real(real)
        r["source"] = "real"
        frames.append(r[["text", "label", "source"]])
        print(f"Including {len(r)} real collected messages")
    fb = DATA / "feedback_export.csv"  # optional: produced by ml/export_feedback.py
    if fb.exists():
        f = pd.read_csv(fb)
        f["text"] = f["text"].map(fill_placeholders)  # stored text is redacted
        f["source"] = "feedback"
        frames.append(f)
        print(f"Including {len(f)} rows of user feedback")

    df = pd.concat(frames, ignore_index=True).dropna(subset=["text"])
    df = df.drop_duplicates(subset=["text"])
    return df


def build_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("word", TfidfVectorizer(preprocessor=normalize_text, ngram_range=(1, 2), min_df=2,
                                 max_features=30000, sublinear_tf=True)),
        ("char", TfidfVectorizer(preprocessor=normalize_text, analyzer="char_wb", ngram_range=(2, 5),
                                 min_df=3, max_features=40000, sublinear_tf=True)),
    ])
    clf = LogisticRegression(C=8.0, class_weight="balanced", max_iter=3000)
    return Pipeline([("features", features), ("clf", clf)])


def main() -> None:
    df = load_data()
    print(f"Rows: {len(df)} | scam ratio: {df.label.mean():.2%}")
    print(df.groupby("source").label.agg(["count", "mean"]))

    train, test = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])
    weights = np.where(train["source"].isin(WEIGHTED), SEED_WEIGHT, 1.0)

    pipe = build_pipeline()
    pipe.fit(train["text"], train["label"], clf__sample_weight=weights)

    proba = pipe.predict_proba(test["text"])[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "model": "tfidf_word_char+logreg",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_train": int(len(train)), "n_test": int(len(test)),
        "precision": round(precision_score(test.label, pred), 4),
        "recall": round(recall_score(test.label, pred), 4),
        "f1": round(f1_score(test.label, pred), 4),
        "roc_auc": round(roc_auc_score(test.label, proba), 4),
        "confusion_matrix": confusion_matrix(test.label, pred).tolist(),
    }
    seed_test = test[test.source == "seed"]
    if len(seed_test) and seed_test.label.nunique() == 2:
        sp = pipe.predict(seed_test["text"])
        metrics["seed_subset_f1"] = round(f1_score(seed_test.label, sp), 4)
    real_test_path = DATA / "real_test.csv"  # Phase 2 held-out set: never in df, never trained on
    if real_test_path.exists():
        rt = load_real(real_test_path)
        if len(rt) and rt.label.nunique() == 2:
            rp = pipe.predict(rt["text"])
            metrics["real_test"] = {"n": int(len(rt)),
                                    "precision": round(precision_score(rt.label, rp), 4),
                                    "recall": round(recall_score(rt.label, rp), 4),
                                    "f1": round(f1_score(rt.label, rp), 4)}

    print(classification_report(test.label, pred, target_names=["safe", "scam"], digits=4))
    print(json.dumps(metrics, indent=2))

    # Retrain on ALL data for the final model we ship (metrics above are from the held-out split).
    final = build_pipeline()
    final.fit(df["text"], df["label"],
              clf__sample_weight=np.where(df["source"].isin(WEIGHTED), SEED_WEIGHT, 1.0))

    version = "text-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    joblib.dump({"pipeline": final, "version": version, "metrics": metrics},
                MODELS / "text_model.joblib", compress=3)
    (MODELS / "text_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved models/text_model.joblib ({version})")


if __name__ == "__main__":
    main()
