import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowRight, Check, Download, Leaf, RefreshCw, Sparkles, TrendingUp } from 'lucide-react';
import Chart from 'chart.js/auto';
import { Link } from 'react-router-dom';

const money = value => `Rs. ${Number(value || 0).toLocaleString('en-LK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const monthName = value => new Date(`${value.slice(0, 7)}-01T12:00:00`).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });

function ForecastChart({ forecast }) {
  const ref = useRef(null);
  useEffect(() => {
    const history = forecast.history.slice(-6);
    const target = new Date(`${forecast.target_month}T12:00:00`);
    const bridge = new Date(target); bridge.setMonth(bridge.getMonth() - 1);
    const bridgeLabel = bridge.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
    const labels = [...history.map(row => monthName(row.month)), bridgeLabel, monthName(forecast.target_month)];
    const chart = new Chart(ref.current, {
      type: 'line', data: { labels, datasets: [
        { label: 'Recorded completed months', data: [...history.map(row => Number(row.expenses)), null, null], borderColor: '#38634b', backgroundColor: '#edf3e5', tension: .25, pointRadius: 3 },
        { label: 'Next-month estimate', data: [...history.map((row, i) => i === history.length - 1 ? Number(row.expenses) : null), null, Number(forecast.prediction)], borderColor: '#b79a68', borderDash: [5, 5], spanGaps: true, pointRadius: 4 },
      ] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${money(context.parsed.y)}` } } }, scales: { x: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#8c9d7e' } }, y: { beginAtZero: true, grid: { color: '#eef3e7' }, border: { display: false }, ticks: { maxTicksLimit: 4, font: { size: 9 }, color: '#8c9d7e', callback: value => `${(value / 1000).toFixed(0)}k` } } } },
    });
    return () => chart.destroy();
  }, [forecast]);
  return <div className="forecast-chart"><canvas ref={ref} role="img" aria-label="Completed-month expenses and next-month estimate"/></div>;
}

export function IntelligencePanels({ request, revision, openEditor }) {
  const [forecast, setForecast] = useState(null); const [alerts, setAlerts] = useState(null); const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  const [includeNormal, setIncludeNormal] = useState(false); const [scanning, setScanning] = useState(false); const [busyId, setBusyId] = useState(null);
  useEffect(() => {
    let active = true; setError(''); setScanning(true); setForecast(null);
    request('/intelligence/forecast').then(value => { if (active) setForecast(value); }).catch(err => { if (active) setError(err.message); });
    request('/intelligence/unusual/scan', { method: 'POST' }).then(() => request(`/intelligence/unusual?include_normal=${includeNormal}`)).then(value => { if (active) setAlerts(value); }).catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setScanning(false); });
    return () => { active = false; };
  }, [request, revision, retry, includeNormal]);
  async function normal(alert) {
    setBusyId(alert.id); setError('');
    try {
      await request(`/intelligence/unusual/${alert.id}/normal`, { method: 'PUT', body: JSON.stringify({ marked_normal: !alert.marked_normal }) });
      setAlerts(await request(`/intelligence/unusual?include_normal=${includeNormal}`));
    } catch (err) { setError(err.message); } finally { setBusyId(null); }
  }
  return <section className="intelligence-section"><div className="intelligence-section-title"><span className="eyebrow">A LITTLE MORE PERSPECTIVE</span><h2>Looking ahead. Staying aware.</h2><p>Estimates and patterns from your own financial history.</p></div>{error && <div className="finance-error" role="alert">{error}<button onClick={() => setRetry(v => v + 1)}>Try again</button></div>}<div className="intelligence-grid"><article className="forecast-panel"><div className="panel-heading"><div><h2><TrendingUp size={17}/> Next month’s expenses</h2><p>A planning estimate, grounded in your records</p></div><span className="panel-tag">{forecast ? monthName(forecast.target_month) : 'LOOKING AHEAD'}</span></div>{forecast ? forecast.prediction !== null ? <><div className="forecast-amount" data-testid="forecast-amount">≈ {money(forecast.prediction)}</div><div className="forecast-method"><span>{forecast.method === 'ridge_regression' ? 'Ridge regression' : 'Recent-month average'}</span><span>{forecast.confidence} confidence</span></div><p className="planning-range">Planning range: {money(forecast.range.low)} – {money(forecast.range.high)}</p><ForecastChart forecast={forecast}/><details className="intelligence-explanation"><summary>How this estimate works</summary><p>{forecast.training_months} completed months, {forecast.active_months} with recorded expenses. Trained through {monthName(forecast.trained_through)}.</p>{forecast.evaluation && <p>Chronological backtest over {forecast.evaluation.test_months} months: regression MAE {money(forecast.evaluation.regression.mae)}, RMSE {money(forecast.evaluation.regression.rmse)}; average MAE {money(forecast.evaluation.baseline.mae)}, RMSE {money(forecast.evaluation.baseline.rmse)}.</p>}<ul>{forecast.limitations.map(item => <li key={item}>{item}</li>)}</ul></details></> : <div className="intelligence-empty"><Leaf size={26}/><h3>History makes the picture clearer.</h3><p>Add expenses from completed months to get an estimate. Your current month stays out of the training data.</p><Link to="/transactions" className="inline-link">Build your financial history <ArrowRight size={14}/></Link></div> : <p className="subtle">Preparing your estimate…</p>}</article><article className="unusual-panel"><div className="panel-heading"><div><h2><AlertTriangle size={17}/> Unusual transactions</h2><p>Amounts that stand out from your usual spending</p></div><button className="icon-button" aria-label="Refresh unusual transactions" disabled={scanning} onClick={() => setRetry(v => v + 1)}><RefreshCw size={16}/></button></div><label className="show-normal"><input type="checkbox" checked={includeNormal} onChange={e => setIncludeNormal(e.target.checked)}/> Show transactions marked normal</label>{scanning ? <p role="status" className="subtle">Reviewing earlier spending patterns…</p> : alerts?.items.length ? <div className="unusual-list">{alerts.items.map(alert => <div className={`unusual-item ${alert.marked_normal ? 'marked-normal' : ''}`} key={alert.id}><div className="unusual-item-heading"><strong>{alert.transaction.merchant || alert.transaction.description}</strong><span>{money(alert.transaction.amount)}</span></div><p>{alert.explanation}</p><span className="unusual-score">Unusualness score {Math.round(alert.score * 100)}/100 · {alert.method === 'isolation_forest' ? 'Experimental Isolation Forest' : 'Category/merchant statistics'}</span><div className="unusual-actions"><button className="inline-link" onClick={() => openEditor(alert.transaction)}>Review transaction</button><button className="finance-secondary" disabled={busyId === alert.id} onClick={() => normal(alert)}><Check size={13}/>{alert.marked_normal ? 'Restore warning' : 'Mark as normal'}</button></div></div>)}</div> : <div className="intelligence-empty"><Check size={26}/><h3>Nothing stands out right now.</h3><p>New categories and merchants need at least five earlier expenses before a comparison is made. This isn’t a guarantee about every transaction.</p></div>}<p className="unusual-limit">These are unusual transactions, not fraud determinations. Scores are heuristics, not probabilities.</p></article></div></section>;
}

export function CategoryAssistant({ suggestion, loading, error, downloadLabels, trainModel, training }) {
  return <div className="category-assistant"><div><Sparkles size={16}/><strong>{loading ? 'Finding a category…' : suggestion ? `${suggestion.category_name} · ${Math.round(suggestion.confidence * 100)}% score` : 'Category suggestions'}</strong>{suggestion && <span>{suggestion.method.replaceAll('_', ' ')}</span>}</div><p>{error || suggestion?.reason || 'Enter a description or merchant for a suggestion. You can always choose a different category.'}</p>{suggestion && <small>Scores are not calibrated probabilities. The starter model uses synthetic examples.</small>}{downloadLabels && <button type="button" onClick={downloadLabels} className="inline-link"><Download size={12}/> Download my confirmed labels</button>}{trainModel && <button type="button" disabled={training} onClick={trainModel} className="inline-link"><Sparkles size={12}/>{training ? 'Training…' : 'Train a private model from my labels'}</button>}</div>;
}
import './intelligence.css';
