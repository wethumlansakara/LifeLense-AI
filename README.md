# LifeLens AI

Personal finance application implemented through **phases 1–6**: React/Vite/Tailwind, FastAPI, PostgreSQL/SQLAlchemy, Alembic migrations, authentication, transaction management, Chart.js analytics, and CSV/XLSX statement import.

## Run on this Windows machine

Dependencies are installed in `frontend/node_modules` and `backend/.venv`. PostgreSQL 18 binaries are already installed. An isolated password-protected PostgreSQL cluster lives in ignored `.local/postgres-data`, listening only on `127.0.0.1:55432`.

From the project root, initialize or restart the local database:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-local.ps1
```

Apply migrations and seed the eleven default categories:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
cd ..
```

Start these commands in two terminals from the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

Open **http://localhost:5173**. API documentation: **http://127.0.0.1:8000/docs**.

## Fresh checkout

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd ci --prefix frontend
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-local.ps1
```

For an independently managed PostgreSQL server or another OS, copy `backend/.env.example` to `backend/.env`, set `DATABASE_URL` and a cryptographically random `JWT_SECRET` of at least 32 characters, and create the named database. Copy `frontend/.env.example` to `frontend/.env`. The setup script intentionally refuses to overwrite another database configuration. Run the migration/seed commands above, then `python -m uvicorn app.main:app --reload` from `backend/` and `npm run dev` from `frontend/`.

## Verification

Tests use the configured PostgreSQL database. Backend tests create randomly named users and remove them afterward; browser tests leave a uniquely named test account.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
cd ../frontend
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

The backend must be running on port 8000 for browser tests. Playwright starts Vite automatically when needed.

## Using LifeLens

- **Overview:** select a month to view income, expenses, savings, previous-month comparisons, category breakdown, daily spending, six-month trends, and recent transactions. All charts use your actual records; a new account starts empty.
- **Transactions:** add income or expenses, choose a compatible category, merchant, and date, then view, edit, or delete entries. Search descriptions/merchants, combine category/type/date filters, change sorting, and paginate results.
- **Import statement:** upload CSV or XLSX, confirm detected columns or map them manually, choose date order and the default direction for unsigned amounts, and preview. Correct fields in the table and check rows to include. Invalid rows and possible duplicates start unchecked. Only **Confirm import** saves records. Duplicate checking runs again during confirmation.

A [sample CSV](frontend/public/sample-statement.csv) is included and can be downloaded from the import screen. Supported statements have a header row, at most 2,000 records, at most 50 columns, and are 5 MB or smaller. XLSX uses the first worksheet. Amounts are LKR with decimal points and optional comma thousands separators; there is no currency conversion. Dates support ISO, day-first/month-first formats, and Excel dates. Review all inferred values before confirming.

## Scope

- All four models and relationships, money stored as exact decimals, foreign keys and database constraints.
- Pydantic create/read schemas; Alembic initial migration; idempotent category seeding.
- Register, login, current user, JWT authentication dependency, Argon2 hashes, normalized unique emails, and password/email validation.
- Registration/login screens, session authentication state, protected routes, expiry handling, logout, profile menu, error recovery, and a responsive foundation workspace.
- Owner-scoped transaction create/read/update/delete, category/type validation, search, inclusive date/category/type filters, pagination, sorting, and details dialogs.
- Five Chart.js views: income versus expenses, category doughnut, monthly spending line, daily spending, and six-month income/expense/savings trend.
- PostgreSQL dashboard aggregates, exact money values, recent transactions, top spending category, and previous-month percentage comparisons.
- pandas-based CSV/XLSX parsing, editable mapping and previews, date/amount normalization, merchant-rule category suggestions, duplicate detection, and atomic confirmation. Uploaded statements are not permanently stored.

Predictions, anomaly detection, saving-goal workflows, chat, reports, and ML/LLM integrations are future phases and are not implemented. Import category suggestions use deterministic rules rather than ML.

See [architecture](docs/architecture.md) for API and security details.
