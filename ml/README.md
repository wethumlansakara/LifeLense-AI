# ML workspace

`train_categories.py` generates a clearly synthetic 120-row starter dataset, evaluates TF-IDF + Logistic Regression against TF-IDF + Random Forest, and saves the selected pipeline and metrics in ignored `artifacts/`.

Run from the project root:

```powershell
backend/.venv/Scripts/python.exe ml/train_categories.py
```

The synthetic dataset in `data/starter_categories.csv` contains no private financial records. Personal labels remain in PostgreSQL; personal models are trained on demand using only that account's confirmed labels and saved in ignored, account-specific artifact namespaces.

Runtime categorization, forecasting, and anomaly services live in `backend/app/intelligence/`. Forecast regressions train per request on completed months and compare against a recent-month average with chronological backtesting. Isolation Forest is an experimental secondary unusual-spending detector. No LLM is used.

See [model design, limitations, and API details](../docs/intelligence.md).
