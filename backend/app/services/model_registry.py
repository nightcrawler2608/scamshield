"""Loads trained models once at startup and gives simple predict functions."""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np

from ..config import settings
from ..core.features import url_feature_vector

log = logging.getLogger("scamshield.models")


class ModelRegistry:
    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self.text = None
        self.url = None
        self.transformer = None
        self.versions: dict[str, str] = {}
        self.metrics: dict[str, dict] = {}

    def load(self) -> None:
        text_path = self.model_dir / "text_model.joblib"
        url_path = self.model_dir / "url_model.joblib"
        if text_path.exists():
            bundle = joblib.load(text_path)
            self.text = bundle["pipeline"]
            self.versions["text"] = bundle["version"]
            self.metrics["text"] = bundle.get("metrics", {})
        else:
            log.warning("No text model at %s - run ml/train_text_model.py. Rules only.", text_path)
        if url_path.exists():
            bundle = joblib.load(url_path)
            self.url = bundle["model"]
            self.versions["url"] = bundle["version"]
            self.metrics["url"] = bundle.get("metrics", {})
        else:
            log.warning("No URL model at %s - run ml/train_url_model.py. Rules only.", url_path)
        if settings.use_transformer:
            self._load_transformer()

    def _load_transformer(self) -> None:
        path = self.model_dir / "text_transformer"
        try:
            from transformers import pipeline  # optional heavy dependency
            self.transformer = pipeline("text-classification", model=str(path), tokenizer=str(path),
                                        truncation=True, max_length=128, top_k=None)
            self.versions["text"] = "transformer:" + path.name
        except Exception as exc:  # fall back to TF-IDF model
            log.warning("Transformer not loaded (%s); using TF-IDF model.", exc)

    @property
    def version_string(self) -> str:
        return "|".join(f"{k}={v}" for k, v in sorted(self.versions.items())) or "rules-only"

    def predict_text(self, text: str) -> float | None:
        if self.transformer is not None:
            scores = self.transformer(text)[0]
            return float(next(s["score"] for s in scores if s["label"] in ("LABEL_1", "1")))
        if self.text is None:
            return None
        return float(self.text.predict_proba([text])[0, 1])

    def text_coverage(self, text: str) -> float:
        """Share of the message's words that the text model saw during training (0-1).

        An English-trained model shown a Hindi sentence knows almost none of its words, so its
        score rests on one or two clues (e.g. a number) and is not trustworthy. Low coverage = low trust.
        """
        if self.transformer is not None or self.text is None:
            return 1.0  # the multilingual transformer handles Hindi itself
        word_vec = self.text.named_steps["features"].transformer_list[0][1]
        tokens = [t for t in word_vec.build_analyzer()(text) if " " not in t]  # single words only
        if not tokens:
            return 1.0
        return sum(t in word_vec.vocabulary_ for t in tokens) / len(tokens)

    def predict_urls(self, urls: list[str]) -> list[float] | None:
        """Returns one phishing probability per URL, or None if no URL model is trained."""
        if self.url is None:
            return None
        if not urls:
            return []
        X = np.array([url_feature_vector(u) for u in urls], dtype=np.float32)
        return [float(p) for p in self.url.predict_proba(X)[:, 1]]


registry = ModelRegistry(settings.model_dir)
