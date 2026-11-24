# Phase 2 – Real data collection guide

Goal: **200+ real messages** (target about 120 scam and 100+ safe), with a good share in **Hindi and Hinglish**.
This is the data that fixes the known weaknesses (N4, N7, weak Hindi) and is the core of your Dataset chapter.

---

## 1. Where to collect from

| Source | What to ask for | `source` value |
|---|---|---|
| Your own phone | Old scam SMS, bank alerts, OTPs, delivery SMS | `own` |
| Family (parents, relatives) | "Forward me any fake or suspicious message you got", plus normal bank/delivery SMS | `family` |
| Friends / class groups | WhatsApp scam forwards, job scams, fake offers | `friend` |
| News and official advisories | Scam SMS shown in news reports, cybercrime.gov.in, RBI and bank fraud-awareness pages | `public` |

**Collect SAFE messages too**, especially the hard ones that look like scams:
- real bank alerts
- OTPs
- delivery updates with real links
- recharge confirmations
- chats that *mention* "KYC" or "blocked"

Without these the model learns "company tone = scam" again.

---

## 2. Fill in the template

1. Copy `ml/data/collect/TEMPLATE.csv` to a new file in the same folder, e.g. `ml/data/collect/batch1_family.csv`.
2. Open it in Excel or Google Sheets and add one message per row. Save as **CSV UTF-8** so Hindi doesn't break.
3. Delete the 3 example rows.

| Column | Required? | Values |
|---|---|---|
| `text` | yes | The full message, copied exactly (keep spelling mistakes and emojis) |
| `label` | yes | `scam` or `safe` |
| `kind` | recommended | One of the types below |
| `language` | recommended | `en`, `hi` (Devanagari) or `hinglish` (Hindi in English letters). If blank, the script guesses `hi` or `en` |
| `source` | recommended | `own`, `family`, `friend`, `public` |
| `notes` | optional | Anything useful: "WhatsApp", "came with a call", "not sure" |

**Kinds:**
- Scam: `kyc`, `bank_block`, `otp`, `parcel`, `electricity`, `challan`, `lottery`, `job`, `investment`, `loan`, `digital_arrest`, `mistaken_payment`, `family_emergency`, `refund`, `reward`, `free_offer`, `sextortion`
- Safe: `bank_alert`, `otp_genuine`, `delivery`, `recharge`, `bill`, `personal`, `college`, `official_warning`, `promo_genuine`
- `other` if nothing fits

### Labelling rules (be consistent)
- **scam:** it tries to get money, OTP, PIN, personal data, an app install or a click on a fake link *by deceiving you*.
- **safe:** genuine (from the real company or a real person), *even if* it contains a link, an OTP or the word "blocked".
- **Genuine promotional spam** (a real shop's offer) is `safe` with kind `promo_genuine`. We detect *scams*, not adverts.
- **Not sure?** Leave it out, or put "not sure" in `notes` and ask your guide. A wrong label hurts more than a missing row.

---

## 3. Privacy (very important)

The raw files in `ml/data/collect/` **are never committed** (they're in `.gitignore`). The prepare script also redacts automatically:

| Removed automatically | Becomes |
|---|---|
| Phone numbers | `[PHONE]` |
| Emails, UPI IDs | `[EMAIL]`, `[UPI_ID]` |
| OTPs, PINs, codes | `[CODE]` |
| Card, account, Aadhaar numbers | `[NUMBER]` |

**You must remove names yourself:** replace any real person's name with `[NAME]`.
Brand names (SBI, Amazon, Jio) stay; the model needs them.

Ask people's permission before using their messages, and tell them personal details are removed.
Mention this consent in your report's ethics section.

---

## 4. Prepare the data

```powershell
python ml/prepare_real_data.py
```

What it does:
1. Reads every CSV in `ml/data/collect/` except the template.
2. **Checks** the labels and columns and tells you which file and row is wrong.
3. **Redacts** personal data and lists rows that *still* look personal (long digit runs, `@`), so you can check them by hand.
4. **Removes duplicates**: exact ones, and near-copies such as the same forward with a different link, so a message can't be in both train and test.
5. **Drops anything that's already in our trial/stress test sets**, so those stay untouched.
6. **Splits** into `ml/data/real_train.csv` (about 80%) and `ml/data/real_test.csv` (about 20%).
   - The split is decided by a fingerprint of each message, so **adding new messages later never moves old ones** between train and test.

Re-run it every time you add a batch.

---

## 5. Measure "before vs after" (the results chapter)

```powershell
python ml/evaluate_real.py --tag before         # current model, BEFORE training on real data
python ml/train_text_model.py                  # retrains, now including real_train.csv
python ml/evaluate_real.py --tag after          # same test set, new model
python ml/evaluate_real.py --compare before after
```

- Results are saved to `docs/results/real_eval_<tag>.json`.
- `--compare` prints a table you can paste straight into your report: overall, per language, scams caught and false alarms.
- **Never train on `real_test.csv`.** The training script only reads `real_train.csv`.

---

## 6. Checklist
- [ ] Batch 1: 50 messages (your own phone + family)
- [ ] Batch 2: 50 more (friends, WhatsApp forwards)
- [ ] Batch 3: 100 more, filling the gaps the script reports (Hindi? safe look-alikes?)
- [ ] Names replaced with `[NAME]`, flagged rows checked by hand
- [ ] `evaluate_real.py --tag before` run **before** the first retrain
- [ ] Retrain, `--tag after`, `--compare` table in the report
- [ ] Commit `real_train.csv`, `real_test.csv` and `docs/results/` (never the raw files)
