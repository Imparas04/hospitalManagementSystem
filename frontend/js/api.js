/* API client: JWT is attached to all protected calls; binary exports are downloaded as blobs. */
const Api = (() => {
  const BASE = localStorage.getItem('hospital_api_url') || 'http://127.0.0.1:5000/api';
  const getToken = () => localStorage.getItem('hospital_access_token');
  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (getToken()) headers.set('Authorization', `Bearer ${getToken()}`);
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    let response;
    try { response = await fetch(`${BASE}${path}`, {...options, headers}); }
    catch (_) { throw new Error(`Cannot reach backend at ${BASE}. Start Flask and check the API URL.`); }
    const type = response.headers.get('content-type') || '';
    const payload = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok || (payload && payload.success === false)) {
      if (response.status === 401 && getToken()) { localStorage.removeItem('hospital_access_token'); localStorage.removeItem('hospital_user'); }
      throw new Error(payload?.message || `Request failed (${response.status})`);
    }
    return payload?.data !== undefined ? payload.data : payload;
  }
  async function download(path, filename) {
    const headers = {}; if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
    let response;
    try { response = await fetch(`${BASE}${path}`, {headers}); } catch (_) { throw new Error('Could not reach backend.'); }
    if (!response.ok) { let msg = `Download failed (${response.status})`; try { msg = (await response.json()).message || msg; } catch(_){} throw new Error(msg); }
    const blob = await response.blob(), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return {request, download, base: BASE};
})();
