"""
Step 4 (MLOps loop): export user feedback from the database into a training CSV.

Each feedback row says whether our verdict was right. We turn that into a label:
  * user said "correct"   -> keep our verdict (scam/suspicious -> 1, safe -> 0)
  * user said "wrong"     -> use correct_label if given, else flip our verdict

Run:  python ml/export_feedback.py      (uses DATABASE_URL from .env, same as the backend)
Then: python ml/train_text_model.py     (automatically includes ml/data/feedback_export.csv)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.db import SessionLocal  # noqa: E402
from app.models import Analysis, Feedback  # noqa: E402


def main() -> None:
    rows = []
    with SessionLocal() as db:
        q = db.query(Analysis, Feedback).join(Feedback, Feedback.analysis_id == Analysis.id)
        for a, f in q:
            if a.input_type == "url":
                continue  # URL feedback would retrain the URL model; kept simple here
            ours = 0 if a.verdict == "safe" else 1
            if f.is_correct:
                label = ours
            elif f.correct_label in ("scam", "safe"):
                label = 1 if f.correct_label == "scam" else 0
            else:
                label = 1 - ours
            rows.append({"text": a.redacted_input, "label": label})
    out = ROOT / "ml" / "data" / "feedback_export.csv"
    pd.DataFrame(rows, columns=["text", "label"]).drop_duplicates().to_csv(out, index=False)
    print(f"Exported {len(rows)} feedback rows to {out}")


if __name__ == "__main__":
    main()
