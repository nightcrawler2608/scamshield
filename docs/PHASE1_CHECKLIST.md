# Phase 1 – Setup and ownership (week 1)

Goal: the project is safely saved on GitHub, it runs on your laptop, and you can explain it.

## 1. Git (done)
- [x] Local git repository created, first commit made
- [x] `.env`, database file and raw datasets are excluded by `.gitignore`

## 2. Put it on GitHub (≈10 min)
1. Sign in at https://github.com → **New repository**
2. Name: `scamshield` · **Public** · do **not** tick "Add README" (we already have one)
3. Copy the repo URL, then in a terminal inside the project folder run:
   ```powershell
   git remote add origin https://github.com/<your-username>/scamshield.git
   git push -u origin main
   ```
4. A browser window will ask you to sign in to GitHub the first time. That's normal.
5. Open the **Actions** tab on GitHub: the tests should run and turn green ✅.

## 3. Install Tesseract OCR (≈5 min, for screenshot checks)
1. Download the Windows installer from the UB Mannheim build:
   https://github.com/UB-Mannheim/tesseract/wiki
2. During install, under **Additional language data**, tick **Hindi**.
3. Keep the default folder `C:\Program Files\Tesseract-OCR`.
4. Close and reopen your terminal, then check:
   ```powershell
   tesseract --version
   ```

## 4. Run it yourself
```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```
Open http://127.0.0.1:8000 and try **10 different messages**: 5 real scams you have
received, 5 normal ones. Note any wrong answers in a text file. They become test cases later.

Run the tests:
```powershell
.venv\Scripts\python.exe -m pytest -q
```

## 5. Understand the core (read in this order)
| # | File | What to understand |
|---|------|--------------------|
| 1 | `docs/ARCHITECTURE.md` | The full picture and the 11-step data flow |
| 2 | `backend/app/main.py` | Which URL does what |
| 3 | `backend/app/services/analyzer.py` | How ML score + rules → one final score |
| 4 | `backend/app/core/rules.py` | The 14 scam patterns |
| 5 | `ml/train_text_model.py` | How the message model is trained |

**Self-test:** can you explain, without notes, in 2 minutes:
- what happens from "user pastes a message" to "verdict appears"?
- why the LLM only *explains* and never *decides*?
- why we removed the http/https shortcut from the link model (F1 0.997 → 0.87)?

## 6. Synopsis for your guide
Submit title, problem statement, objectives, tech stack, and timeline. Ask Claude to draft it.

## Done when
- [ ] Code is on GitHub and the Actions tests are green
- [ ] `tesseract --version` works
- [ ] App runs on your laptop; 10 messages tried
- [ ] You can explain the data flow in 2 minutes
- [ ] Synopsis submitted
