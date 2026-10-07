import { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('lifelens-token'));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  function logout() { sessionStorage.removeItem('lifelens-token'); setToken(null); setUser(null); setError(''); }
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    if (!token) { setLoading(false); return; }
    api('/auth/me', { token }).then(value => { if (active) setUser(value); }).catch(err => {
      if (!active) return;
      if (err.status === 401) logout(); else setError(err.message);
    }).finally(() => { if (active) setLoading(false); });
    const timer = setInterval(() => {
      try {
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        if (payload.exp * 1000 <= Date.now()) logout();
      } catch { logout(); }
    }, 1000);
    return () => { active = false; clearInterval(timer); };
  }, [token, retry]);
  async function login(email, password) {
    const result = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
    const profile = await api('/auth/me', { token: result.access_token });
    sessionStorage.setItem('lifelens-token', result.access_token);
    setUser(profile); setToken(result.access_token);
  }
  return <AuthContext.Provider value={{ user, token, loading, error, login, logout, retry: () => setRetry(v => v + 1) }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
