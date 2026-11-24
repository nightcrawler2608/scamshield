"""
Step 3: train the URL (link) phishing classifier.

Data:
  * UCI PhiUSIIL  (label 0 = phishing, 1 = legitimate  -> we flip it so 1 = phishing)
  * OpenPhish live feed (all phishing)
  * A few official brand URLs (legitimate) so the model learns "real brand domain = fine"

Bias fix (data augmentation): most PhiUSIIL legitimate URLs are bare home pages,
so a naive model learns "any path = phishing". We add realistic paths to ~40% of
legitimate URLs so the model must use better signals.

Model: XGBoost on 32 hand-made features (see backend/app/core/features.py).

Run:  python ml/train_url_model.py
Output: models/url_model.joblib, models/url_metrics.json
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.features import URL_FEATURE_NAMES, url_feature_vector  # noqa: E402

RAW = ROOT / "ml" / "data" / "raw"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)
random.seed(42)

LEGIT_PATHS = [
    "/login", "/signin", "/account", "/account/settings", "/about", "/contact", "/products",
    "/products/item?id=1024", "/blog/2024/05/how-we-build", "/search?q=shoes&page=2",
    "/help/faq", "/en-in/", "/news/latest", "/docs/getting-started", "/cart", "/checkout",
    "/user/profile", "/careers", "/privacy-policy", "/category/electronics/mobiles",
]
OFFICIAL_URLS = [
    "https://www.onlinesbi.sbi/", "https://retail.onlinesbi.sbi/retail/login.htm",
    "https://www.hdfcbank.com/personal/pay/cards", "https://www.icicibank.com/personal-banking",
    "https://www.amazon.in/gp/css/order-history", "https://www.flipkart.com/account/orders",
    "https://accounts.google.com/signin", "https://www.paypal.com/signin",
    "https://www.netflix.com/login", "https://www.irctc.co.in/nget/train-search",
    "https://uidai.gov.in/en/my-aadhaar/update-aadhaar.html", "https://www.incometax.gov.in/iec/foportal/",
    "https://www.epfindia.gov.in/site_en/index.php", "https://www.paytm.com/recharge",
    "https://www.phonepe.com/business-solutions/", "https://www.airtel.in/prepaid-recharge",
    "https://www.jio.com/selfcare/plans/mobility/prepaid-plans-home/", "https://web.whatsapp.com/",
    "https://www.instagram.com/accounts/login/", "https://www.facebook.com/login/",
    "https://login.microsoftonline.com/", "https://outlook.live.com/mail/",
    "https://store.steampowered.com/", "https://steamcommunity.com/market/",
    "https://www.indiapost.gov.in/vas/Pages/IndiaPostHome.aspx", "https://github.com/login",
]


def load() -> pd.DataFrame:
    phi = pd.read_csv(RAW / "phiusiil" / "PhiUSIIL_Phishing_URL_Dataset.csv", usecols=["URL", "label"])
    phi = phi.rename(columns={"URL": "url"})
    phi["label"] = 1 - phi["label"]  # now 1 = phishing

    legit = phi["label"] == 0
    idx = phi[legit].sample(frac=0.4, random_state=42).index
    phi.loc[idx, "url"] = phi.loc[idx, "url"].str.rstrip("/") + [random.choice(LEGIT_PATHS) for _ in idx]

    # Bias fix #2: in PhiUSIIL 100% of legitimate URLs are https but only ~49% of phishing
    # URLs are. A model would learn "http = phishing" and miss modern https phishing sites.
    # We randomise the scheme (50/50) for every row so the model must learn real signals.
    # (The rule engine still adds a small risk bump for plain http.)
    phi["url"] = [("https://" if random.random() < 0.5 else "http://") + u.split("://", 1)[-1]
                  for u in phi["url"]]

    frames = [phi]
    op = RAW / "openphish.txt"
    if op.exists():
        urls = [u.strip() for u in op.read_text(encoding="utf-8", errors="ignore").splitlines() if u.strip()]
        frames.append(pd.DataFrame({"url": urls, "label": 1}))
    frames.append(pd.DataFrame({"url": OFFICIAL_URLS * 20, "label": 0}))  # repeated = upweighted
    df = pd.concat(frames, ignore_index=True)
    return df


def main() -> None:
    df = load()
    print(f"Rows: {len(df)} | phishing ratio: {df.label.mean():.2%}")
    print("Computing features ...")
    X = np.array([url_feature_vector(u) for u in df["url"]], dtype=np.float32)
    y = df["label"].to_numpy()

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    params = dict(n_estimators=400, max_depth=7, learning_rate=0.08, subsample=0.9,
                  colsample_bytree=0.8, eval_metric="logloss", n_jobs=-1, random_state=42)
    model = XGBClassifier(**params)
    model.fit(X_tr, y_tr)

    proba = model.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "model": "xgboost_url_features",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
        "precision": round(precision_score(y_te, pred), 4),
        "recall": round(recall_score(y_te, pred), 4),
        "f1": round(f1_score(y_te, pred), 4),
        "roc_auc": round(roc_auc_score(y_te, proba), 4),
        "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
        "top_features": sorted(zip(URL_FEATURE_NAMES, map(float, model.feature_importances_)),
                               key=lambda t: -t[1])[:10],
    }
    print(classification_report(y_te, pred, target_names=["legit", "phishing"], digits=4))
    print(json.dumps(metrics, indent=2))

    final = XGBClassifier(**params)
    final.fit(X, y)
    version = "url-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    joblib.dump({"model": final, "feature_names": URL_FEATURE_NAMES, "version": version, "metrics": metrics},
                MODELS / "url_model.joblib", compress=3)
    (MODELS / "url_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved models/url_model.joblib ({version})")


if __name__ == "__main__":
    main()
