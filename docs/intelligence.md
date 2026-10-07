# Phases 7–9: categorization, forecasting and unusual spending

No LLM or external finance/AI service is used. All data queries derive ownership from the current authenticated user. No personal corrections are added to the shared starter dataset.

## Category pipeline

Merchant names and descriptions are normalized for case, accents, punctuation, reference numbers and common payment boilerplate. The pipeline checks your private confirmed labels, known merchants and unambiguous keyword rules, then TF-IDF classification. Unknown/low-scoring text falls back to Other. Income defaults to Salary. Original merchant text remains available for display.

Rules include Uber/PickMe → Transport, Keells/Cargills → Groceries, Netflix/Spotify → Entertainment, and Dialog → Bills. Rule scores are heuristic; classifier probabilities are uncalibrated scores. Neither should be treated as guaranteed correctness. The transaction form automatically selects a suggestion until you manually choose a category. Imports show each suggestion's method/score, and corrections remain editable before confirmation.

Explicit transaction category choices and edits are saved as private confirmed labels. Automatically chosen categories are recomputed on save against the latest text and are not treated as corrected training labels. Category edits update the existing label; converting an expense to income removes its expense label. Import predictions are not automatically treated as training labels: only explicitly corrected categories (`category_confirmed: true`) are saved. Labels are associated with their owning user and transaction and cascade on deletion.

The starter training script builds `ml/data/starter_categories.csv` from 120 explicitly synthetic expense examples across ten categories. It compares TF-IDF + Logistic Regression with TF-IDF + Random Forest on a stratified 30-example holdout, selecting the higher macro-F1 model and refitting on all examples. The feature vectorizer is fit only on the training split during evaluation. Synthetic merchant names are excluded from features to avoid category-name leakage. The saved metrics describe a small synthetic test, not accuracy on real bank data.

From the project root:

```powershell
backend/.venv/Scripts/python.exe ml/train_categories.py
```

Saved files: ignored `ml/artifacts/category_model.joblib` and `category_metrics.json`. The API loads only these trusted local artifacts, never uploaded pickles. If the artifact is absent, rules and Other fallback continue working.

You can download your confirmed label CSV and train a private model from the transaction form. Training requires 20 distinct preprocessed examples, at least two expense categories, and at least four examples per category. It uses only the latest 1,000 labels belonging to you, deduplicates text before splitting, compares both classifiers, and atomically saves the winner in `ml/artifacts/users/{user_id}-{account_fingerprint}/`. This private model takes precedence over the shared starter model for that user. Model evaluation is reported on a held-out text split; merchant/domain overlap can still make accuracy optimistic. Models change only when trained again. The artifact namespace fingerprints the account email and creation timestamp so a reused numeric user ID cannot inherit another account’s model.

## Expense forecasts

The forecast API aggregates up to 36 completed months of the owner's expenses. Current-month and future transactions are excluded. Months after the first recorded expense with no records become zeros; they indicate missing recorded spending, not proof of complete statement coverage.

With fewer than 12 completed months or fewer than 9 months with expenses, the API uses a mean of up to the latest three months and labels confidence low. No completed-month expenses means no prediction, rather than a made-up zero estimate.

For enough history, a scaled Ridge regression uses previous one/two month totals, a trailing-three-month mean, time index, and seasonal sine/cosine features. Expanding chronological windows backtest up to the last six historical months, using strictly earlier data for each prediction. MAE and RMSE are reported for both the regression and moving-average baseline. Regression is used only when its MAE beats the average by at least 5%; otherwise the average remains the forecast.

The target is the next calendar month in Asia/Colombo. Since the current month is excluded from training, regression recursively estimates the current month as a bridge before next month. The UI explains training coverage and shows recorded history and a dotted next-month estimate. Its low/high planning range uses historical variation/backtest error and a conservative minimum width. This is a heuristic range, not a calibrated confidence interval. Confidence is a qualitative label, never a probability.

## Unusual spending

Scans process up to 2,000 latest recorded expenses in date/ID order. Only earlier expenses contribute to category and normalized-merchant baselines. A baseline needs at least five examples; it uses a median and a median-absolute-deviation scale, with a relative/minimum scale floor. A statistical flag requires an amount above both 2.5× the median and median + 3.5 robust scales, plus at least Rs. 1,000 above the median.

An experimental Isolation Forest uses log-transformed prior category amounts after at least 20 examples. Models are refreshed every 20 new accepted baseline examples to bound runtime. A secondary flag additionally requires an amount over twice the median and Rs. 1,000 above it. Its score and the statistical score are heuristic unusualness rankings, not fraud probabilities. There is no labeled anomaly dataset, so no fraud accuracy claim is made.

Detected records persist in `spending_anomalies`, including explanation, score, baseline and method. A user can mark an alert normal, see dismissed alerts, or restore the warning. That choice survives rescans. Earlier flagged outliers are excluded from later baselines unless marked normal. Scans deactivate alerts that no longer qualify after edits; deletions cascade. A per-user advisory lock serializes scans. The dashboard refreshes the scan after transaction changes and provides a rescan button.

These are **unusual transactions**. LifeLens cannot establish whether a payment is fraudulent.

## API

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | `/api/intelligence/suggest-category` | Description, merchant, direction → category, method, score, explanation |
| POST | `/api/intelligence/transactions/{id}/category` | Owned category correction and private label update |
| GET | `/api/intelligence/training-dataset` | Owner's confirmed labels as spreadsheet-safe CSV |
| GET | `/api/intelligence/model-status` | Applicable model availability and evaluation metadata |
| POST | `/api/intelligence/train-category-model` | Train/persist a model using only the owner's confirmed labels |
| GET | `/api/intelligence/forecast` | Next-calendar-month estimate, history, comparison metrics, limitations |
| POST | `/api/intelligence/unusual/scan` | Persist/reconcile unusual expense observations |
| GET | `/api/intelligence/unusual` | Active owner alerts; `include_normal=true` includes dismissed alerts |
| PUT | `/api/intelligence/unusual/{id}/normal` | Set or clear the owner's normal override |

Create/edit transactions may omit `category_id` to use the server suggestion. Explicit choices are still validated against income/expense direction. Intelligence endpoints reject ownership IDs supplied by clients. Alert lists are capped at 50 active results; scans cover the latest 2,000 recorded expenses.

References: [TF-IDF](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html), [chronological evaluation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html), [regression metrics](https://scikit-learn.org/stable/api/sklearn.metrics.html), [Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).
