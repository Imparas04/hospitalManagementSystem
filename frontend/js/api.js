/* api.js — talks to the Flask backend. Every call adds the login token (JWT) automatically.

   Api.get('/patients')                     -> returns the "data" part of the JSON answer
   Api.post('/patients', {full_name: ...})  -> same, with a JSON body
   Api.download('/bills/1/pdf', 'bill.pdf') -> saves a file (PDF / Excel / CSV)

   If something goes wrong an Error is thrown whose message is shown to the user. */
const Api = (() => {
  const BASE = window.HOSPITAL_CONFIG.apiUrl;
  const TOKEN_KEY = 'hospital_access_token';
  const USER_KEY = 'hospital_user';

  const getToken = () => localStorage.getItem(TOKEN_KEY);

  function saveSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
  function savedUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch (_) { return null; }
  }

  // Turn the backend's {"errors": {...}} into one readable sentence.
  function describeErrors(errors) {
    const parts = [];
    const walk = (value, label) => {
      if (value === null || value === undefined || value === '') return;
      if (Array.isArray(value)) value.forEach((v, i) => walk(v, `${label} #${i + 1}`));
      else if (typeof value === 'object') Object.entries(value).forEach(([k, v]) => walk(v, label ? `${label} ${k}` : k));
      else parts.push(label ? `${label.replace(/_/g, ' ')}: ${value}` : String(value));
    };
    walk(errors, '');
    return parts.join('; ');
  }

  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (getToken()) headers.set('Authorization', `Bearer ${getToken()}`);
    let body = options.body;
    if (body !== undefined && !(body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
      body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(`${BASE}${path}`, { ...options, headers, body });
    } catch (_) {
      throw new Error(`Cannot reach the backend at ${BASE}. Is Flask running? (python run.py)`);
    }

    const isJson = (response.headers.get('content-type') || '').includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok || (payload && payload.success === false)) {
      // Token missing/expired/logged-out -> send the person back to the login screen.
      if (response.status === 401 && getToken()) {
        clearSession();
        window.dispatchEvent(new Event('session-expired'));
      }
      let message = (payload && payload.message) || `Request failed (${response.status})`;
      const details = payload && payload.errors ? describeErrors(payload.errors) : '';
      if (details && details !== message) message += ` — ${details}`;
      throw new Error(message);
    }
    return payload && payload.data !== undefined ? payload.data : payload;
  }

  async function download(path, filename) {
    const headers = {};
    if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
    let response;
    try { response = await fetch(`${BASE}${path}`, { headers }); }
    catch (_) { throw new Error('Could not reach the backend.'); }
    if (!response.ok) {
      let message = `Download failed (${response.status})`;
      try { message = (await response.json()).message || message; } catch (_) { /* not JSON */ }
      throw new Error(message);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return {
    base: BASE,
    get: path => request(path),
    post: (path, body = {}) => request(path, { method: 'POST', body }),
    put: (path, body = {}) => request(path, { method: 'PUT', body }),
    del: path => request(path, { method: 'DELETE' }),
    download, saveSession, clearSession, savedUser, getToken,
  };
})();
