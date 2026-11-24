# ScamShield – Viva Notes

How to use: read the **one-liners** first and say them out loud. Then read the details. Then close this file and answer from memory.
Numbers are from the current model (text-202611241517). If you retrain, update them from `models/*_metrics.json`.

---

## Part A – One-line answers (revise these the night before)

| # | Question | Say this |
|---|---|---|
| 1 | Click to verdict? | Text goes to FastAPI. Language is detected, links are extracted and scored, the message model and rules run, scores are fused into a verdict, personal data is removed, an explanation is added, it's saved and returned. |
| 2 | The three judges? | The message model (TF-IDF + logistic regression) reads the wording, the URL model (XGBoost, 32 features) reads the link, and 15 rules catch known scam tricks. |
| 3 | The LLM's job? | It only explains the verdict in simple words. It never decides it, because our models are measurable and consistent and the app works without it. |
| 4 | Removed before saving? | Phone, email, UPI ID, OTP/codes, card/account numbers, to protect users and follow DPDP data minimisation. |
| 5 | Verdict bands? | 70% and above is SCAM, 40–69% SUSPICIOUS, under 40% SAFE. |
| 6 | TF-IDF and char n-grams? | TF-IDF scores words that are frequent in this message but rare overall. Character chunks catch misspellings and Hinglish variants like "kyc / K.Y.C / turnt". |
| 7 | URL 0.997 → 0.87? | The model learned the shortcut "https = safe". I randomised the scheme and added realistic paths. 0.87 is the honest score. |
| 8 | Why share features.py? | So training and serving build features identically. Separate copies can drift silently: training-serving skew. |
| 9 | Hindi false alarm? | The English model knew only the number "5" and guessed scam. Now, if it knows under 50% of the words, its score is scaled down. |
| 10 | Feedback button? | It's saved with the analysis, exported by `export_feedback.py`, and used in retraining. Review it first and keep the old model if the new one is worse. |
| 11 | Why trust 0.97 on Indian scams? | 0.97 is on mostly UK data. On Indian messages I measured separately: 0.90 F1 on the seed slice, 26/28 trials and 19/20 stress, every scam caught. Phase 2 adds real data. |
| 12 | Why noisy-OR, not average? | Averaging lets a silent signal drag a real scam down. Noisy-OR only adds evidence and never goes past 100%. |
| 13 | What is stored? | Only redacted text plus the result. The original is analysed in memory and never saved. A test checks this on every push. |
| 14 | Precision vs recall? | Precision: how often a SCAM alert is right. Recall: how many scams are caught. Recall matters more, but precision keeps users trusting the warnings. |
| 15 | Is 74% a probability? | No, it's a risk score for ranking and bands. Class weights and rule boosts shift it. Calibration is a planned improvement. |
| 16 | Why ML and rules? | The model learns patterns from data. The rules catch known scam types in any wording and explain them clearly. Each covers the other's gaps. |

---

## Part B – Detailed answers

### Q1. From click to verdict
1. `app.js` sends the text to `POST /api/analyze/text` ([main.py](../backend/app/main.py)). A screenshot goes to `/api/analyze/image`, where **Tesseract OCR** (eng+hin) turns it into text first.
2. Rate limit (30 requests/min) and input checks (text cut to 5,000 characters).
3. Language detection: Devanagari letters mean `hi`, otherwise `en`.
4. Links are extracted and each is scored by the **URL model** and its warning signs.
5. The **message model** scores the text, and the **rule engine** checks 15 scam patterns.
6. **Fusion** gives one risk score, which becomes a verdict.
7. Personal data is **removed**, an **explanation** is written (LLM or template), the result is **saved**, and JSON is returned. The UI draws the badge, meter, reasons and advice.

Core code: `analyze()` in [analyzer.py](../backend/app/services/analyzer.py).

### Q2. The three judges
| Judge | Looks at | How |
|---|---|---|
| Message model | The wording | TF-IDF (word 1–2-grams + char 2–5-grams) + logistic regression, trained on about 5,500 UCI SMS plus Indian seed examples |
| URL model | The link text only | XGBoost on 32 features: subdomains, suspicious endings (.xyz, .top), look-alike brands, IP address, `@`, length… |
| Rule engine | Known scam tricks | 15 regex rules (OTP request, KYC threat, lottery, digital arrest, "sent by mistake"…) in English, Hinglish and Hindi script |

### Q3. The LLM's job
- **Does:** explains the verdict in 2–3 simple sentences, in English or Hindi.
- **Does not:** decide or change the verdict. It gets the verdict and reasons as fixed input.
- **Why:**
  - LLMs can make things up and are inconsistent, while our models are measured.
  - The app works without an API key, using templates.
  - It proves the AI is *my own* work, not just an API call.
- It only ever sees **redacted** text.

### Q4 and Q13. Privacy: what is stored
- `redact()` in [privacy.py](../backend/app/core/privacy.py) replaces:
  - phone numbers → `[PHONE]`
  - email addresses → `[EMAIL]`
  - UPI IDs → `[UPI_ID]`
  - OTPs and codes → `[CODE]`
  - card and account numbers → `[NUMBER]`
- The full text is analysed **in memory only**. The Analysis table stores only `redacted_input` plus the verdict.
- Text is also redacted before going to the external LLM.
- **Proof:** `test_pii_not_stored_and_feedback` in [test_api.py](../tests/test_api.py) reads the database row back and checks that the phone number is gone. It runs in CI on every push.
- **Why:** if the database ever leaked, it would hold no OTPs or account numbers. This is data minimisation under the **DPDP Act 2023**.

### Q5 and Q12. Verdicts and noisy-OR fusion
| Risk | Verdict |
|---|---|
| 70% and above | SCAM |
| 40–69% | SUSPICIOUS |
| under 40% | SAFE |

- `base = max(message score, link score)`, then `final = base + rule_boost × (1 − base)`.
- This equals `1 − (1 − base)(1 − rule)`: the chance that *at least one* partly reliable warning sign is right.
- **Why not average:**

| Case | Model | Rules | Average | Noisy-OR |
|---|---|---|---|---|
| New scam, no rule fired | 0.95 | 0 | 0.475, SUSPICIOUS ❌ | 0.95, SCAM ✅ |
| Odd wording, OTP rule fired | 0.30 | 0.60 | 0.45, SUSPICIOUS ❌ | 0.72, SCAM ✅ |

- How noisy-OR behaves:
  - It never decreases when evidence is added.
  - It never exceeds 1.
  - Diminishing returns: there's little room to add near 100%.
- The display caps at 99%, because we never claim certainty.

### Q6. TF-IDF and character n-grams
- **TF** is how often a word appears in this message. **IDF** is how rare it is across all messages.
  - Common words ("the", "hai") score low.
  - Telling words ("KYC", "lottery", "blocked") score high.
- **Character 2–5-grams** match spelling variants ("kyc / K.Y.C / kycc", "turant / turnt", "fr33") and parts of words the model has never seen.
- Code: `build_pipeline()` in [train_text_model.py](../ml/train_text_model.py).

### Q7. URL model: 0.997 → 0.87
- **Problem:** shortcut learning.
  - In PhiUSIIL, every legitimate URL used https, but only about half of the phishing ones did.
  - `is_https` carried 63% of all feature importance.
  - Real scam sites use free https certificates, so this model would fail in real use.
- **Fix** in [train_url_model.py](../ml/train_url_model.py):
  - Randomise http/https 50/50.
  - Add realistic paths to 40% of legitimate URLs, which were all bare homepages.
- **Result:** 0.87 F1, based on real signals (subdomains, free hosting, suspicious endings).
- *"A high score isn't proof. I checked what the model learned."*

### Q8. Shared feature code
- `features.py` and `normalize_text` are imported by **both** the training scripts and the backend.
- With separate copies, a change to one makes live inputs differ from training inputs. Accuracy then drops silently, with no error.
- This is **training-serving skew**. One shared source prevents it.

### Q9. The Hindi false alarm
- In "कल शाम 5 बजे मिलते हैं", the English-trained model recognised only `5`, which became `numtoken`. Numbers appear mostly in spam, so it said 90% scam.
- **Fix:** `text_coverage()` in [model_registry.py](../backend/app/services/model_registry.py) measures the share of words known from training.
  - If it's under 50%, then `score × coverage / 0.5`.
  - *"The model knows when it doesn't know."*
- Hindi scams are still caught by the **Hindi-script rules**. The long-term fix is real Hindi data (Phase 2).

### Q10. The feedback loop
1. YES/NO sends `POST /api/feedback`, which is saved in the Feedback table and linked to the analysis (redacted text only).
2. The dashboard shows feedback count and accuracy according to users.
3. [export_feedback.py](../ml/export_feedback.py) turns them into labelled rows: for example, SCAM plus a NO vote means "not scam". They go to `feedback_export.csv`.
4. `train_text_model.py` picks that up and retrains. Compare the metrics before and after.
- **Caution:** feedback can be wrong or abused. Review a sample, and keep the old model if the new one is worse.

### Q11. "Why trust 0.97 on real Indian scams?"
- *"Don't trust that number alone."* The test split is mostly UCI (UK) SMS.
- Indian evidence, measured separately:
  - Seed slice F1: **0.90**.
  - Trial set: **26/28**.
  - Stress set: **19/20**.
  - **All 26 scams caught.** Both errors are false alarms, the safer side to be wrong on.
- The rules cover known Indian scam types from day one.
- I found and fixed a dataset bias ("company tone = scam") using genuine service SMS. The before-and-after is in [PHASE1_TRIALS.md](PHASE1_TRIALS.md).
- **Honest limit:** these sets are small and self-written. Phase 2 collects 200+ real messages.

### Q14. Precision vs recall
- **Precision:** of the messages called SCAM, how many really are. Low precision means false alarms.
- **Recall:** of the real scams, how many were caught. Low recall means missed scams.
- Ours: P **0.979**, R **0.965**, F1 **0.972** (harmonic mean).
- **Recall matters more,** because a miss costs money. Precision still matters: too many false alarms and users ignore warnings ("cry wolf").
- Supporting design:
  - the SUSPICIOUS middle band
  - `class_weight="balanced"`
  - in trials, all scams caught and both errors on the safe side

### Q15. Is 74% a probability?
- No. It's a **risk score** for ranking and bands, not a calibrated probability.
- Logistic regression output is only roughly a probability, and it's shifted by:
  - balanced class weights
  - seed sample weights
  - hand-set rule weights
  - coverage damping
- Evidence: N4, a real Amazon SMS, scored 74% and was safe.
- **Improvement:**
  - `CalibratedClassifierCV` (Platt or isotonic) on held-out data
  - check with a reliability diagram
  - report the Brier score before and after

### Q16. Why both ML and rules?
- The **model** generalises from data and catches scams that *feel* like scams without matching any rule.
- The **rules** catch known types in any wording or language (Hindi especially), and give **readable reasons**.
- Both run on every message and are combined by noisy-OR.
- The rules don't train the model.

---

## Part C – Known weaknesses (say these before the examiner finds them)
- **N4:** a genuine Amazon delivery SMS with a real link scores 74% SCAM. The text model reacts to "delivery + link".
- **N7:** a friend talking about their own blocked account scores 51% SUSPICIOUS. Bag-of-words has no context.
- **Hindi:** the model knows little Hindi and relies on rules plus coverage damping.
- **Test sets:** small and self-written.
- **Fixes planned:** real data (Phase 2), a transformer (Phase 3), calibration.
- I did **not** tune against the test set until these passed, because that would be overfitting.
