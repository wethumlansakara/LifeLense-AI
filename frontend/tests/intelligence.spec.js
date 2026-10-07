import { test, expect } from '@playwright/test';

async function register(page) {
  await page.goto('/register');
  await page.getByLabel('Full name').fill('Intelligence Browser');
  await page.getByLabel('Email address').fill(`intelligence-browser-${Date.now()}@example.com`);
  await page.getByLabel('Password', { exact: true }).fill('intelligence-browser-long-password');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByTestId('expenses')).toHaveText('Rs. 0.00');
}

test('automatic category suggestion, correction learning and private dataset download', async ({ page }) => {
  await register(page);
  await page.getByRole('button', { name: 'Add transaction', exact: true }).first().click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('Description').fill('Weekly basket');
  await dialog.getByLabel('Merchant').fill('KEELLS Colombo 123');
  const options = await dialog.getByLabel('Category', { exact: true }).locator('option').allTextContents();
  expect(options).toContain('Groceries');
  await expect(dialog.locator('.category-assistant')).toContainText('Groceries');
  await expect(dialog.getByLabel('Category', { exact: true }).locator('option:checked')).toHaveText('Groceries');
  await dialog.getByLabel('Amount (LKR)').fill('1500');
  await dialog.getByLabel('Category', { exact: true }).selectOption({ label: 'Shopping' });
  await dialog.getByRole('button', { name: 'Add transaction', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole('button', { name: 'Add transaction', exact: true }).first().click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Description').fill('Another basket');
  await dialog.getByLabel('Merchant').fill('Keells');
  await expect(dialog.locator('.category-assistant')).toContainText('Shopping');
  await expect(dialog.locator('.category-assistant')).toContainText('personal correction');
  const downloadPromise = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'Download my confirmed labels' }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('lifelens-training-labels.csv');
  await dialog.getByRole('button', { name: 'Train a private model from my labels' }).click();
  await expect(dialog.getByRole('alert')).toContainText('at least 20 distinct');
});

test('forecast fallback, unusual warning explanation, mark normal and restore', async ({ page }) => {
  await register(page);
  await expect(page.getByText('History makes the picture clearer.')).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem('lifelens-token'));
  const headers = { Authorization: `Bearer ${token}` };
  const categories = await (await page.request.get('/api/categories', { headers })).json();
  const food = categories.find(c => c.name === 'Food').id;
  for (let index = 0; index < 6; index++) {
    const response = await page.request.post('/api/transactions', { headers, data: { description: index === 5 ? 'Celebration dinner' : 'Regular lunch', merchant: 'Garden Cafe', amount: index === 5 ? '18500' : '2000', transaction_date: `2026-09-${String(index + 1).padStart(2, '0')}`, transaction_type: 'expense', category_id: food } });
    expect(response.status()).toBe(201);
  }
  await page.reload();
  await expect(page.getByTestId('forecast-amount')).toContainText('Rs. 28,500.00');
  await expect(page.getByText('Recent-month average', { exact: true })).toBeVisible();
  await expect(page.getByText('low confidence', { exact: true })).toBeVisible();
  await expect(page.locator('.unusual-item')).toContainText('earlier');
  await expect(page.locator('.unusual-item')).toContainText('18,500.00');
  await page.getByRole('button', { name: 'Mark as normal', exact: true }).click();
  await expect(page.locator('.unusual-item')).toHaveCount(0);
  await page.getByLabel('Show transactions marked normal').check();
  await expect(page.getByRole('button', { name: 'Restore warning' })).toBeVisible();
  await page.getByRole('button', { name: 'Restore warning' }).click();
  await expect(page.getByRole('button', { name: 'Mark as normal', exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
