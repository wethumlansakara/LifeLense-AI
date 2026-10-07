import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

async function register(page){
 const email='reports-browser-'+Date.now()+'-'+Math.random().toString(36).slice(2)+'@example.com';
 await page.goto('/register');await page.getByLabel('Full name').fill('Report Browser');
 await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill('report-browser-long-password');
 await page.getByRole('button',{name:'Create account'}).click();await expect(page.getByTestId('expenses')).toHaveText('Rs. 0.00');
 return email;
}

test('reports preview, PDF download, historical snapshot, delete confirmation',async({page})=>{
 await register(page);await page.getByRole('link',{name:'Reports',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Report preview'})).toBeVisible();
 const downloadPromise=page.waitForEvent('download');
 await page.getByRole('button',{name:'Generate PDF',exact:true}).click();
 const download=await downloadPromise;
 expect(download.suggestedFilename()).toMatch(/^lifelens-\d{4}-\d{2}-\d+\.pdf$/);
 const bytes=await readFile(await download.path());expect(bytes.subarray(0,4).toString()).toBe('%PDF');
 await expect(page.locator('.report-history article')).toHaveCount(1);
 await page.reload();await expect(page.locator('.report-history article')).toHaveCount(1);
 await page.locator('.history-open').click();await expect(page.getByRole('heading',{name:/Saved report #/})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'../.local/reports-mobile.png',fullPage:true});
 await page.locator('.report-history article button[aria-label^="Delete"]').click();
 await page.getByRole('dialog').getByRole('button',{name:'Delete report',exact:true}).click();
 await expect(page.locator('.report-history article')).toHaveCount(0);
});

test('settings dark mode persists, analytics chart page, escaped financial text',async({page})=>{
 await register(page);await page.getByRole('link',{name:'Settings',exact:true}).first().click();
 await page.getByRole('button',{name:'Dark',exact:true}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await page.reload();await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await page.getByRole('link',{name:'Analytics',exact:true}).click();await expect(page.getByRole('heading',{name:'Spending analytics',exact:true})).toBeVisible();
 await expect(page.locator('canvas')).toHaveCount(4);
 await page.screenshot({path:'../.local/analytics-dark.png',fullPage:true});
 await page.getByRole('link',{name:'Saving goals',exact:true}).click();await page.getByRole('button',{name:'Create goal',exact:true}).click();
 const dialog=page.getByRole('dialog');
 const payload='<img src=x onerror="window.xssExecuted=true">';
 await dialog.getByLabel('Goal name').fill(payload);await dialog.getByLabel('Target amount').fill('1000');await dialog.getByLabel('Target date').fill('2027-06-01');await dialog.getByRole('button',{name:'Save goal'}).click();
 await expect(page.locator('.goal-card')).toContainText(payload);
 expect(await page.evaluate(()=>window.xssExecuted)).toBeUndefined();await expect(page.locator('.goal-card img')).toHaveCount(0);
 await page.getByRole('link',{name:'Settings',exact:true}).first().click();await page.getByRole('button',{name:'Light',exact:true}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
});

test('complete finance workflow from registration and login to generated report',async({page})=>{
 const email=await register(page);
 await page.locator('.profile summary').click();await page.getByRole('button',{name:'Sign out'}).click();
 await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill('report-browser-long-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByTestId('income')).toHaveText('Rs. 0.00');
 await page.getByRole('button',{name:'Add transaction',exact:true}).first().click();
 let dialog=page.getByRole('dialog');await dialog.getByLabel('Description').fill('October salary');await dialog.getByRole('button',{name:'Income',exact:true}).click();await dialog.getByLabel('Category',{exact:true}).selectOption({label:'Salary'});await dialog.getByLabel('Amount (LKR)').fill('95000');await dialog.getByLabel('Date',{exact:true}).fill('2026-10-01');await dialog.getByRole('button',{name:'Add transaction',exact:true}).click();
 await expect(page.getByTestId('income')).toHaveText('Rs. 95,000.00');
 await page.getByRole('button',{name:'Add transaction',exact:true}).first().click();dialog=page.getByRole('dialog');
 await dialog.getByLabel('Description').fill('Weekly groceries');await dialog.getByLabel('Merchant').fill('Keells');await dialog.getByLabel('Amount (LKR)').fill('6850');await dialog.getByLabel('Date',{exact:true}).fill('2026-10-05');
 await expect(dialog.locator('.category-assistant')).toContainText('Groceries');await dialog.getByRole('button',{name:'Add transaction',exact:true}).click();
 await page.getByRole('link',{name:'Import statement',exact:true}).click();
 const lines=['Date,Description,Merchant,Debit,Credit',...Array.from({length:6},(_,i)=>'2026-09-0'+(i+1)+',Restaurant lunch,Garden Cafe,'+(i===5?'18500':'2000')+','),'2026-09-07,Weekly basket,Keells,500,'].join('\n');
 await page.getByLabel('Bank statement file').setInputFiles({name:'statement.csv',mimeType:'text/csv',buffer:Buffer.from(lines)});
 await page.getByRole('button',{name:'Preview statement',exact:true}).click();
 await expect(page.getByLabel('Row 8 category').locator('option:checked')).toHaveText('Groceries');
 for(let row=2;row<=7;row++)await page.getByLabel('Row '+row+' category').selectOption({label:'Food'});
 await page.getByRole('button',{name:'Confirm import (7)',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Your finances, brought together.'})).toBeVisible();
 await page.getByRole('link',{name:'Overview',exact:true}).click();await expect(page.getByTestId('expenses')).toHaveText('Rs. 6,850.00');
 await expect(page.getByTestId('forecast-amount')).toContainText('Rs. 29,000.00');await expect(page.locator('.unusual-item')).toContainText('18,500.00');
 await page.getByRole('link',{name:'Ask LifeLens',exact:true}).click();await page.getByLabel('Ask something').fill('Why did I spend more this month?');await page.getByRole('button',{name:'Send',exact:true}).click();await expect(page.locator('.chat-answer')).toContainText('6,850.00');
 await page.getByRole('link',{name:'Saving goals',exact:true}).click();await page.getByRole('button',{name:'Create goal',exact:true}).click();dialog=page.getByRole('dialog');
 await dialog.getByLabel('Goal name').fill('New Laptop');await dialog.getByLabel('Target amount').fill('300000');await dialog.getByLabel('Saved amount').fill('120000');await dialog.getByLabel('Target date').fill('2027-06-07');await dialog.getByRole('button',{name:'Save goal'}).click();await expect(page.locator('.goal-card')).toContainText('40.0%');
 await page.getByRole('link',{name:'Reports',exact:true}).click();await expect(page.locator('.report-metrics')).toContainText('Rs. 95,000.00');
 const promise=page.waitForEvent('download');await page.getByRole('button',{name:'Generate PDF',exact:true}).click();const download=await promise;await download.saveAs('../.local/workflow-report.pdf');
 await expect(page.locator('.report-history article')).toHaveCount(1);
});
