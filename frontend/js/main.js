/* main.js — starts the app: login, menu, switching pages, change password, logout. */

const PAGE_ORDER = ['dashboard', 'patients', 'doctors', 'departments', 'appointments', 'emergency', 'beds', 'admissions',
  'laboratory', 'pharmacy', 'prescriptions', 'billing', 'reports', 'notifications', 'users', 'audit'];
let currentPage = 'dashboard';

function renderMenu() {
  let lastGroup = '';
  $('#navigation').innerHTML = PAGE_ORDER.filter(id => Pages[id] && Pages[id].roles.includes(Session.role)).map(id => {
    const page = Pages[id];
    const heading = page.group !== lastGroup ? `<div class="nav-label nav-group">${esc(page.group.toUpperCase())}</div>` : '';
    lastGroup = page.group;
    return `${heading}<button class="nav-item ${id === currentPage ? 'active' : ''}" data-page="${id}"><span class="nav-icon">${page.icon}</span><span class="nav-text">${esc(page.title)}</span></button>`;
  }).join('');
  $$('[data-page]', $('#navigation')).forEach(b => b.onclick = () => openPage(b.dataset.page));
}

async function openPage(id) {
  const page = Pages[id];
  if (!page || !page.roles.includes(Session.role)) id = 'dashboard';
  currentPage = id;
  const current = Pages[id];
  renderMenu();
  $('#page-title').textContent = current.title;
  $('#section-eyebrow').textContent = current.group.toUpperCase();
  $('#today-label').textContent = new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  $('#page-content').innerHTML = '<div class="panel empty-state">Loading…</div>';
  try { await current.render(); }
  catch (e) {
    $('#page-content').innerHTML = `<div class="panel empty-state"><strong>Could not load ${esc(current.title)}</strong><p>${esc(e.message)}</p><button class="btn secondary" id="retry-btn">Try again</button></div>`;
    $('#retry-btn').onclick = () => openPage(id);
  }
}
window.openPage = openPage;
window.reloadPage = () => openPage(currentPage);

async function refreshNotificationCount() {
  try {
    const data = await Api.get('/notifications/unread-count');
    const n = data.unread_count || 0;
    $('#notification-count').textContent = n;
    $('#notification-count').classList.toggle('hidden', !n);
  } catch (_) { /* the bell is optional */ }
}
window.refreshNotificationCount = refreshNotificationCount;

function showApp(user) {
  Session.user = user;
  $('#user-name').textContent = user.full_name || user.username;
  $('#user-role').textContent = titleCase(Session.role);
  $('#user-avatar').textContent = (user.full_name || user.username || 'U').slice(0, 1).toUpperCase();
  $('#login-screen').classList.add('hidden');
  $('#app').classList.remove('hidden');
  openPage('dashboard');
  refreshNotificationCount();
}

function showLogin(message = '') {
  Session.user = null;
  $('#app').classList.add('hidden');
  $('#login-screen').classList.remove('hidden');
  $('#login-error').textContent = message;
  $('#login-password').value = '';
  Dialog.close();
}

async function signOut() {
  try { await Api.post('/auth/logout'); } catch (_) { /* even if this fails we still sign out here */ }
  Api.clearSession();
  Object.keys(listState).forEach(k => delete listState[k]);
  showLogin();
}

function openChangePassword() {
  openForm({
    title: 'Change my password', eyebrow: 'Account', submitLabel: 'Change password',
    fields: [
      { name: 'old_password', label: 'Current password', type: 'password', required: true, wide: true },
      { name: 'new_password', label: 'New password', type: 'password', required: true, hint: 'At least 8 characters with a letter and a digit.' },
      { name: 'confirm', label: 'Repeat new password', type: 'password', required: true, skip: true },
    ],
    onSubmit: async (values, form) => {
      if (form.elements.confirm.value !== values.new_password) throw new Error('The two new passwords do not match.');
      await Api.post('/auth/change-password', values);
      return 'Password changed';
    },
  });
}

/* ---------- wiring ---------- */
$('#login-form').addEventListener('submit', async e => {
  e.preventDefault();
  $('#login-error').textContent = '';
  try {
    const result = await Api.post('/auth/login', { username: $('#login-username').value.trim(), password: $('#login-password').value });
    Api.saveSession(result.access_token, result.user);
    showApp(result.user);
  } catch (err) { $('#login-error').textContent = err.message; }
});
$('#logout-btn').onclick = signOut;
$('#password-btn').onclick = openChangePassword;
$('#refresh-btn').onclick = () => openPage(currentPage);
$('#notification-btn').onclick = () => openPage('notifications');
$('#dialog-close').onclick = () => Dialog.close();
window.addEventListener('session-expired', () => showLogin('Your session has ended. Please sign in again.'));

(async function boot() {
  if (!Api.getToken()) return showLogin();
  try { showApp(await Api.get('/auth/me')); }          // check the saved token is still valid
  catch (_) { Api.clearSession(); showLogin(); }
})();
