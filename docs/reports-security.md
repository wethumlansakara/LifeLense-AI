# Reports, experience and security (phases 13–16)

## Monthly reports

All report routes require authentication and scope data to the current user:

- GET /api/reports/data?month=2026-10-01: live structured preview.
- POST /api/reports with month: save an immutable JSON snapshot.
- GET /api/reports?page=1: paginated private report history, 20 per page.
- GET /api/reports/{id}: retrieve your saved snapshot.
- GET /api/reports/{id}/pdf: generate a PDF from that snapshot in memory.
- DELETE /api/reports/{id}: delete your snapshot.

The report includes income, expenses, surplus savings, savings rate (N/A when income is zero), category ranking, six-month vector chart, active previously detected unusual transactions, grounded insights and a next-month forecast with limitations. Future months are rejected. The current month is month-to-date; future-dated transactions are excluded. Report forecasts are calculated as of the selected month and exclude that month, matching the forecasting service's completed-history policy. Later transactions do not leak into historical forecasts.

The PDF uses ReportLab Platypus with a reusable template, escaped paragraph text, repeating category-table headers and page footers. PDFs are generated in memory on download; raw bank files are never persisted. The JSON snapshot is retained privately until the user deletes it. Editing transactions does not rewrite old reports. Generating another report creates a new version.

## Experience

Authenticated navigation covers Overview, Transactions, Import statement, Analytics, Ask LifeLens, Saving goals, Reports and Settings. Analytics shares the existing owner-scoped dashboard calculations and charts. Settings saves a light/dark preference on this browser and offers account information, sign-out and confirmed chat-history clearing. Mobile navigation uses a two-row grid. Dashboard/report loading skeletons respect reduced-motion preferences. Existing notifications, empty/error states and confirmation dialogs are retained.

## Security controls

- Argon2 password hashing; validated and normalized emails; JWT signature verification, required timestamps and expiry.
- All private database operations use authenticated user IDs; report PDFs and history enforce ownership.
- SQLAlchemy parameterized queries and allowlisted sort fields; React escapes financial text; PDF paragraphs escape markup.
- JSON request size cap 256 KiB; import endpoints have a 6 MiB total multipart/body cap. Parser file limit remains 5 MiB, with row/column/ZIP expansion validation.
- PostgreSQL atomic fixed-window rate limits shared across backend workers: 30 auth requests/IP/minute, 600 general requests/IP/minute, 60 analysis requests/user/minute (IP when unauthenticated). Analysis includes AI calls, report generation, model training and anomaly scans. Retry-After accompanies 429. Database failures fail closed with 503.
- Bucket identifiers use HMAC hashes; IP addresses and tokens are not stored. Old buckets are removed automatically during checks. Limits are configurable using AUTH_RATE_LIMIT, API_RATE_LIMIT and ANALYSIS_RATE_LIMIT.
- The start script disables access logging to avoid recording transaction-search URLs and disables forwarded-header processing so clients cannot spoof rate-limit identities. If deploying behind a reverse proxy, explicitly configure trusted proxies and network access controls rather than accepting arbitrary forwarded headers. Shared-IP users share the general/auth budgets.
- Exception handlers log only exception class names, excluding SQL parameters, payloads and provider error bodies. Settings validation hides secret inputs.
- Backend CORS allows only the configured FRONTEND_ORIGIN; no wildcard credentials. API responses set no-store, nosniff, DENY framing and no-referrer.
- Vite dev/preview adds browser security headers and a Content Security Policy. Production preview uses self-only scripts; development permits inline scripts for Vite React refresh. Inline styles are allowed for React styles and charts. A deployed static host must apply the equivalent headers and use HTTPS; Vite config does not configure an external host.
- Secrets remain in backend environment variables. Git ignores env files, uploads, bank-statement folders, PDF/XLSX/XLS/CSV files, private ML data and artifacts. Only the explicitly named synthetic starter and sample-statement CSVs are exempt.
- AI receives only verified structured facts and approved suggestion IDs; no raw questions, merchants, descriptions, bank statements or unrestricted database access.

The fixed-window limiter allows a boundary burst. It is application-level protection and does not replace infrastructure connection/body timeouts or network-level denial-of-service controls. Goal fund additions are locked but are not retry-idempotent. LLM-generated insight selection remains optional and falls back to verified local analysis.

## Dependency checks

Ran npm audit and pip-audit on October 7, 2026. Both finished with zero known vulnerabilities after upgrading the local pip installer from 25.3 to 26.2.1. These are point-in-time advisory checks, not a guarantee against all security issues.

```powershell
cd backend
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip_audit
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m alembic check
cd ../frontend
npm.cmd audit
npm.cmd run build
npm.cmd run test:e2e
```

Re-run audits after dependency changes and regularly in deployment maintenance. [Manual end-to-end test](manual-test.md) covers the complete user journey.
