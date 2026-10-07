import { test, expect } from '@playwright/test';

async function register(page) {
  await page.goto('/register');
  await page.getByLabel('Full name').fill('Finance Browser');
  await page.getByLabel('Email address').fill(`finance-browser-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`);
  await page.getByLabel('Password', { exact: true }).fill('finance-browser-test-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByTestId('expenses')).toHaveText('Rs. 0.00');
}

test('transactions CRUD, dashboard charts, details, filters, sorting and pagination', async ({ page }) => {
  await register(page);
  await page.getByRole('button', { name: 'Add transaction', exact: true }).first().click();
  let dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Income', exact: true }).click();
  await dialog.getByLabel('Description').fill('October salary');
  await dialog.getByLabel('Amount (LKR)').fill('95000');
  await dialog.getByLabel('Date', { exact: true }).fill('2026-10-01');
  await dialog.getByLabel('Category', { exact: true }).selectOption({ label: 'Salary' });
  await dialog.getByLabel('Merchant').fill('Employer');
  await dialog.getByRole('button', { name: 'Add transaction', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByLabel('Dashboard month').fill('2026-10');
  await expect(page.getByTestId('income')).toHaveText('Rs. 95,000.00');
  await page.getByRole('link', { name: 'Transactions', exact: true }).click();
  await page.getByRole('button', { name: 'Add transaction', exact: true }).first().click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Description').fill('Weekly groceries');
  await dialog.getByLabel('Amount (LKR)').fill('6850');
  await dialog.getByLabel('Date', { exact: true }).fill('2026-10-05');
  await dialog.getByLabel('Category', { exact: true }).selectOption({ label: 'Groceries' });
  await dialog.getByLabel('Merchant').fill('Keells');
  await dialog.getByRole('button', { name: 'Add transaction', exact: true }).click();
  await expect(page.getByRole('cell', { name: '−Rs. 6,850.00', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'View Weekly groceries' }).click();
  await expect(page.getByRole('dialog')).toContainText('Keells');
  await expect(page.getByRole('dialog')).toContainText('05 Oct 2026');
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Edit Weekly groceries' }).click();
  await page.getByRole('dialog').getByLabel('Amount (LKR)').fill('7000.50');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('cell', { name: '−Rs. 7,000.50', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByLabel('Dashboard month').fill('2026-10');
  await expect(page.getByTestId('expenses')).toHaveText('Rs. 7,000.50');
  await expect(page.getByTestId('savings')).toHaveText('Rs. 87,999.50');
  await expect(page.locator('canvas')).toHaveCount(5);
  await page.getByRole('link', { name: 'Transactions', exact: true }).click();
  const token = await page.evaluate(() => sessionStorage.getItem('lifelens-token'));
  const categories = await (await page.request.get('/api/categories', { headers: { Authorization: `Bearer ${token}` } })).json();
  const food = categories.find(c => c.name === 'Food').id;
  for (let i = 0; i < 11; i++) {
    const response = await page.request.post('/api/transactions', { headers: { Authorization: `Bearer ${token}` }, data: { category_id: food, description: `Coffee ${i}`, merchant: 'Cafe', amount: `${i + 1}.00`, transaction_date: '2026-09-01', transaction_type: 'expense' } });
    expect(response.status()).toBe(201);
  }
  await page.reload();
  await expect(page.getByText('Page 1 of 2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.getByText('Page 2 of 2', { exact: true })).toBeVisible();
  await page.getByLabel('Search transactions').fill('Keells');
  await expect(page.getByRole('row')).toHaveCount(2);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await page.getByLabel('Category', { exact: true }).selectOption({ label: 'Food' });
  await page.getByLabel('Type', { exact: true }).selectOption('expense');
  await page.getByLabel('From', { exact: true }).fill('2026-09-01');
  await page.getByLabel('To', { exact: true }).fill('2026-09-30');
  await page.getByLabel('Sort transactions', { exact: true }).selectOption('amount:asc');
  await expect(page.locator('tbody tr').first()).toContainText('−Rs. 1.00');
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await page.getByLabel('Search transactions').fill('Weekly groceries');
  await page.getByRole('button', { name: 'Delete Weekly groceries' }).click();
  await page.getByRole('button', { name: 'Delete transaction', exact: true }).click();
  await expect(page.getByText('No matching transactions.')).toBeVisible();
});

test('CSV preview, corrections, duplicate skipping, confirmation and mobile layout', async ({ page }) => {
  await register(page);
  await page.getByRole('link', { name: 'Import statement', exact: true }).click();
  const csv = 'Date,Description,Merchant,Debit,Credit\n05/10/2026,Coffee,Cafe,1200,,\n01/10/2026,Salary,Employer,,95000\nwrong,Broken,Shop,abc,\n05/10/2026,Coffee,Cafe,1200,\n';
  // Keep every record consistent with the five-column header.
  const statement = csv.replace('1200,,\n', '1200,\n');
  await page.getByLabel('Bank statement file').setInputFiles({ name: 'statement.csv', mimeType: 'text/csv', buffer: Buffer.from(statement) });
  await page.getByRole('button', { name: 'Preview statement', exact: true }).click();
  await expect(page.getByText('4 rows · 3 parsed · 1 need attention · 1 possible duplicates')).toBeVisible();
  await expect(page.getByLabel('Include row 5')).not.toBeChecked();
  await page.getByLabel('Row 4 date').fill('2026-10-05');
  await page.getByLabel('Row 4 amount').fill('100.25');
  await page.getByLabel('Include row 4').check();
  await page.getByRole('button', { name: 'Confirm import (3)', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your finances, brought together.' })).toBeVisible();
  await page.getByRole('link', { name: 'View transactions', exact: true }).click();
  await expect(page.getByRole('row')).toHaveCount(4);
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByLabel('Dashboard month').fill('2026-10');
  await expect(page.getByTestId('income')).toHaveText('Rs. 95,000.00');
  await expect(page.getByTestId('expenses')).toHaveText('Rs. 1,300.25');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('link', { name: 'Import statement', exact: true }).click();
  await page.getByLabel('Bank statement file').setInputFiles({ name: 'statement.csv', mimeType: 'text/csv', buffer: Buffer.from(statement) });
  await page.getByRole('button', { name: 'Preview statement', exact: true }).click();
  await expect(page.getByText('4 rows · 3 parsed · 1 need attention · 3 possible duplicates')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirm import (0)', exact: true })).toBeDisabled();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
