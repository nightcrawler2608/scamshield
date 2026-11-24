# ScamShield – Architecture, Data Flow & Database

## 1. Big picture (one sentence)
A user sends a message / link / screenshot → our API runs **our own trained ML models** + **safety rules** → combines them into a **risk score** → an **LLM writes a simple explanation** → result is shown and saved (privacy-redacted) → user feedback is used to **retrain** the models.

## 2. System architecture

```
                         ┌─────────────────────────────────────────────┐
   CLIENTS               │            BACKEND  (FastAPI, Docker)         │
 ┌──────────────┐  HTTPS │                                              │
 │ Web app      │───────▶│  /api/analyze/text   ┌──────────────────────┐ │
 │ (HTML/JS)    │        │  /api/analyze/url    │ Analyzer (orchestr.) │ │
 ├──────────────┤        │  /api/analyze/image  │                      │ │
 │ Telegram bot │───────▶│  /api/feedback       │ 1. OCR (image→text)  │ │
 ├──────────────┤        │  /api/stats          │ 2. URL extractor     │ │
 │ Chrome ext.  │───────▶│  /api/health         │ 3. Text model  (ML)  │ │
 └──────────────┘        │                      │ 4. URL model   (ML)  │ │
                         │                      │ 5. Rule engine       │ │
                         │                      │ 6. Score fusion      │ │
                         │                      │ 7. LLM explainer ────┼─┼──▶ Free LLM API
                         │                      │    (fallback: template)│ │   (Groq / Gemini,
                         │                      └──────────┬───────────┘ │    optional)
                         │                                 │ redact PII   │
                         └─────────────────────────────────┼─────────────┘
                                                           ▼
                                          ┌──────────────────────────────┐
                                          │ Database (SQLAlchemy)         │
                                          │  local: SQLite                │
                                          │  live : Supabase Postgres     │
                                          │  tables: analyses, feedback,  │
                                          │          model_versions       │
                                          └──────────────┬───────────────┘
                                                         │ export labelled feedback
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │ ML pipeline (offline, Colab)  │
                                          │ download → train → evaluate   │
                                          │ → save models/*.joblib        │
                                          │ → redeploy                    │
                                          └──────────────────────────────┘
```

### Why this design?
| Decision | Reason |
|---|---|
| **Our model decides, the LLM only explains** | Shows real ML work, cheap, fast, and still works if the LLM is down. |
| **Rules + ML fusion** | ML catches patterns from data; rules catch new, obvious tricks ("share your OTP") on day one. |
| **One Docker container** | Free hosting (Hugging Face Spaces) runs a single container. Easy to deploy. |
| **SQLAlchemy** | Same code works for SQLite (laptop) and Postgres (Supabase, live). |
| **PII redaction before saving** | Users paste private messages. We never store phone numbers, emails, OTPs or account numbers. |

## 3. Data flow (step by step for one request)

1. **Input** – the user pastes text (or a link or a screenshot) into the web app, bot or extension.
2. **OCR** (images only) – Tesseract turns the screenshot into text.
3. **URL extraction** – a regex finds every link in the text.
4. **Text model** – TF‑IDF (words + characters) → Logistic Regression → `p_text` (0–1).
   *Upgrade:* a fine‑tuned multilingual transformer (see `ml/finetune_transformer.py`).
5. **URL model** – 30+ hand‑made features per link (length, digits, `@`, IP address, odd TLD,
   look‑alike brand names, entropy…) → XGBoost → `p_url` (0–1).
6. **Rule engine** – checks for known scam signals (OTP request, urgency, KYC/account block,
   lottery/prize, pay‑to‑get‑a‑job, UPI collect request, shortened links, Hinglish variants).
7. **Fusion** – `base = max(p_text, p_url)`, then each rule pushes the score up:
   `final = base + rule_boost × (1 − base)`.
   Verdict: `≥ 0.70 → SCAM`, `≥ 0.40 → SUSPICIOUS`, else `SAFE`.
8. **Explanation** – the LLM gets the verdict + reasons and writes 2–3 simple sentences
   (English or Hindi). If no API key is set, a template explanation is used.
9. **Save** – the input is **redacted** (PII removed) and saved with score, verdict and model version.
10. **Response** – JSON returned to the client: verdict, score, reasons, explanation, advice, `analysis_id`.
11. **Feedback** – the user taps 👍/👎 → `POST /api/feedback` → stored → later exported to retrain.

## 4. Database design

```
model_versions                analyses                               feedback
──────────────                ─────────────────────────              ──────────────────────
id (PK)                       id (PK, uuid string)                   id (PK)
name  (text|url)              created_at                             analysis_id (FK → analyses.id)
version                       channel  (web|telegram|extension|api)  is_correct (bool)
metrics (JSON)                input_type (text|url|image)            correct_label (scam|safe|null)
created_at                    redacted_input (text)                  comment
                              verdict (scam|suspicious|safe)         created_at
                              risk_score (float)
                              text_score, url_score (float)
                              reasons (JSON list)
                              language
                              model_version
```

* **One analysis → many feedback rows** (one‑to‑many).
* Full SQL for Supabase: [`database/schema.sql`](../database/schema.sql).

## 5. 100% free tech stack

| Layer | Tool | Free because |
|---|---|---|
| Language | Python 3.11+ | open source |
| ML | scikit‑learn, XGBoost, (optional) Hugging Face Transformers | open source |
| Training GPU | Google Colab / Kaggle notebooks | free GPU hours |
| API | FastAPI + Uvicorn | open source |
| Web UI | Plain HTML/CSS/JS served by FastAPI | no build tools, no hosting bill |
| OCR | Tesseract (+ Hindi pack) | open source |
| LLM explanation | Groq or Google Gemini free tier (optional) | free API tier; app works without it |
| Database | Supabase Postgres | free tier (500 MB) |
| Hosting | Hugging Face Spaces (Docker) | free CPU container |
| Bot | Telegram Bot API | free |
| Extension | Chrome Manifest V3 | free to load unpacked (Chrome Web Store listing has a one‑time $5 fee – optional) |
| CI/CD | GitHub + GitHub Actions | free for public repos |

## 6. Known limitations (write these in your report – examiners like honesty)
* The SMS dataset is **spam**, not only **scams**; we add hand‑written Indian‑context scam examples (`ml/data/seed_messages.csv`) to fix this a little. Real user feedback is the best long‑term fix.
* PhiUSIIL "legitimate" URLs are mostly home pages, so a model could wrongly learn "has a path = phishing". We **augment** legitimate URLs with realistic paths to reduce this shortcut.
* In PhiUSIIL, 100% of legitimate URLs use https but only ~49% of phishing URLs do. The first model
  we trained put ~63% of its importance on `is_https`, a shortcut that fails on modern https phishing
  sites. We now randomise the scheme during training so the model learns real signals. (This
  "found a bias, fixed it" story is excellent material for your viva.)
* No model is 100% accurate. The app is an **assistant**, not a guarantee.
