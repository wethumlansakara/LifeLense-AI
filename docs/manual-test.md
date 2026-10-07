# Complete manual finance test

Run the local database, migrations, backend and frontend using README commands. Use a fresh test account. This script uses October 2026 and is repeatable by explicitly selecting that month. On a date before October 7, 2026, choose equivalent past dates instead.

1. **Register:** create a unique email and a password of at least 12 characters. Expected: empty dashboard, private workspace, zero balances.
2. **Login:** sign out using the profile menu, then sign in with the same account. Try a wrong password first; expect a generic error without a session.
3. **Add income:** add “October salary”, Income, Salary, Rs. 95,000, October 1, 2026. Expected: October income Rs. 95,000.
4. **Add expense:** add “Weekly groceries”, merchant Keells, Expense, Rs. 6,850, October 5. Expected: Groceries suggested automatically; October expenses Rs. 6,850.
5. **Upload a statement:** save the following synthetic CSV outside version control, then open Import statement. Preview, review the categories and confirm seven records. Set the six restaurant rows to Food if necessary; Keells should suggest Groceries.

   ```csv
   Date,Description,Merchant,Debit,Credit
   2026-09-01,Restaurant lunch,Garden Cafe,2000,
   2026-09-02,Restaurant lunch,Garden Cafe,2000,
   2026-09-03,Restaurant lunch,Garden Cafe,2000,
   2026-09-04,Restaurant lunch,Garden Cafe,2000,
   2026-09-05,Restaurant lunch,Garden Cafe,2000,
   2026-09-06,Restaurant celebration,Garden Cafe,18500,
   2026-09-07,Weekly basket,Keells,500,
   ```

6. **Dashboard:** select October 2026. Expected: income Rs. 95,000, expenses Rs. 6,850, savings Rs. 88,150. September expenses are Rs. 29,000. Charts and previous-month comparisons use these recorded amounts.
7. **Categorization:** verify Keells is Groceries in the form and import preview. These known merchants use rules before ML. For the classifier path, use the existing saved synthetic model with an unknown merchant/description, or collect at least 20 distinct private confirmed examples across two categories and train in the transaction form. Model scores are estimates; correct labels when needed.
8. **Prediction:** expect a simple average of Rs. 29,000 with low confidence from the one completed historical month. This sparse history must not claim a reliable regression prediction.
9. **Unusual transaction:** expect the Rs. 18,500 restaurant entry to be flagged relative to the five earlier Rs. 2,000 entries. Review the explanation, mark normal, enable dismissed warnings, and restore the warning.
10. **Ask LifeLens:** ask “Why did I spend more this month?” Expected: it reports the actual decrease versus September rather than agreeing with the premise. Try “How much did I spend on groceries?” and “Compare September and October 2026.” Reload: your history persists. The source shows local analysis if the provider is not configured.
11. **Goal:** create New Laptop, target Rs. 300,000, saved Rs. 120,000, June 7, 2027. Expected: 40% progress and Rs. 180,000 remaining. Add Rs. 30,000: 50% progress and Rs. 150,000 remaining. Account balance is unchanged by goal allocations.
12. **Report:** open Reports, select October 2026, Generate PDF. Expected: a downloadable valid PDF with income, expenses, savings, savings rate, categories, vector trend chart, recorded unusual transactions, insights and forecast limitations. Current-month report is labeled month-to-date.
13. **Historical snapshot:** reload Reports and download the saved report. Edit a transaction, then reopen that saved report: its original values remain. Generate a new report to capture revised values. Delete a saved report using the confirmation dialog.
14. **Appearance and mobile:** Settings → Dark, reload, verify persistence. Open Analytics and review chart readability. Switch to Light. At 390px width, all eight navigation links are available, pages fit the screen and wide transaction tables scroll internally.
15. **Privacy:** create a second account. Its transactions, chat, goals and report library must be empty; copied report/goal/transaction IDs from the first account return 404. Expired tokens return 401. Injection-like descriptions and goal names render as literal text.
16. **Errors and limits:** temporarily stop the backend: expect a useful connection error and retry option. Repeated login attempts from one client eventually return 429 with Retry-After. Large requests are rejected before parsing; statements over 5 MB and invalid file formats are rejected. Restore services after testing.

Automated equivalents are in backend/tests and frontend/tests. The complete browser workflow is frontend/tests/reports-security.spec.js; it writes its synthetic sample PDF into ignored .local/workflow-report.pdf. It exercises rule categorization; private ML training and evaluation have separate backend tests.
