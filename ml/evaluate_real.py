"""
Phase 2: measure the CURRENT model on the held-out real test set, and compare runs.

    python ml/evaluate_real.py --tag before           # run BEFORE retraining on real data
    python ml/train_text_model.py
    python ml/evaluate_real.py --tag after
    python ml/evaluate_real.py --compare before after # table for the report

Saves docs/results/real_eval_<tag>.json (metrics + per-message verdicts, no raw personal data).
"Correct" is the same as in stress_test.py: scam -> SCAM or SUSPICIOUS, safe -> SAFE.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["LLM_API_KEY"] = ""  # evaluation never calls the external LLM

from app.core.privacy import fill_placeholders  # noqa: E402
from app.services.analyzer import analyze  # noqa: E402
from app.services.model_registry import registry  # noqa: E402

TEST = ROOT / "ml" / "data" / "real_test.csv"
RESULTS = ROOT / "docs" / "results"


def is_correct(label: str, verdict: str) -> bool:
    return verdict == "safe" if label == "safe" else verdict in ("scam", "suspicious")


def summarise(df: pd.DataFrame) -> dict:
    scam, safe = df[df.label == "scam"], df[df.label == "safe"]
    out = {
        "n": int(len(df)), "n_scam": int(len(scam)), "n_safe": int(len(safe)),
        "accuracy": round(df.correct.mean(), 4) if len(df) else None,
        "scams_caught": round(scam.correct.mean(), 4) if len(scam) else None,
        "false_alarm_rate": round(1 - safe.correct.mean(), 4) if len(safe) else None,
    }
    if df.label.nunique() == 2:  # text model on its own, threshold 0.5
        y, p = (df.label == "scam").astype(int), (df.text_score >= 0.5).astype(int)
        out.update(text_precision=round(precision_score(y, p, zero_division=0), 4),
                   text_recall=round(recall_score(y, p, zero_division=0), 4),
                   text_f1=round(f1_score(y, p, zero_division=0), 4))
    return out


async def evaluate(tag: str) -> None:
    if not TEST.exists():
        sys.exit("ml/data/real_test.csv not found - run python ml/prepare_real_data.py first")
    registry.load()
    df = pd.read_csv(TEST, dtype=str, keep_default_na=False)
    verdicts, risks, text_scores = [], [], []
    for text in df["text"]:
        r = await analyze(fill_placeholders(text))  # dummy values back in place of [PHONE] etc.
        verdicts.append(r.verdict)
        risks.append(r.risk_score)
        text_scores.append(r.text_score or 0.0)
    df["verdict"], df["risk"], df["text_score"] = verdicts, risks, text_scores
    df["correct"] = [is_correct(lab, v) for lab, v in zip(df.label, df.verdict)]

    result = {
        "tag": tag, "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": registry.version_string,
        "overall": summarise(df),
        "by_language": {lang: summarise(g) for lang, g in df.groupby("language")},
        "messages": df[["id", "label", "kind", "language", "verdict", "risk", "correct"]].to_dict("records"),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"real_eval_{tag}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    o = result["overall"]
    print(f"Model {result['model_version']} on {o['n']} held-out real messages")
    print(f"  accuracy {o['accuracy']:.1%} | scams caught {o['scams_caught'] or 0:.1%} | "
          f"false alarms {o['false_alarm_rate'] or 0:.1%} | text-model F1 {o.get('text_f1', '-')}")
    for lang, s in result["by_language"].items():
        print(f"  {lang:9} n={s['n']:<4} accuracy {s['accuracy']:.1%}")
    wrong = df[~df.correct]
    if len(wrong):
        print("\nWrong:")
        for r in wrong.itertuples():
            print(f"  {r.id} {r.label:4} -> {r.verdict:10} {r.risk:.0%}  [{r.kind}, {r.language}] {r.text[:60]}")
    print(f"\nSaved {path.relative_to(ROOT)}")


def compare(a: str, b: str) -> None:
    ra, rb = (json.loads((RESULTS / f"real_eval_{t}.json").read_text(encoding="utf-8")) for t in (a, b))
    if [m["id"] for m in ra["messages"]] != [m["id"] for m in rb["messages"]]:
        print("WARNING: the two runs used different test sets - the comparison is not fair.\n")

    def pct(v):
        return "-" if v is None else f"{v:.1%}"

    rows = [("Accuracy (full system)", "accuracy"), ("Scams caught", "scams_caught"),
            ("False alarm rate (lower is better)", "false_alarm_rate"),
            ("Text model precision", "text_precision"), ("Text model recall", "text_recall"),
            ("Text model F1", "text_f1")]
    print(f"| Metric | {a} | {b} |\n|---|---|---|")
    for name, k in rows:
        print(f"| {name} | {pct(ra['overall'].get(k))} | {pct(rb['overall'].get(k))} |")
    for lang in sorted(set(ra["by_language"]) | set(rb["by_language"])):
        sa, sb = ra["by_language"].get(lang, {}), rb["by_language"].get(lang, {})
        print(f"| Accuracy – {lang} (n={sb.get('n', sa.get('n'))}) | {pct(sa.get('accuracy'))} | "
              f"{pct(sb.get('accuracy'))} |")
    print(f"\nModels: {a} = {ra['model_version']}, {b} = {rb['model_version']}")

    before = {m["id"]: m for m in ra["messages"]}
    fixed = [m for m in rb["messages"] if m["correct"] and not before.get(m["id"], m)["correct"]]
    broke = [m for m in rb["messages"] if not m["correct"] and before.get(m["id"], m)["correct"]]
    print(f"Fixed by {b}: {len(fixed)}  {[m['id'] for m in fixed]}")
    print(f"Broken by {b}: {len(broke)}  {[m['id'] for m in broke]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", help="name for this run, e.g. before / after / v2")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="compare two saved runs")
    args = ap.parse_args()
    if args.compare:
        compare(*args.compare)
    elif args.tag:
        asyncio.run(evaluate(args.tag))
    else:
        ap.print_help()
