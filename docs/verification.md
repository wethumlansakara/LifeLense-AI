# Verification

Updated on October 7, 2026 against the isolated PostgreSQL 18 database:

- Vite production build passed.
- Eighteen PostgreSQL-backed pytest tests passed: phases 1–6 regression checks plus normalization/rules; private correction learning and dataset export; ML fallback; label refresh; import category corrections; cold-start/average forecasting and ownership; chronological Ridge evaluation with MAE/RMSE; unusual-spending explanations and normal overrides; repeatable Isolation Forest experiments; and private model training/persistence/isolation.
- Alembic schema comparison passed with no new upgrade operations detected.
- Five Playwright end-to-end tests passed through real React → FastAPI → PostgreSQL requests: original authentication/transaction/import workflows plus automatic category suggestions, saved private corrections, label downloads/training prerequisites, forecast fallback, warning explanations, mark-normal/restore, and mobile layouts.
- Desktop and 390px mobile browser screenshots inspected; dashboard, transactions and import views had no page-level horizontal overflow. Wide tables scroll inside their panels.
- Confirmed Git ignores backend/frontend `.env`, local PostgreSQL data, virtual environment, and frontend dependencies.

Browser tests ran using the installed default Playwright Chromium. Install it on a fresh machine using `npx playwright install chromium`. Test and screenshot accounts are separate, randomly named accounts; no existing user's transactions were altered.

The shared category comparison used 120 synthetic examples and a stratified 30-example holdout. Logistic Regression: accuracy 0.8667, macro-F1 0.8695. Random Forest: accuracy 0.6333, macro-F1 0.6105. Logistic Regression was saved. These are synthetic holdout results, not claims about real statement accuracy.

The installed Starlette version emits a non-failing deprecation warning about its httpx test client. All assertions passed.

## Phases 10–12

25 backend tests and seven browser tests passed. Frontend production build and Alembic comparison passed. New checks cover owner-only goal CRUD/funding, progress and monthly savings, private chat/history clearing, period/category analysis, future-record exclusion, provider grounding and errors/timeouts. No live LLM call was made; provider calls were verified using mocked HTTP responses. See [AI and goals](ai-and-goals.md).
