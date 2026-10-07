import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, ArrowRight, CalendarDays, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, CreditCard, Download, Eye, FileUp, LayoutDashboard, Leaf, LogOut, Pencil, Plus, Search, ShieldCheck, Trash2, TrendingUp, Wallet, X } from 'lucide-react';
import Chart from 'chart.js/auto';
import { api } from './api';
import { useAuth } from './auth';
import './finance.css';
import { CategoryAssistant, IntelligencePanels } from './intelligence';
import { AskLifeLens, SavingGoals, InsightCard } from './ai-goals';
import { Reports, Settings, Skeleton } from './reports-settings';

const FinanceContext = createContext(null);
export const useFinance = () => useContext(FinanceContext);
export const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Colombo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const currency = value => `Rs. ${Number(value || 0).toLocaleString('en-LK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const shortMoney = value => Number(value).toLocaleString('en-LK', { maximumFractionDigits: 0 });
const displayDate = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
const monthLabel = value => new Date(`${value.slice(0, 7)}-01T12:00:00`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
const chartColors = ['#285746', '#a4bd8c', '#d6aa75', '#789ea2', '#9d8fb4', '#bccbae', '#d38e7c', '#8fb28f', '#a8a59c', '#596f83', '#c1b8d0'];

function useResource(path, refresh = 0) {
  const { request } = useFinance();
  const [data, setData] = useState(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(true); const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setError(''); setData(null);
    request(path).then(value => { if (active) setData(value); }).catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, refresh, retry, request]);
  return { data, error, loading, retry: () => setRetry(v => v + 1) };
}
function ErrorNotice({ message, retry }) { return message ? <div className="finance-error" role="alert"><span>{message}</span>{retry && <button onClick={retry}>Try again</button>}</div> : null; }
function Empty({ title = 'A fresh start.', text = 'Add a transaction or import a statement to see your money in focus.', action = true }) {
  const { openEditor } = useFinance();
  return <div className="empty-state"><span className="empty-icon"><Wallet size={25}/></span><h3>{title}</h3><p>{text}</p>{action && <button className="finance-primary" onClick={() => openEditor()}><Plus size={16}/> Add transaction</button>}</div>;
}

export default function FinanceApp() {
  const { user, token, logout } = useAuth();
  const [categories, setCategories] = useState([]); const [categoryError, setCategoryError] = useState(''); const [categoryRetry, setCategoryRetry] = useState(0);
  const [revision, setRevision] = useState(0); const [editor, setEditor] = useState(null); const [notice, setNotice] = useState('');
  const location = useLocation();
  const request = useCallback(async (path, options = {}) => {
    try { return await api(path, { ...options, token }); }
    catch (error) { if (error.status === 401) logout(); throw error; }
  }, [token]);
  useEffect(() => {
    let active = true; setCategoryError('');
    request('/categories').then(value => { if (active) setCategories(value); }).catch(error => { if (active) setCategoryError(error.message); });
    return () => { active = false; };
  }, [request, categoryRetry]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 6000); return () => clearTimeout(timer); }, [notice]);
  const changed = message => { setRevision(v => v + 1); setNotice(message); };
  const openEditor = (transaction = null) => setEditor({ transaction });
  return <FinanceContext.Provider value={{ categories, request, revision, changed, openEditor }}><div className="finance-app"><aside className="finance-sidebar"><Link to="/" className="brand"><span className="brand-icon"><Leaf size={24}/></span>LifeLens<span className="ai">AI</span></Link><span className="nav-caption">YOUR FINANCIAL SPACE</span><nav aria-label="Main navigation"><NavLink to="/" end><LayoutDashboard size={19}/> Overview</NavLink><NavLink to="/transactions"><CreditCard size={19}/> Transactions</NavLink><NavLink to="/import"><FileUp size={19}/> Import statement</NavLink><NavLink to="/analytics"><TrendingUp size={19}/> Analytics</NavLink><NavLink to="/reports"><Download size={19}/> Reports</NavLink><NavLink to="/settings"><ShieldCheck size={19}/> Settings</NavLink><NavLink to="/ask"><CircleHelp size={19}/> Ask LifeLens</NavLink><NavLink to="/goals"><Wallet size={19}/> Saving goals</NavLink></nav><div className="sidebar-bottom"><div className="sidebar-note"><span className="sidebar-leaf"><Leaf size={29}/></span><h3>Small steps.<br/>A brighter future.</h3><p>A little awareness goes a long way. Keep your money in focus.</p><Link to="/import">Bring your finances together <ArrowRight size={15}/></Link></div><span className="sidebar-security"><ShieldCheck size={15}/> Your own private workspace</span></div></aside><div className="finance-content"><header className="finance-topbar"><span className="breadcrumb">Your workspace <span>/</span> <strong>{location.pathname === '/reports' ? 'Reports' : location.pathname === '/settings' ? 'Settings' : location.pathname === '/analytics' ? 'Analytics' : location.pathname === '/ask' ? 'Ask LifeLens' : location.pathname === '/goals' ? 'Saving goals' : location.pathname === '/transactions' ? 'Transactions' : location.pathname === '/import' ? 'Import statement' : 'Overview'}</strong></span><details className="profile"><summary><span className="avatar">{user.name.charAt(0).toUpperCase()}</span><span>{user.name}</span><ChevronDown size={16}/></summary><div className="profile-menu"><strong>{user.name}</strong><small>{user.email}</small><Link to="/settings">Settings</Link><button onClick={logout}><LogOut size={16}/> Sign out</button></div></details></header><main className="finance-main">{notice && <div className="finance-notice" role="status" aria-live="polite"><ShieldCheck size={16}/>{notice}<button onClick={() => setNotice('')} aria-label="Dismiss notification"><X size={16}/></button></div>}<ErrorNotice message={categoryError} retry={() => setCategoryRetry(v => v + 1)}/><Routes><Route index element={<Dashboard/>}/><Route path="transactions" element={<Transactions/>}/><Route path="import" element={<StatementImport/>}/><Route path="ask" element={<AskLifeLens/>}/><Route path="goals" element={<SavingGoals/>}/><Route path="analytics" element={<Dashboard analytics/>}/><Route path="reports" element={<Reports/>}/><Route path="settings" element={<Settings/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes><footer className="finance-footer"><span>LifeLens AI · A clearer view of your money.</span><span><span className="dot"/> Your data, your perspective</span></footer></main></div></div>{editor && <TransactionEditor transaction={editor.transaction} close={() => setEditor(null)}/>}</FinanceContext.Provider>;
}

function FinancialChart({ type, data, options = {}, label }) {
  const canvas = useRef(null);
  useEffect(() => {
    const dark = document.documentElement.dataset.theme === 'dark';
    const chart = new Chart(canvas.current, {
      type, data,
      options: { responsive: true, maintainAspectRatio: false, animation: { duration: 400 }, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 7, padding: 20, font: { size: 11 }, color: dark ? '#bccdb3' : '#7e897f' } }, tooltip: { backgroundColor: '#203e32', padding: 12, callbacks: { label: context => `${context.dataset.label || context.label}: ${currency(context.parsed.y ?? context.parsed)}` } } },
        ...(type !== 'doughnut' ? { scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color: dark ? '#bccdb3' : '#8a948a', font: { size: 10 }, maxTicksLimit: 8 } }, y: { beginAtZero: true, border: { display: false }, grid: { color: dark ? '#3c5041' : '#edf0e9' }, ticks: { color: dark ? '#bccdb3' : '#8a948a', font: { size: 10 }, maxTicksLimit: 5, callback: value => Math.abs(value) >= 1000 ? `${shortMoney(value / 1000)}k` : shortMoney(value) } } } } : { cutout: '76%' }), ...options,
      },
    });
    return () => chart.destroy();
  }, [type, data, options]);
  return <div className="chart-canvas"><canvas ref={canvas} role="img" aria-label={label}/></div>;
}

function Change({ value, expense = false }) {
  if (value === null || value === undefined) return <span className="change neutral">No previous-month baseline</span>;
  const favorable = expense ? value <= 0 : value >= 0;
  return <span className={`change ${favorable ? 'positive' : 'negative'}`}><TrendingUp size={12}/>{value > 0 ? '+' : ''}{value.toLocaleString()}% <span>vs. previous month</span></span>;
}

function Dashboard({ analytics = false }) {
  const { revision, openEditor, request } = useFinance();
  const [month, setMonth] = useState(today().slice(0, 7));
  const resource = useResource(`/dashboard?month=${month}-01`, revision);
  const data = resource.data; const monthly = data?.monthly || [];
  const monthNames = monthly.map(row => new Date(`${row.month}T12:00:00`).toLocaleDateString('en-GB', { month: 'short' }));
  return <div><div className="page-heading"><div><span className="eyebrow">THE BIG PICTURE</span><h1>{analytics ? 'Spending analytics' : <>Your money, in focus<span>.</span></>}</h1><p>A little clarity today. More possibility tomorrow.</p></div><div className="heading-actions"><label className="month-picker"><CalendarDays size={16}/><input aria-label="Dashboard month" type="month" min="1900-01" max="9998-12" value={month} onChange={e => e.target.value && setMonth(e.target.value)}/></label><button className="finance-primary" onClick={() => openEditor()}><Plus size={16}/> Add transaction</button></div></div><ErrorNotice message={resource.error} retry={resource.retry}/>{resource.loading ? <Skeleton rows={4}/> : data && <><div className="summary-grid"><article className="balance-card"><div className="summary-label"><Wallet size={17}/> Current balance<span>LKR</span></div><h2 data-testid="balance">{currency(data.balance)}</h2><p>Net recorded income − expenses</p><span className="balance-bottom">As of {displayDate(data.as_of)}<ArrowUpRight size={18}/></span><Leaf className="balance-decoration" size={130}/></article><article className="summary-card"><span className="summary-icon income"><ArrowDownLeft size={20}/></span><div className="summary-label">{monthLabel(month).split(' ')[0]} income</div><h2 data-testid="income">{currency(data.income)}</h2><Change value={data.changes.income}/></article><article className="summary-card"><span className="summary-icon expense"><ArrowUpRight size={20}/></span><div className="summary-label">{monthLabel(month).split(' ')[0]} expenses</div><h2 data-testid="expenses">{currency(data.expenses)}</h2><Change value={data.changes.expenses} expense/></article><article className="summary-card"><span className="summary-icon savings"><Leaf size={20}/></span><div className="summary-label">Monthly savings</div><h2 data-testid="savings">{currency(data.savings)}</h2><Change value={data.changes.savings}/></article></div><div className="chart-grid"><section className="chart-panel wide"><div className="panel-heading"><div><h2>Money in. Money out.</h2><p>Income and expenses, side by side</p></div><span className="panel-tag">MONTHLY COMPARISON</span></div><FinancialChart type="bar" label="Income versus expenses for the previous and selected month" data={{ labels: [monthLabel(data.previous.month), monthLabel(data.month)], datasets: [{ label: 'Income', data: [Number(data.previous.income), Number(data.income)], backgroundColor: '#285746', borderRadius: 6, maxBarThickness: 42 }, { label: 'Expenses', data: [Number(data.previous.expenses), Number(data.expenses)], backgroundColor: '#b5c998', borderRadius: 6, maxBarThickness: 42 }] }}/><div className="chart-footnote"><CircleHelp size={14}/> Savings are income minus expenses, not your saving-goal balance.</div></section><section className="chart-panel"><div className="panel-heading"><div><h2>Where it goes</h2><p>Spending by category</p></div><span className="panel-dot"><Leaf size={16}/></span></div>{data.categories.length ? <><div className="donut-wrap"><FinancialChart type="doughnut" label="Expense breakdown by category" options={{ plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.label}: ${currency(context.parsed)}` } } } }} data={{ labels: data.categories.map(c => c.name), datasets: [{ data: data.categories.map(c => Number(c.amount)), backgroundColor: chartColors, borderWidth: 4, borderColor: '#fff', hoverOffset: 3 }] }}/><div className="donut-center"><span>Total spent</span><strong>{currency(data.expenses)}</strong></div></div><div className="category-legend">{data.categories.map((c, i) => <div key={c.id}><span><i style={{ background: chartColors[i % chartColors.length] }}/>{c.name}</span><strong>{c.percentage}%</strong></div>)}</div><div className="top-category"><span>Top spending category</span><strong>{data.top_category}</strong></div></> : <Empty title="A clean slate." text="Your spending breakdown will appear after your first expense." action={false}/>}</section><section className="chart-panel"><div className="panel-heading"><div><h2>Your spending rhythm</h2><p>Monthly expenses over six months</p></div></div><FinancialChart type="line" label="Monthly expenses over six months" data={{ labels: monthNames, datasets: [{ label: 'Expenses', data: monthly.map(row => Number(row.expenses)), borderColor: '#6d8e5b', backgroundColor: '#b5c99825', fill: true, tension: .35, pointRadius: 4, pointBackgroundColor: '#fff', pointBorderWidth: 2 }] }}/></section><section className="chart-panel wide"><div className="panel-heading"><div><h2>The everyday picture</h2><p>Daily spending in {monthLabel(month)}</p></div><span className="panel-tag">DAY BY DAY</span></div><FinancialChart type="line" label="Daily spending for the selected month" data={{ labels: data.daily.map(row => Number(row.date.slice(-2))), datasets: [{ label: 'Expenses', data: data.daily.map(row => Number(row.expenses)), borderColor: '#285746', backgroundColor: '#2857460d', fill: true, tension: .3, pointRadius: 2, pointHoverRadius: 5 }] }}/></section><section className="chart-panel full"><div className="panel-heading"><div><h2>A longer perspective</h2><p>Your six-month financial trend</p></div><span className="panel-tag">{monthLabel(monthly[0].month)} — {monthLabel(month)}</span></div><FinancialChart type="bar" label="Six month income, expenses and savings trend" data={{ labels: monthNames, datasets: [{ label: 'Income', data: monthly.map(row => Number(row.income)), backgroundColor: '#285746', borderRadius: 4, maxBarThickness: 30 }, { label: 'Expenses', data: monthly.map(row => Number(row.expenses)), backgroundColor: '#b5c998', borderRadius: 4, maxBarThickness: 30 }, { type: 'line', label: 'Savings', data: monthly.map(row => Number(row.savings)), borderColor: '#c79c6b', pointBackgroundColor: '#c79c6b', tension: .3, order: -1 }] }}/></section></div><InsightCard month={month} revision={revision} request={request}/><IntelligencePanels request={request} revision={revision} openEditor={openEditor}/><section className="transaction-panel"><div className="panel-heading"><div><h2>Recent transactions</h2><p>The latest entries in {monthLabel(month)}</p></div><Link className="inline-link" to="/transactions">View all transactions <ArrowRight size={15}/></Link></div>{data.recent_transactions.length ? <TransactionTable transactions={data.recent_transactions} compact/> : <Empty/>}</section></>}</div>;
}

function Modal({ title, children, close, className = '' }) {
  const ref = useRef(null);
  useEffect(() => { const dialog = ref.current; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog className={`finance-modal ${className}`} ref={ref} aria-label={title} onCancel={e => { e.preventDefault(); close(); }}><div className="modal-heading"><div><span className="eyebrow">YOUR FINANCIAL RECORD</span><h2>{title}</h2></div><button className="icon-button" aria-label="Close dialog" onClick={close}><X size={20}/></button></div>{children}</dialog>;
}

function TransactionEditor({ transaction, close }) {
  const { categories, request, changed } = useFinance();
  const [direction, setDirection] = useState(transaction?.transaction_type || 'expense');
  const [description, setDescription] = useState(transaction?.description || '');
  const [merchant, setMerchant] = useState(transaction?.merchant || '');
  const [category, setCategory] = useState(String(transaction?.category_id || ''));
  const [manualCategory, setManualCategory] = useState(Boolean(transaction));
  const [suggestion, setSuggestion] = useState(null);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [suggestionError, setSuggestionError] = useState('');
  const [training, setTraining] = useState(false);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const available = categories.filter(c => c.type === direction);
  useEffect(() => {
    let active = true;
    setSuggestionError(''); setSuggestionLoading(false);
    if (!description.trim() && !merchant.trim()) { setSuggestion(null); return; }
    const timer = setTimeout(() => {
      setSuggestionLoading(true);
      request('/intelligence/suggest-category', { method: 'POST', body: JSON.stringify({ description: description.trim() || merchant.trim(), merchant: merchant.trim(), transaction_type: direction }) })
        .then(value => { if (active) { setSuggestion(value); if (!manualCategory && value.category_id) setCategory(String(value.category_id)); } })
        .catch(err => { if (active) setSuggestionError(err.message); })
        .finally(() => { if (active) setSuggestionLoading(false); });
    }, 350);
    return () => { active = false; clearTimeout(timer); };
  }, [description, merchant, direction, manualCategory, request]);
  function chooseDirection(value) { setDirection(value); setCategory(''); setManualCategory(false); }
  async function trainModel() {
    setTraining(true); setError('');
    try {
      const metadata = await request('/intelligence/train-category-model', { method: 'POST' });
      const score = metadata.metrics[metadata.selected_model];
      changed(`Private category model trained on ${metadata.samples} labels. Holdout accuracy ${(score.accuracy * 100).toFixed(1)}%, macro-F1 ${score.macro_f1.toFixed(3)}.`);
    } catch (err) { setError(err.message); } finally { setTraining(false); }
  }
  async function downloadLabels() {
    try {
      const csv = await request('/intelligence/training-dataset', { responseType: 'text' });
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const link = document.createElement('a'); link.href = url; link.download = 'lifelens-training-labels.csv'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err.message); }
  }
  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const body = { description: description.trim(), merchant: merchant.trim() || null, amount: values.amount, transaction_date: values.transaction_date, transaction_type: direction, category_id: manualCategory ? Number(category) : null };
    try {
      await request(transaction ? `/transactions/${transaction.id}` : '/transactions', { method: transaction ? 'PUT' : 'POST', body: JSON.stringify(body) });
      changed(transaction ? 'Transaction updated; your category choice was saved.' : 'Transaction added.'); close();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <Modal title={transaction ? 'Edit transaction' : 'Add a transaction'} close={() => !busy && close()}>
    <form onSubmit={submit}>
      <div className="type-toggle" role="group" aria-label="Transaction type"><button type="button" aria-pressed={direction === 'expense'} className={direction === 'expense' ? 'selected' : ''} onClick={() => chooseDirection('expense')}><ArrowUpRight size={16}/> Expense</button><button type="button" aria-pressed={direction === 'income'} className={direction === 'income' ? 'selected' : ''} onClick={() => chooseDirection('income')}><ArrowDownLeft size={16}/> Income</button></div>
      <div className="form-grid">
        <label className="span-two">Description<input name="description" placeholder="What was this transaction for?" value={description} onChange={e => setDescription(e.target.value)} required maxLength={500} autoFocus/></label>
        <label>Amount (LKR)<input name="amount" type="number" inputMode="decimal" step="0.01" min="0.01" max="999999999999.99" placeholder="0.00" defaultValue={transaction?.amount} required/></label>
        <label>Date<input name="transaction_date" type="date" defaultValue={transaction?.transaction_date || today()} required/></label>
        <label>Category<select aria-label="Category" name="category_id" value={category} onChange={e => { setCategory(e.target.value); setManualCategory(true); }} required><option value="">Choose a category</option>{available.map(c => <option value={c.id} key={c.id}>{c.name}</option>)}</select></label>
        <label>Merchant <span className="optional">optional</span><input name="merchant" placeholder="e.g. Keells" value={merchant} onChange={e => setMerchant(e.target.value)} maxLength={200}/></label>
      </div>
      <CategoryAssistant suggestion={suggestion} loading={suggestionLoading} error={suggestionError} downloadLabels={downloadLabels} trainModel={trainModel} training={training}/>
      <ErrorNotice message={error}/>
      <div className="modal-actions"><button className="finance-secondary" type="button" disabled={busy} onClick={close}>Cancel</button><button className="finance-primary" disabled={busy || !available.length}>{busy ? 'Saving…' : transaction ? 'Save changes' : 'Add transaction'}</button></div>
    </form>
  </Modal>;
}

function TransactionDetails({ transaction, close }) {
  const { openEditor } = useFinance();
  const resource = useResource(`/transactions/${transaction.id}`);
  const data = resource.data;
  return <Modal title="Transaction details" close={close}><ErrorNotice message={resource.error} retry={resource.retry}/>{resource.loading ? <p className="subtle">Loading transaction…</p> : data && <><div className={`details-amount ${data.transaction_type}`}><span>{data.transaction_type === 'income' ? 'Money in' : 'Money out'}</span><h3>{data.transaction_type === 'income' ? '+' : '−'}{currency(data.amount)}</h3></div><dl className="details-list">{[['Description', data.description], ['Merchant', data.merchant || 'Not provided'], ['Category', data.category.name], ['Date', displayDate(data.transaction_date)], ['Type', data.transaction_type], ['Source', data.source.toUpperCase()], ['Created', new Date(data.created_at).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' })]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><div className="modal-actions"><button className="finance-primary" onClick={() => { close(); openEditor(data); }}><Pencil size={15}/> Edit transaction</button></div></>}</Modal>;
}

function DeleteTransaction({ transaction, close }) {
  const { request, changed } = useFinance(); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function remove() { setBusy(true); setError(''); try { await request(`/transactions/${transaction.id}`, { method: 'DELETE' }); changed('Transaction deleted.'); close(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  return <Modal title="Delete transaction?" close={() => !busy && close()}><p className="delete-copy">Delete <strong>{transaction.description}</strong> for <strong>{currency(transaction.amount)}</strong>? This will remove it from your financial record and dashboard.</p><ErrorNotice message={error}/><div className="modal-actions"><button className="finance-secondary" disabled={busy} onClick={close}>Keep transaction</button><button className="finance-danger" disabled={busy} onClick={remove}>{busy ? 'Deleting…' : 'Delete transaction'}</button></div></Modal>;
}

function TransactionTable({ transactions, compact = false }) {
  const { openEditor } = useFinance(); const [details, setDetails] = useState(null); const [deleting, setDeleting] = useState(null);
  return <><div className="table-scroll"><table className="finance-table"><thead><tr><th>Transaction</th><th>Date</th><th>Category</th><th>Type</th><th className="amount-cell">Amount</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{transactions.map(t => <tr key={t.id}><td><button className="transaction-name" onClick={() => setDetails(t)}><span className={`transaction-symbol ${t.transaction_type}`}>{t.transaction_type === 'income' ? <ArrowDownLeft size={18}/> : <ArrowUpRight size={18}/>}</span><span><strong>{t.merchant || t.description}</strong><small>{t.merchant ? t.description : t.source === 'manual' ? 'Manual entry' : `Imported from ${t.source.toUpperCase()}`}</small></span></button></td><td className="date-cell">{displayDate(t.transaction_date)}</td><td><span className="category-badge">{t.category.name}</span></td><td><span className={`type-badge ${t.transaction_type}`}>{t.transaction_type}</span></td><td className={`amount-cell amount-${t.transaction_type}`}>{t.transaction_type === 'income' ? '+' : '−'}{currency(t.amount)}</td><td><div className="row-actions"><button className="icon-button" aria-label={`View ${t.description}`} onClick={() => setDetails(t)}><Eye size={16}/></button>{!compact && <><button className="icon-button" aria-label={`Edit ${t.description}`} onClick={() => openEditor(t)}><Pencil size={15}/></button><button className="icon-button danger-icon" aria-label={`Delete ${t.description}`} onClick={() => setDeleting(t)}><Trash2 size={15}/></button></>}</div></td></tr>)}</tbody></table></div>{details && <TransactionDetails transaction={details} close={() => setDetails(null)}/>} {deleting && <DeleteTransaction transaction={deleting} close={() => setDeleting(null)}/>}</>;
}

function Transactions() {
  const { categories, revision, openEditor } = useFinance();
  const [filters, setFilters] = useState({ search: '', category_id: '', date_from: '', date_to: '', transaction_type: '', sort_by: 'transaction_date', sort_order: 'desc', page_size: '10' });
  const [search, setSearch] = useState(''); const [page, setPage] = useState(1);
  useEffect(() => { const timer = setTimeout(() => setSearch(filters.search), 300); return () => clearTimeout(timer); }, [filters.search]);
  const query = new URLSearchParams(Object.entries({ ...filters, search, page }).filter(([, value]) => value !== ''));
  const resource = useResource(`/transactions?${query}`, revision);
  const data = resource.data;
  function filter(key, value) { setFilters(v => ({ ...v, [key]: value })); setPage(1); }
  useEffect(() => { if (!resource.loading && data?.pages && page > data.pages) setPage(data.pages); }, [data, resource.loading, page]);
  const active = filters.search || filters.category_id || filters.date_from || filters.date_to || filters.transaction_type;
  return <div><div className="page-heading"><div><span className="eyebrow">THE EVERYDAY DETAILS</span><h1>Your transactions<span>.</span></h1><p>Every entry tells a part of your financial story.</p></div><div className="heading-actions"><Link className="finance-secondary" to="/import"><FileUp size={16}/> Import statement</Link><button className="finance-primary" onClick={() => openEditor()}><Plus size={16}/> Add transaction</button></div></div><section className="transaction-panel"><div className="transaction-toolbar"><label className="search-field"><Search size={17}/><input aria-label="Search transactions" placeholder="Search description or merchant…" value={filters.search} maxLength={200} onChange={e => filter('search', e.target.value)}/></label><label className="sr-only" htmlFor="sort-transactions">Sort transactions</label><select id="sort-transactions" value={`${filters.sort_by}:${filters.sort_order}`} onChange={e => { const [sort_by, sort_order] = e.target.value.split(':'); setFilters(v => ({ ...v, sort_by, sort_order })); setPage(1); }}><option value="transaction_date:desc">Newest first</option><option value="transaction_date:asc">Oldest first</option><option value="amount:desc">Amount: high to low</option><option value="amount:asc">Amount: low to high</option><option value="merchant:asc">Merchant: A–Z</option><option value="category:asc">Category: A–Z</option><option value="description:asc">Description: A–Z</option></select></div><div className="filter-row"><label>Category<select aria-label="Category" value={filters.category_id} onChange={e => filter('category_id', e.target.value)}><option value="">All categories</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label><label>Type<select aria-label="Type" value={filters.transaction_type} onChange={e => filter('transaction_type', e.target.value)}><option value="">All transactions</option><option value="income">Income</option><option value="expense">Expenses</option></select></label><label>From<input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={e => filter('date_from', e.target.value)}/></label><label>To<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => filter('date_to', e.target.value)}/></label>{active && <button className="clear-filters" onClick={() => { setFilters(v => ({ ...v, search: '', category_id: '', transaction_type: '', date_from: '', date_to: '' })); setSearch(''); setPage(1); }}><X size={13}/> Clear filters</button>}</div><ErrorNotice message={resource.error} retry={resource.retry}/>{resource.loading ? <div className="table-loading" role="status">Loading transactions…</div> : data?.items.length ? <TransactionTable transactions={data.items}/> : !resource.error && <Empty title={active ? 'No matching transactions.' : 'Your story starts here.'} text={active ? 'Try adjusting your search or filters.' : 'Add your first income or expense, or bring in a bank statement.'} action={!active}/>}<div className="pagination"><span>{data?.total || 0} transaction{data?.total === 1 ? '' : 's'}{data?.items.length ? ` · Showing ${(page - 1) * Number(filters.page_size) + 1}–${Math.min(page * Number(filters.page_size), data.total)}` : ''}</span><div><label>Rows<select aria-label="Rows per page" value={filters.page_size} onChange={e => filter('page_size', e.target.value)}>{[10, 25, 50, 100].map(value => <option key={value}>{value}</option>)}</select></label><button className="icon-button" aria-label="Previous page" disabled={page <= 1 || resource.loading} onClick={() => setPage(v => v - 1)}><ChevronLeft size={17}/></button><span>Page {page} of {Math.max(data?.pages || 0, 1)}</span><button className="icon-button" aria-label="Next page" disabled={!data || page >= data.pages || resource.loading} onClick={() => setPage(v => v + 1)}><ChevronRight size={17}/></button></div></div></section></div>;
}

function StatementImport() {
  const { categories, request, changed } = useFinance();
  const [file, setFile] = useState(null); const [preview, setPreview] = useState(null); const [mapping, setMapping] = useState({});
  const [dayFirst, setDayFirst] = useState(true); const [defaultType, setDefaultType] = useState('expense'); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [result, setResult] = useState(null); const [page, setPage] = useState(1);
  const inputRef = useRef(null);
  function choose(selected) {
    setError(''); setPreview(null); setResult(null); setMapping({}); setPage(1);
    if (!selected) return;
    if (!/\.(csv|xlsx)$/i.test(selected.name)) { setFile(null); setError('Choose a CSV or XLSX statement.'); return; }
    if (selected.size > 5 * 1024 * 1024) { setFile(null); setError('Statements must be 5 MB or smaller.'); return; }
    setFile(selected);
  }
  async function parse() {
    if (!file) return;
    setBusy(true); setError(''); setPreview(null); setResult(null);
    const body = new FormData(); body.append('file', file); body.append('mapping', JSON.stringify(mapping)); body.append('day_first', String(dayFirst)); body.append('default_type', defaultType);
    try {
      const data = await request('/imports/preview', { method: 'POST', body });
      setPreview({ ...data, rows: data.rows.map(row => ({ ...row, selected: !row.errors.length && !row.duplicate })) }); setMapping(data.mapping); setPage(1);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  function rowIssues(row) {
    const t = row.transaction; const issues = [];
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t.transaction_date || '') || Number.isNaN(new Date(`${t.transaction_date}T12:00:00`).getTime())) issues.push('Choose a valid date');
    if (!t.description?.trim() || t.description.length > 500) issues.push('Description is required (max 500 characters)');
    if (!/^\d+(?:\.\d{1,2})?$/.test(t.amount || '') || Number(t.amount) <= 0 || Number(t.amount) > 999999999999.99) issues.push('Enter a positive amount with at most two decimals');
    if ((t.merchant || '').length > 200) issues.push('Merchant exceeds 200 characters');
    const category = categories.find(c => c.id === Number(t.category_id));
    if (!category || category.type !== t.transaction_type) issues.push('Choose a category matching the type');
    if (!row.corrected) issues.push(...row.errors);
    return [...new Set(issues)];
  }
  function updateRow(index, field, value) {
    setPreview(previous => ({ ...previous, rows: previous.rows.map((row, i) => i !== index ? row : {
      ...row, corrected: true, transaction: { ...row.transaction, [field]: value, ...(field === 'category_id' ? { category_confirmed: true } : {}), ...(field === 'transaction_type' ? { category_id: categories.find(c => c.type === value)?.id || null } : {}) },
    }) }));
  }
  const selected = preview?.rows.filter(row => row.selected) || []; const issues = selected.filter(row => rowIssues(row).length); const ready = selected.length - issues.length;
  const mappingChanged = preview && JSON.stringify(mapping) !== JSON.stringify(preview.mapping);
  async function confirm() {
    if (!ready || issues.length || mappingChanged) return;
    setBusy(true); setError('');
    try {
      const body = { source: preview.source, transactions: selected.map(row => ({ ...row.transaction, category_id: Number(row.transaction.category_id), merchant: row.transaction.merchant?.trim() || null, description: row.transaction.description.trim() })) };
      const value = await request('/imports/confirm', { method: 'POST', body: JSON.stringify(body) });
      setResult(value); setPreview(null); setFile(null); setMapping({}); if (inputRef.current) inputRef.current.value = '';
      changed(`${value.imported} transaction${value.imported === 1 ? '' : 's'} imported. ${value.skipped_duplicates} duplicate${value.skipped_duplicates === 1 ? '' : 's'} skipped.`);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div><div className="page-heading"><div><span className="eyebrow">BRING IT ALL TOGETHER</span><h1>A statement. A clearer picture<span>.</span></h1><p>Import your bank activity, with a chance to review every detail.</p></div></div><div className="import-steps"><span className={preview || result ? 'complete' : 'active'}><i>1</i> Upload statement</span><div/><span className={preview ? 'active' : result ? 'complete' : ''}><i>2</i> Review & correct</span><div/><span className={result ? 'active' : ''}><i>3</i> Confirm import</span></div><ErrorNotice message={error}/>{result && <section className="import-success"><span className="success-leaf"><ShieldCheck size={28}/></span><h2>Your finances, brought together.</h2><p><strong>{result.imported}</strong> transactions imported. <strong>{result.skipped_duplicates}</strong> duplicates skipped.</p><div><Link className="finance-primary" to="/transactions">View transactions <ArrowRight size={16}/></Link><Link className="finance-secondary" to="/">See your dashboard</Link></div></section>}<section className="import-upload"><div className="upload-drop" onDragOver={e => { e.preventDefault(); }} onDrop={e => { e.preventDefault(); if (!busy) choose(e.dataTransfer.files[0]); }}><span className="upload-icon"><FileUp size={29}/></span><h2>{file ? file.name : 'Your financial story is already here.'}</h2><p>{file ? `${(file.size / 1024).toFixed(1)} KB · Ready to preview` : 'Drop your bank statement here, or choose a file to get started.'}</p><input ref={inputRef} className="sr-only" type="file" accept=".csv,.xlsx" aria-label="Bank statement file" disabled={busy} onChange={e => choose(e.target.files[0])}/><button className="finance-secondary" disabled={busy} onClick={() => inputRef.current.click()}>{file ? 'Choose another file' : 'Choose a statement'}</button><span className="upload-limits">CSV or XLSX · Up to 5 MB · 2,000 rows per import</span></div><div className="upload-guidance"><span className="eyebrow">A LITTLE GUIDANCE</span><h3>Simple. Thoughtful. Yours.</h3><ul><li><span>01</span> Export a CSV or Excel statement with column headers.</li><li><span>02</span> Map your date, description, and amount or debit/credit columns.</li><li><span>03</span> Review suggested categories and fix anything that needs attention.</li></ul><a href="/sample-statement.csv" download className="inline-link"><Download size={15}/> Download a sample CSV</a><div className="import-privacy"><ShieldCheck size={18}/><p>Your original file is not kept. Only the transactions you confirm are saved.</p></div></div></section>{file && <section className="mapping-panel"><div className="panel-heading"><div><h2>{preview ? 'Check your column mapping' : 'Choose how to read your statement'}</h2><p>Dates default to day/month/year. Amounts use a decimal point and optional comma thousands separators.</p></div><button className="finance-primary" disabled={busy} onClick={parse}>{busy ? 'Reading statement…' : preview ? 'Apply mapping & reparse' : 'Preview statement'}<ArrowRight size={16}/></button></div><div className="import-options"><label>Date format<select value={dayFirst ? 'day' : 'month'} onChange={e => { setDayFirst(e.target.value === 'day'); setPreview(null); }}><option value="day">Day first (05/10/2026)</option><option value="month">Month first (10/05/2026)</option></select></label><label>Unsigned amount default<select value={defaultType} onChange={e => { setDefaultType(e.target.value); setPreview(null); }}><option value="expense">Expense</option><option value="income">Income</option></select></label></div>{preview?.columns && <div className="mapping-grid">{[['transaction_date', 'Date'], ['description', 'Description'], ['amount', 'Amount'], ['debit', 'Debit'], ['credit', 'Credit'], ['merchant', 'Merchant'], ['transaction_type', 'Type'], ['category', 'Category']].map(([key, label]) => <label key={key}>{label}<select aria-label={`Map ${label} column`} value={mapping[key] || ''} onChange={e => setMapping(previous => ({ ...previous, [key]: e.target.value }))}><option value="">Not mapped</option>{preview.columns.map(column => <option key={column}>{column}</option>)}</select></label>)}</div>}</section>}{preview && <section className="import-preview"><div className="panel-heading"><div><h2>Review your transactions</h2><p>{preview.total_rows} rows · {preview.valid_rows} parsed · {preview.invalid_rows} need attention · {preview.duplicates} possible duplicates</p></div><span className="panel-tag">NOT SAVED YET</span></div>{preview.warnings.map((warning, i) => <p className="import-warning" key={i}><CircleHelp size={15}/>{warning}</p>)}{preview.rows.length > 0 && <><div className="preview-controls"><label><input type="checkbox" aria-label="Select all valid non-duplicate rows" checked={preview.rows.filter(row => !rowIssues(row).length && !row.duplicate).length > 0 && preview.rows.filter(row => !rowIssues(row).length && !row.duplicate).every(row => row.selected)} onChange={e => setPreview(previous => ({ ...previous, rows: previous.rows.map(row => ({ ...row, selected: e.target.checked && !rowIssues(row).length && !row.duplicate })) }))}/> Select valid rows</label><span>{selected.length} selected · {ready} ready to import</span></div><div className="table-scroll"><table className="preview-table"><thead><tr><th>Include</th><th>Statement row</th><th>Date</th><th>Description</th><th>Merchant</th><th>Amount (LKR)</th><th>Type</th><th>Category</th><th>Review</th></tr></thead><tbody>{preview.rows.slice((page - 1) * 25, page * 25).map((row, offset) => { const index = (page - 1) * 25 + offset; const t = row.transaction; const errors = rowIssues(row); return <tr key={row.row_number} className={errors.length ? 'invalid-row' : row.duplicate ? 'duplicate-row' : ''}><td><input type="checkbox" aria-label={`Include row ${row.row_number}`} checked={row.selected} onChange={e => setPreview(previous => ({ ...previous, rows: previous.rows.map((r, i) => i === index ? { ...r, selected: e.target.checked } : r) }))}/></td><td>{row.row_number}</td><td><input aria-label={`Row ${row.row_number} date`} type="date" value={t.transaction_date} onChange={e => updateRow(index, 'transaction_date', e.target.value)}/></td><td><input aria-label={`Row ${row.row_number} description`} value={t.description} maxLength={500} onChange={e => updateRow(index, 'description', e.target.value)}/></td><td><input aria-label={`Row ${row.row_number} merchant`} value={t.merchant || ''} maxLength={200} onChange={e => updateRow(index, 'merchant', e.target.value)}/></td><td><input aria-label={`Row ${row.row_number} amount`} type="number" step="0.01" min="0.01" value={t.amount} onChange={e => updateRow(index, 'amount', e.target.value)}/></td><td><select aria-label={`Row ${row.row_number} type`} value={t.transaction_type} onChange={e => updateRow(index, 'transaction_type', e.target.value)}><option value="expense">Expense</option><option value="income">Income</option></select></td><td><select aria-label={`Row ${row.row_number} category`} value={t.category_id || ''} onChange={e => updateRow(index, 'category_id', Number(e.target.value))}><option value="">Choose category</option>{categories.filter(c => c.type === t.transaction_type).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></td><td><span className={`preview-row-status ${errors.length ? 'invalid' : row.duplicate ? 'duplicate' : ''}`}>{errors.length ? errors.join('; ') : row.duplicate ? 'Possible duplicate — skipped by default' : row.corrected ? 'Corrected' : row.suggestion ? `${row.suggestion.method.replaceAll('_', ' ')} · ${Math.round(row.suggestion.confidence * 100)}% score` : 'Ready'}</span></td></tr>; })}</tbody></table></div><div className="pagination"><span>Statement rows {(page - 1) * 25 + 1}–{Math.min(page * 25, preview.rows.length)} of {preview.rows.length}</span><div><button className="icon-button" aria-label="Previous preview page" disabled={page === 1} onClick={() => setPage(v => v - 1)}><ChevronLeft size={17}/></button><span>Page {page} of {Math.ceil(preview.rows.length / 25)}</span><button className="icon-button" aria-label="Next preview page" disabled={page >= Math.ceil(preview.rows.length / 25)} onClick={() => setPage(v => v + 1)}><ChevronRight size={17}/></button></div></div><div className="confirm-import"><div><strong>{ready} transactions ready</strong><p>{mappingChanged ? 'Apply your new mapping and reparse before importing.' : issues.length ? `${issues.length} selected rows need corrections. Correct them or uncheck them before importing.` : 'Duplicates are checked again when you confirm. Changes here are saved only after confirmation.'}</p></div><button className="finance-primary" disabled={busy || !ready || issues.length > 0 || mappingChanged} onClick={confirm}>{busy ? 'Importing…' : `Confirm import (${selected.length})`}<ArrowRight size={16}/></button></div></>}</section>}</div>;
}
