export async function api(path, { token, responseType = 'json', ...options } = {}) {
  let response;
  try {
    response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}${path}`, {
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    });
  } catch { throw new Error('Cannot reach LifeLens. Please check your connection and try again.'); }
  const body = response.ok && responseType === 'blob' ? await response.blob() : response.ok && responseType === 'text' ? await response.text() : await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = Array.isArray(body.detail) ? body.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join('; ') : body.detail;
    const error = new Error(message || 'Something went wrong. Please try again.');
    error.status = response.status;
    throw error;
  }
  return body;
}
