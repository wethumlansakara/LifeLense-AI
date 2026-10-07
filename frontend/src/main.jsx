document.documentElement.dataset.theme = localStorage.getItem('lifelens-theme') || 'light';
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Eye, EyeOff, Leaf } from 'lucide-react';
import { AuthProvider, useAuth } from './auth';
import { api } from './api';
import './styles.css';
import FinanceApp from './finance';

function Brand() { return <Link to="/" className="brand"><span className="brand-icon"><Leaf size={23}/></span>LifeLens<span className="ai">AI</span></Link>; }
class ErrorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <main className="loading"><h1>Something went wrong</h1><button onClick={() => window.location.reload()}>Reload LifeLens</button></main> : this.props.children; }
}
function AuthPage({ register = false }) {
  const auth = useAuth(); const navigate = useNavigate();
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [show, setShow] = useState(false);
  if (auth.user) return <Navigate to="/" replace/>;
  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (register) await api('/auth/register', { method: 'POST', body: JSON.stringify(data) });
      await auth.login(data.email, data.password); navigate('/', { replace: true });
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="auth-layout"><aside className="auth-story"><Brand/><div><span className="eyebrow light">A CLEARER VIEW OF YOUR MONEY</span><h1>Good financial habits<br/>start with clarity.</h1><p>Your personal space to build a more intentional financial future. One step at a time.</p><div className="story-art"><div className="orbit one"/><div className="orbit two"/><Leaf size={80}/><span className="art-note"><ShieldCheck size={18}/> A foundation you can trust</span></div></div><small>YOUR MONEY. YOUR PERSPECTIVE.</small></aside><main className="auth-form"><div className="mobile-brand"><Brand/></div><div className="form-wrap"><span className="eyebrow">WELCOME TO LIFELENS</span><h1>{register ? 'Make room for better.' : 'Welcome back.'}</h1><p>{register ? 'Create your account and take the first step.' : 'Sign in to your personal financial workspace.'}</p><form onSubmit={submit} key={register ? 'register' : 'login'}>{register && <label>Full name<input name="name" autoComplete="name" placeholder="Your name" required maxLength={100}/></label>}<label>Email address<input name="email" type="email" autoComplete="email" placeholder="you@example.com" required maxLength={254}/></label><label>Password<div className="password-field"><input name="password" type={show ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} placeholder={register ? 'At least 12 characters' : 'Enter your password'} required minLength={register ? 12 : 1} maxLength={128}/><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18}/> : <Eye size={18}/>}</button></div></label>{register && <small className="hint">Use a unique passphrase with at least 12 characters.</small>}{error && <p role="alert" className="error">{error}</p>}<button className="primary" disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}<ArrowRight size={18}/></button></form><p className="switch">{register ? 'Already have an account?' : 'New to LifeLens?'} <Link to={register ? '/login' : '/register'}>{register ? 'Sign in' : 'Create an account'}</Link></p><div className="secure-note"><ShieldCheck size={16}/> Your password is protected with Argon2 hashing.</div></div><footer>LifeLens AI <span>Built for a more mindful financial life.</span></footer></main></div>;
}
function Protected({ children }) {
  const auth = useAuth();
  if (auth.loading) return <main className="loading">Opening your workspace…</main>;
  if (auth.error) return <main className="loading"><p role="alert">{auth.error}</p><button className="primary" onClick={auth.retry}>Try again</button><button onClick={auth.logout}>Sign out</button></main>;
  return auth.user ? children : <Navigate to="/login" replace/>;
}

function App() { return <ErrorBoundary><BrowserRouter><AuthProvider><Routes><Route path="/login" element={<AuthPage/>}/><Route path="/register" element={<AuthPage register/>}/><Route path="/*" element={<Protected><FinanceApp/></Protected>}/></Routes></AuthProvider></BrowserRouter></ErrorBoundary>; }
createRoot(document.getElementById('root')).render(<App/>);
