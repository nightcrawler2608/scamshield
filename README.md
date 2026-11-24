# 🛡️ ScamShield – AI Scam & Phishing Detection System

Paste a suspicious **message**, **link** or **screenshot** → get **Scam / Suspicious / Safe**, a risk score,
simple reasons and what to do next. Available as a **web app**, **Telegram bot** and **Chrome extension**.
Everything runs on **free** tools and free hosting.

> **Core idea:** our own trained ML models + a rule engine decide the verdict; an (optional) LLM only
> explains it in simple English/Hindi. Personal data is removed before anything is saved.

* Architecture, data flow and database design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
* SQL schema: [database/schema.sql](database/schema.sql)

---

## 📁 Project structure

```
├── backend/app/
│   ├── main.py               ← FastAPI app: all API routes + serves the web UI
│   ├── config.py             ← settings from .env
│   ├── db.py, models.py      ← database connection + tables (SQLite / Supabase Postgres)
│   ├── schemas.py            ← request/response validation
│   ├── core/
│   │   ├── features.py       ← URL features + text cleanup (shared by training AND serving)
│   │   ├── rules.py          ← scam rule engine (English + Hinglish)
│   │   └── privacy.py        ← removes phone numbers, emails, OTPs, account numbers
│   ├── services/
│   │   ├── analyzer.py       ← combines models + rules → verdict
│   │   ├── model_registry.py ← loads trained models
│   │   ├── explainer.py      ← LLM / template explanation + advice
│   │   └── ocr.py            ← screenshot → text (Tesseract)
│   └── static/               ← web app (HTML/CSS/JS) + dashboard
├── ml/
│   ├── download_data.py      ← step 1: download free datasets
│   ├── train_text_model.py   ← step 2: train message classifier
│   ├── train_url_model.py    ← step 3: train link classifier
│   ├── finetune_transformer.py ← optional v2 model (free Colab GPU)
│   ├── export_feedback.py    ← step 4: user feedback → new training data
│   └── data/seed_messages.csv← hand-written Indian-context scam examples
├── models/                   ← trained model files (.joblib)
├── bot/telegram_bot.py       ← Telegram bot
├── extension/                ← Chrome extension (Manifest V3)
├── tests/test_api.py         ← automated tests (pytest)
├── Dockerfile                ← one container for free hosting
└── .github/workflows/ci.yml  ← runs tests on every push (free)
```

---

## 🚀 Run it on your laptop (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

python ml/download_data.py        # ~1 minute
python ml/train_text_model.py     # ~1 minute
python ml/train_url_model.py      # ~2-3 minutes

uvicorn app.main:app --reload --app-dir backend
```
Open **http://127.0.0.1:8000** (web app), **/dashboard** (stats) and **/docs** (interactive API docs).

Run tests: `pytest -q`

**Optional:** screenshots need Tesseract OCR. On Windows install it from the UB Mannheim build
(github.com/UB-Mannheim/tesseract/wiki) and tick "Hindi" during setup. On the live server, Docker installs it automatically.

---

## 🌍 Put it live for FREE (step by step)

### 1. Database – Supabase (free)
1. Sign up at supabase.com → **New project** (region: Mumbai).
2. **SQL Editor** → paste [database/schema.sql](database/schema.sql) → **Run** (optional, the app also creates the tables itself).
3. **Project Settings → Database → Connection string → URI (Session pooler)** → copy it. This is your `DATABASE_URL`.

### 2. App hosting – Hugging Face Spaces (free, Docker)
1. Sign up at huggingface.co → **New Space** → SDK: **Docker** → Blank → Public.
2. Push this repo to the Space (it gives you a git URL), or connect GitHub.
   Add this at the very top of the Space's README.md:
   ```
   ---
   title: ScamShield
   sdk: docker
   app_port: 7860
   ---
   ```
3. Space **Settings → Variables and secrets** → add secrets:
   `DATABASE_URL` (from Supabase) and optionally `LLM_API_KEY`.
4. It builds automatically. Your app is live at `https://<username>-<space>.hf.space` 🎉

> Free Spaces sleep after ~48 h of no traffic and wake on the next visit. Their disk is temporary,
> which is why we use Supabase for the database.

### 3. LLM explanations – Groq (free tier, optional)
console.groq.com → API Keys → create → set `LLM_API_KEY`. Without a key the app uses template explanations.

### 4. Telegram bot (free)
1. Telegram → **@BotFather** → `/newbot` → copy the token.
2. In `.env`: `TELEGRAM_BOT_TOKEN=...` and `SCAMSHIELD_API_URL=https://<your-space>.hf.space`
3. `python bot/telegram_bot.py` (keep running on your laptop for demos, or on a free worker host).

### 5. Chrome extension (free)
1. Chrome → `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → select the `extension` folder.
2. Right-click the extension → **Options** → set your live API URL.
3. Click the icon to check the current page, or right-click any link → **Check link with ScamShield**.

### 6. CI – GitHub Actions (free)
Push to a public GitHub repo; tests run automatically on every push.

---

## 🔁 The MLOps loop (improve the model with real users)
```powershell
python ml/export_feedback.py      # users' 👍/👎 → ml/data/feedback_export.csv
python ml/train_text_model.py     # retrains including feedback
git commit -am "retrain model" ; git push   # Space redeploys with the new model
```

---

## 📊 Current results (held-out 20% test set)
| Model | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|
| Text: TF-IDF + Logistic Regression | 0.978 | 0.950 | 0.964 | 0.998 |
| URL: XGBoost (32 features, bias-corrected) | 0.935 | 0.814 | 0.870 | 0.923 |

Exact numbers are in `models/*_metrics.json` and change slightly with each training run.
The URL model scored 0.997 F1 *before* we removed the https shortcut (see ARCHITECTURE.md §6). The lower
number is the honest one.

---

## 🗓️ Timeline (one student, part-time ~10–12 h/week)

| Weeks | Work | Output for college |
|---|---|---|
| 1–2 | Learn the code, run locally, write synopsis | Synopsis / problem statement |
| 3–4 | Collect 200+ real scam messages from family/friends (remove personal info), add Hindi examples | Dataset chapter |
| 5–6 | Retrain models, compare baselines (Naive Bayes vs LogReg vs XGBoost), confusion matrices | Results chapter |
| 7–8 | Fine-tune transformer on Colab, compare with baseline | "Model v2" comparison |
| 9–10 | Deploy (Supabase + HF Spaces), Telegram bot, extension | Live link |
| 11–13 | Share with real users, collect feedback, retrain once | User numbers, "before vs after" |
| 14–16 | Report, PPT, demo video, viva prep | Final submission |

**The code is ready now. The ~4 months are for data collection, experiments, real users and the report,
which is what examiners grade.**

---

## ⚠️ Limitations
ScamShield is an assistant, not a guarantee. Models are trained on public data that may not cover every new scam.
Always verify through official channels. Report fraud in India at cybercrime.gov.in or call 1930.
