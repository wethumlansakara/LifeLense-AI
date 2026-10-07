# Architecture and API

Vite serves React on port 5173 and proxies `/api` to FastAPI on port 8000. FastAPI opens SQLAlchemy sessions against PostgreSQL. The health endpoint executes a real SQL query; categories require authentication and come from seeded rows.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Verify database connectivity |
| POST | `/api/auth/register` | JSON `{name,email,password}`, returns public user, 201 |
| POST | `/api/auth/login` | JSON `{email,password}`, returns JWT bearer access token |
| GET | `/api/auth/me` | Return only the authenticated user's public profile |
| GET | `/api/categories` | Return eleven shared default categories, authenticated |
| GET | `/api/transactions` | Owner-scoped list with search, filters, sorting, and pagination |
| POST | `/api/transactions` | Create a transaction belonging to the signed-in user |
| GET | `/api/transactions/{id}` | Owner-scoped transaction details |
| PUT | `/api/transactions/{id}` | Owner-scoped complete transaction update |
| DELETE | `/api/transactions/{id}` | Owner-scoped deletion, returns 204 |
| GET | `/api/dashboard?month=2026-10-01` | Owner-scoped monthly summaries and chart series |
| POST | `/api/imports/preview` | Multipart CSV/XLSX upload, mapping and editable parsed rows |
| POST | `/api/imports/confirm` | Atomic owner-scoped import of corrected transactions |

Authentication uses `Authorization: Bearer <token>`. Tokens expire after 30 minutes by default. JWT verification fixes the HS256 algorithm and requires subject, issue time, and expiry. Missing, expired, tampered, or unknown-user tokens return 401. Names are trimmed, emails normalized to lowercase, and passwords must be 12–128 characters. A unique database constraint prevents duplicate email races. No password hashes appear in response schemas. Invalid credentials use one generic error and dummy password verification for unknown accounts.

The browser stores the access token in tab-scoped sessionStorage, restores the current user on reload, and removes the token on logout or expiry. Logout clears this browser session; an already issued token remains valid until its expiry. There are no refresh tokens or server-side revocation in this scope. Deployments handling real financial data should add HTTPS, request throttling, a production secret store, and an appropriate session/revocation policy.

`User` owns `Transaction` and `SavingGoal` records. `Category` is shared and referenced by `Transaction`. User-owned records have foreign keys and indexes; deleting a user cascades to their transactions and goals. Amounts use `NUMERIC(14,2)`, not floating-point storage. Transactions store positive amounts and a separate income/expense direction. Categories allow income or expense; Salary is income and the other defaults are expense. Transaction APIs and import confirmation enforce category-direction compatibility. Transaction schemas reject supplied `user_id` fields; ownership always comes from the authenticated user. Looking up another user's transaction returns the same 404 as a missing record.

Migrations explicitly define the schema; application startup never creates tables implicitly. Run `alembic upgrade head` before starting the app. `python -m app.seed` uses PostgreSQL upserts and is safe to repeat. Database failures return a generic 503 and unexpected failures return a generic 500; detailed errors stay in backend logs.

Environment files and the local database are excluded from Git. Local setup generates independent random database and JWT secrets. The isolated cluster uses existing PostgreSQL installation binaries and does not alter the existing Windows PostgreSQL service.

## Transaction queries

List parameters: `search`, `category_id`, `date_from`, `date_to`, `transaction_type`, `page` (default 1), `page_size` (default 10, maximum 100), `sort_by`, and `sort_order`. Search matches description or merchant literally and case-insensitively; `%` and `_` do not become wildcard searches. Dates are inclusive. Sorting accepts date, amount, merchant, description, category, type, or creation time; ties use descending ID. List items include public category details. Source is set server-side to `manual` on creation and preserved during edits.

## Dashboard calculations

Current balance is recorded income minus recorded expenses through today's date in Asia/Colombo, across all months. It is not a live bank balance and does not include future-dated entries. Other summaries use all transactions within the selected calendar month. Monthly savings = income − expenses; it is not the sum of saving goals. Previous-month change = `(current − previous) / abs(previous) × 100`; a zero baseline returns `null`, displayed as no prior baseline. Daily and six-month series include zero-filled dates/months. Money is serialized as decimal strings and converted to numbers only for display/charts. All aggregates and recent transaction queries include the authenticated user's ID.

## Statement import

Preview accepts multipart `file`, optional JSON `mapping`, `day_first` (default true), and `default_type` (default expense). Mapping keys are `transaction_date`, `description`, `merchant`, `amount`, `debit`, `credit`, `transaction_type`, and `category`. A value is a file column name or empty to leave it unmapped. Mapped debit/credit columns take precedence over a mapped amount column; each row must contain only one positive debit or credit. In a single amount column, explicit type takes precedence; otherwise negatives are expenses and positives use the chosen default. Files are capped at 5 MB, 2,000 rows, and 50 columns. XLSX additionally limits decompressed size to 25 MB and 1,000 ZIP entries, uses the first worksheet, does not execute formulas, and disables external links. Malformed CSV column counts are rejected rather than silently shifted or truncated.

Parsing uses pandas, reads monetary text as exact Decimal values, and suggests categories with private confirmed labels, merchant rules, and a saved text classifier. Unrecognized expenses use Other; incomes default to Salary. Invalid rows are returned for correction, not inserted. UTF-8/BOM and Windows-1252 CSVs are supported, with comma, semicolon, tab, and pipe separators. The original UploadFile spool is closed and removed in a `finally` block; parsing uses in-memory buffers and no uploaded statement path is persisted.

Confirmation accepts `{source: 'csv'|'xlsx', transactions: [...]}`. It revalidates every field and category, derives ownership from the token, and commits atomically. Duplicate identity is owner + date + normalized description + amount + direction + normalized merchant; category and source are excluded. Duplicates in the statement and existing manual/imported transactions are skipped. Exact repeated real-world payments with this identity may need manual entry or a corrected description. A PostgreSQL transaction advisory lock per user serializes confirmations, preventing concurrent import duplicates. No preview server state is retained; the client submits only selected corrected transactions. Changing mapping requires reparsing before confirmation.

Implementation references: [FastAPI JWT and password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite), [FastAPI upload files](https://fastapi.tiangolo.com/tutorial/request-files/), [pandas CSV](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html), [pandas Excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html), [Chart.js](https://www.chartjs.org/docs/latest/).


Phases 7–9 add private category labels, trained text classification, chronological expense forecasting and unusual-spending records. See [intelligence architecture](intelligence.md) for endpoint contracts, model selection, ownership, and limitations.
