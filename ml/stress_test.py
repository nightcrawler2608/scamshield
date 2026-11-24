"""
Runs a hand-written set of tricky messages through the full ScamShield pipeline
(models + rules + fusion) and prints what it got right and wrong.

    python ml/stress_test.py                     # uses ml/data/stress_test.csv
    python ml/stress_test.py my_messages.csv     # any CSV with columns: label,text (label = scam/safe)

"Correct" means: scam -> SCAM or SUSPICIOUS, safe -> SAFE.
"""
from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.analyzer import analyze  # noqa: E402
from app.services.model_registry import registry  # noqa: E402


def is_correct(label: str, verdict: str) -> bool:
    return verdict == "safe" if label == "safe" else verdict in ("scam", "suspicious")


async def main(path: Path) -> None:
    registry.load()
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    wrong = 0
    print(f"{'#':>3} {'label':5} {'verdict':10} {'risk':>5} {'text':>5} {'url':>5}  ok  kind / rules")
    for i, row in enumerate(rows, 1):
        r = await analyze(row["text"])
        ok = is_correct(row["label"], r.verdict)
        wrong += not ok
        rules = len([x for x in r.reasons])
        url = "-" if r.url_score is None else f"{r.url_score:.2f}"
        print(f"{row.get('id', i):>3} {row['label']:5} {r.verdict:10} {r.risk_score:5.2f} {r.text_score:5.2f} {url:>5}  "
              f"{'OK ' if ok else 'XX '} {row.get('kind', '')} ({rules} reasons)")
    print(f"\n{len(rows) - wrong}/{len(rows)} correct")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "ml" / "data" / "stress_test.csv"))
