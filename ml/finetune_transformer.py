"""
OPTIONAL UPGRADE (run on free Google Colab GPU): fine-tune a multilingual transformer.

Why: TF-IDF only sees words; a transformer understands meaning and works across
English, Hindi and Hinglish. Use this in your report as "Model v2" and compare
its F1 with the TF-IDF baseline -> that comparison is great for your viva.

How to run on Colab (free):
  1. Upload this repo (or `git clone` it) in Colab, Runtime -> Change runtime type -> T4 GPU
  2. !pip install transformers datasets accelerate scikit-learn pandas tldextract
  3. !python ml/download_data.py
  4. !python ml/finetune_transformer.py
  5. Download the folder models/text_transformer/ and put it in your repo's models/ folder.
     The backend uses it automatically if `transformers` + `torch` are installed
     (set USE_TRANSFORMER=true). Otherwise it uses the TF-IDF model.

Default model: distilbert-base-multilingual-cased (small, fast, supports Hindi).
Try "google/muril-base-cased" for better Indian-language accuracy (slower).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
from train_text_model import load_data  # noqa: E402  (same data as the baseline = fair comparison)

MODEL_NAME = "distilbert-base-multilingual-cased"
OUT = ROOT / "models" / "text_transformer"


def main() -> None:
    import torch
    from datasets import Dataset
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, Trainer,
                              TrainingArguments)

    df = load_data()
    train, test = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)

    def encode(frame: pd.DataFrame) -> Dataset:
        ds = Dataset.from_pandas(frame[["text", "label"]].reset_index(drop=True))
        return ds.map(lambda b: tok(b["text"], truncation=True, max_length=128, padding="max_length"),
                      batched=True)

    train_ds, test_ds = encode(train), encode(test)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    def compute_metrics(p):
        preds = np.argmax(p.predictions, axis=1)
        return {"f1": f1_score(p.label_ids, preds), "precision": precision_score(p.label_ids, preds),
                "recall": recall_score(p.label_ids, preds)}

    args = TrainingArguments(output_dir=str(ROOT / "ml" / "runs"), num_train_epochs=3,
                             per_device_train_batch_size=32, per_device_eval_batch_size=64,
                             learning_rate=3e-5, eval_strategy="epoch", save_strategy="no",
                             fp16=torch.cuda.is_available(), report_to=[])
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=test_ds,
                      compute_metrics=compute_metrics)
    trainer.train()
    metrics = trainer.evaluate()
    print(json.dumps(metrics, indent=2))

    OUT.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUT))
    tok.save_pretrained(str(OUT))
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
