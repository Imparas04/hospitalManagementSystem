/* pages-admin.js — dashboard, reports, notifications, users and the audit log. */

/* =====================================================================  DASHBOARD  */
// Which charts exist and which roles the server lets see them (same rules as the backend permission list).
const DASHBOARD_CHARTS = [
  { endpoint: '/analytics/patient-registrations?days=14', title: 'Patient registrations', note: 'Last 14 days', type: 'line', roles: ['admin', 'receptionist'] },
  { endpoint: '/analytics/bed-occupancy', title: 'Bed occupancy', note: 'By ward', type: 'bar', roles: ['admin', 'receptionist', 'nurse'] },
  { endpoint: '/analytics/department-patients', title: 'Patients by department', note: 'Appointments per department', type: 'doughnut', roles: ['admin', 'receptionist', 'doctor'] },
  { endpoint: '/analytics/emergency-cases', title: 'Emergency cases', note: 'By priority', type: 'doughnut', roles: ['admin', 'doctor', 'nurse'] },
  { endpoint: '/analytics/monthly-revenue', title: 'Monthly revenue', note: 'Last 12 months', type: 'bar', roles: ['admin', 'billing_staff'] },
  { endpoint: '/analytics/lab-statistics', title: 'Laboratory orders', note: 'By status', type: 'bar', roles: ['admin', 'doctor', 'lab_technician'] },
  { endpoint: '/analytics/medicine-consumption', title: 'Medicine consumption', note: 'Most used medicines', type: 'bar', roles: ['admin', 'pharmacist'] },
];
const QUICK_ACTIONS = [
  { page: 'patients', icon: '♙', title: 'Patients', note: 'Find or register a patient' },
  { page: 'appointments', icon: '▦', title: 'Appointments', note: 'Book or manage visits' },
  { page: 'emergency', icon: '✚', title: 'Emergency triage', note: 'Record vitals, allocate beds' },
  { page: 'admissions', icon: '⌂', title: 'Admissions', note: 'Admit and discharge' },
  { page: 'laboratory', icon: '⚗', title: 'Laboratory', note: 'Orders and results' },
  { page: 'pharmacy', icon: '℞', title: 'Pharmacy', note: 'Medicines and stock' },
  { page: 'prescriptions', icon: '✎', title: 'Prescriptions', note: 'Write or issue' },
  { page: 'billing', icon: '₹', title: 'Billing', note: 'Bills and payments' },
  { page: 'reports', icon: '▥', title: 'Reports', note: 'CSV, Excel and PDF' },
];
let liveCharts = [];

function formatStat(value, format) {
  if (value === null || value === undefined) return '—';
  if (format === 'currency') return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
  return new Intl.NumberFormat('en-IN').format(value);
}

async function drawChart(spec, canvasId) {
  const box = $(`#${canvasId}`);
  try {
    const data = await Api.get(spec.endpoint);
    if (typeof Chart === 'undefined') throw new Error('Chart.js could not be loaded (check your internet connection).');
    const palette = ['#246bfe', '#14b8a6', '#e9a23b', '#e85d75', '#8b5cf6', '#64748b'];
    const datasets = (data.datasets || []).map((d, i) => ({
      label: d.label, data: d.data, borderWidth: 2, tension: 0.35, fill: spec.type === 'line',
      borderColor: d.borderColor || palette[i % palette.length],
      backgroundColor: spec.type === 'doughnut' ? (d.backgroundColor || palette) : (spec.type === 'line' ? '#246bfe22' : (d.backgroundColor || palette[i % palette.length])),
    }));
    liveCharts.push(new Chart(box, {
      type: spec.type, data: { labels: data.labels || [], datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: spec.type === 'doughnut' || datasets.length > 1, position: 'bottom', labels: { boxWidth: 9, usePointStyle: true, font: { size: 10 } } } },
        scales: spec.type === 'doughnut' ? {} : { x: { grid: { display: false }, ticks: { font: { size: 10 } } }, y: { beginAtZero: true, grid: { color: '#eef1f6' }, ticks: { font: { size: 10 } } } },
      },
    }));
  } catch (e) {
    box.parentElement.innerHTML = `<div class="empty-state"><strong>Chart unavailable</strong><small>${esc(e.message)}</small></div>`;
  }
}

definePage('dashboard', {
  title: 'Dashboard', group: 'Overview', icon: '◫', roles: ROLES,
  render: async () => {
    const data = await Api.get('/dashboard');
    liveCharts.forEach(c => c.destroy()); liveCharts = [];
    const icons = ['♙', '▦', '▤', '✚', '⚗', '℞', '₹', '↗'];
    const charts = DASHBOARD_CHARTS.filter(c => c.roles.includes(Session.role));
    const quick = QUICK_ACTIONS.filter(q => Pages[q.page] && Pages[q.page].roles.includes(Session.role));

    $('#page-content').innerHTML = `
      <section class="welcome-banner"><div class="welcome-copy"><span class="welcome-kicker">CAREPOINT · HOSPITAL OPERATIONS</span>
        <h2>Welcome, ${esc(Session.user.full_name || Session.user.username)}</h2>
        <p>Here is how the hospital looks today — ${esc(dateOnly(data.date))}.</p></div><div class="welcome-art" role="img" aria-label="Healthcare team"></div></section>
      <div class="stats-grid">${(data.cards || []).map((c, i) => `<div class="stat-card"><div class="stat-top"><span class="stat-label">${esc(c.label)}</span><span class="stat-icon">${icons[i % icons.length]}</span></div><div class="stat-value">${esc(formatStat(c.value, c.format))}</div></div>`).join('')}</div>
      ${charts.length ? `<div class="chart-grid">${charts.map((c, i) => `<div class="panel"><div class="panel-head"><div><h3>${esc(c.title)}</h3><p>${esc(c.note)}</p></div></div><div class="chart-wrap"><canvas id="chart-${i}"></canvas></div></div>`).join('')}</div>` : ''}
      ${quick.length ? `<div class="panel"><div class="panel-head"><div><h3>Go to</h3><p>Pages you can use</p></div></div><div class="quick-grid">${quick.map(q => `<button class="quick-action" data-quick="${q.page}"><span>${q.icon}</span><strong>${esc(q.title)}</strong><small>${esc(q.note)}</small></button>`).join('')}</div></div>` : ''}`;
    $$('[data-quick]').forEach(b => b.onclick = () => window.openPage(b.dataset.quick));
    charts.forEach((spec, i) => drawChart(spec, `chart-${i}`));
  },
});

/* =====================================================================  REPORTS  */
definePage('reports', {
  title: 'Reports & Exports', group: 'Insights', icon: '▥', roles: ['admin', 'pharmacist', 'billing_staff'],   // the only roles the server gives reports to
  render: async () => {
    const reports = await Api.get('/reports');
    const now = new Date(), monthStart = `${todayISO().slice(0, 8)}01`;
    $('#page-content').innerHTML = `
      <div class="panel report-filters"><div class="panel-head"><div><h3>Report period</h3><p>Reports use the fields that apply to them (day, month, or from–to).</p></div></div>
        <div class="form-grid">
          <label>Day (daily / weekly)<input type="date" id="rp-date" value="${todayISO()}"></label>
          <label>Month (monthly)<input type="month" id="rp-month" value="${todayISO().slice(0, 7)}"></label>
          <label>From<input type="date" id="rp-from" value="${monthStart}"></label>
          <label>To<input type="date" id="rp-to" value="${todayISO()}"></label>
        </div></div>
      <div class="report-grid">${reports.length ? reports.map(r => `<div class="report-card"><div class="stat-icon">▥</div><h3 class="card-title">${esc(r.title || r.type)}</h3>
        <p>Uses: ${esc((r.parameters || []).join(', ') || 'no options')}</p>
        <div class="report-actions"><button class="btn secondary" data-report="${esc(r.type)}" data-format="json">Preview</button>${(r.formats || ['csv', 'xlsx', 'pdf']).filter(f => f !== 'json').map(f => `<button class="btn ${f === 'pdf' ? 'primary' : 'secondary'}" data-report="${esc(r.type)}" data-format="${f}" data-params="${esc((r.parameters || []).join(','))}">${f === 'xlsx' ? 'Excel' : f.toUpperCase()}</button>`).join('')}</div></div>`).join('') : '<div class="panel empty-state"><strong>No reports available for your role</strong></div>'}</div>
      <div id="report-preview" class="report-preview"></div>`;

    const query = (params, format) => {
      const q = new URLSearchParams({ format });
      if (params.includes('date')) q.set('date', $('#rp-date').value);
      if (params.includes('month')) q.set('month', $('#rp-month').value);
      if (params.includes('from')) { q.set('from', $('#rp-from').value); q.set('to', $('#rp-to').value); }
      return q.toString();
    };
    $$('[data-report]').forEach(btn => btn.onclick = async () => {
      const type = btn.dataset.report, format = btn.dataset.format;
      const params = (reports.find(r => r.type === type)?.parameters) || [];
      try {
        if (format === 'json') {
          const data = await Api.get(`/reports/${type}?${query(params, 'json')}`);
          $('#report-preview').innerHTML = `<div class="panel"><div class="panel-head"><h3>${esc(data.title || type)} — preview</h3><button class="btn secondary" id="close-preview">Close</button></div><pre class="json-preview">${esc(JSON.stringify(data, null, 2))}</pre></div>`;
          $('#close-preview').onclick = () => { $('#report-preview').innerHTML = ''; };
        } else {
          await Api.download(`/reports/${type}?${query(params, format)}`, `${type}_${todayISO()}.${format}`);
          toast(`${format.toUpperCase()} download started`);
        }
      } catch (e) { toast(e.message, true); }
    });
  },
});

/* =====================================================================  NOTIFICATIONS  */
definePage('notifications', {
  title: 'Notifications', group: 'System', icon: '♧', roles: ROLES,
  render: async () => {
    const data = await Api.get('/notifications?per_page=50');
    const notes = data.items || [];
    $('#page-content').innerHTML = `
      <div class="page-toolbar"><div><h3>Alerts for you</h3><p class="muted">${data.unread_count || 0} unread</p></div>
        <div class="toolbar-right">${Session.isAdmin ? '<button id="scan-alerts" class="btn secondary">↻ Check for new alerts</button>' : ''}<button id="read-all" class="btn primary">Mark all read</button></div></div>
      <div class="panel">${notes.length ? notes.map(n => `<div class="notification-item"><div class="notification-dot ${n.is_read ? 'read' : ''}"></div>
        <div class="grow"><strong>${esc(n.title)}</strong> ${n.severity && n.severity !== 'info' ? badge(n.severity) : ''}<p>${esc(n.message)}</p><small>${esc(dateTime(n.created_at))}</small></div>
        ${n.is_read ? '' : `<button class="text-btn" data-read="${n.id}">Mark read</button>`}</div>`).join('')
        : '<div class="empty-state"><strong>You are all caught up</strong><span>No alerts right now.</span></div>'}</div>`;

    const done = async (promise, message) => { try { await promise; if (message) toast(message); await window.openPage('notifications'); window.refreshNotificationCount(); } catch (e) { toast(e.message, true); } };
    $('#read-all').onclick = () => done(Api.post('/notifications/read-all'), 'All alerts marked as read');
    if ($('#scan-alerts')) $('#scan-alerts').onclick = () => done(Api.post('/notifications/refresh'), 'Alerts refreshed');
    $$('[data-read]').forEach(b => b.onclick = () => done(Api.post(`/notifications/${b.dataset.read}/read`)));
  },
});

/* =====================================================================  USERS  */
function openUserForm(user) {
  const editing = Boolean(user);
  openForm({
    title: editing ? `Edit ${user.username}` : 'Create user', eyebrow: 'Users & roles', wide: true,
    submitLabel: editing ? 'Save changes' : 'Create user',
    fields: [
      { name: 'full_name', label: 'Full name', required: true, value: user?.full_name },
      { name: 'username', label: 'Username', required: true, value: user?.username },
      { name: 'email', label: 'Email', type: 'email', required: true, value: user?.email },
      { name: 'phone', label: 'Phone', type: 'tel', value: user?.phone, sendEmpty: editing },
      { name: 'role', label: 'Role', type: 'select', required: true, options: ROLES, value: user?.role },
      ...(editing ? [] : [{ name: 'password', label: 'Temporary password', type: 'password', required: true, hint: 'At least 8 characters with a letter and a digit.' }]),
      ...(editing ? [{ name: 'is_active', label: 'Account is active', type: 'checkbox', value: user.is_active }] : []),
    ],
    onSubmit: async values => {
      if (editing) await Api.put(`/users/${user.id}`, values); else await Api.post('/users', values);
      reload();
      return editing ? 'User updated' : 'User created';
    },
  });
}

function openResetPassword(user) {
  openForm({
    title: 'Reset password', eyebrow: `${user.full_name} (${user.username})`, submitLabel: 'Set new password',
    fields: [{ name: 'new_password', label: 'New password', type: 'password', required: true, wide: true, hint: 'At least 8 characters with a letter and a digit. Tell the person to change it after signing in.' }],
    onSubmit: async values => { await Api.post(`/users/${user.id}/reset-password`, values); return 'Password reset'; },
  });
}

definePage('users', {
  title: 'Users & Roles', group: 'System', icon: '☻', roles: ['admin'],
  render: () => renderList({
    id: 'users', search: { placeholder: 'Search name, username or email…' },
    load: s => Api.get(`/users?per_page=15&page=${s.page}&q=${encodeURIComponent(s.q)}${s.filters.role ? `&role=${s.filters.role}` : ''}`),
    filters: [{ name: 'role', label: 'All roles', server: true, options: ROLES }],
    columns: [
      { label: 'Name', key: 'full_name' }, { label: 'Username', key: 'username' }, { label: 'Email', key: 'email' },
      { label: 'Role', key: 'role', type: 'status' }, { label: 'Status', render: r => badge(r.is_active ? 'active' : 'inactive') },
      { label: 'Last sign-in', key: 'last_login_at', type: 'datetime' },
    ],
    rowActions: r => [
      { label: 'Edit', onClick: () => openUserForm(r) },
      { label: 'Reset password', onClick: () => openResetPassword(r) },
      ...(r.is_active && r.id !== Session.user.id ? [{ label: 'Deactivate', danger: true, confirm: `Deactivate ${r.username}? They will not be able to sign in.`, onClick: async () => { await Api.del(`/users/${r.id}`); toast('User deactivated'); reload(); } }] : []),
    ],
    buttons: [{ label: '＋ Create user', onClick: () => openUserForm() }],
  }),
});

/* =====================================================================  AUDIT LOG  */
definePage('audit', {
  title: 'Audit Log', group: 'System', icon: '≋', roles: ['admin'],
  render: async () => {
    const actions = await Api.get('/audit-logs/actions').catch(() => []);
    const names = (Array.isArray(actions) ? actions : actions.actions || []).map(a => (typeof a === 'string' ? a : a.action));
    return renderList({
      id: 'audit', search: { placeholder: 'Search the description…' },
      load: s => Api.get(`/audit-logs?per_page=25&page=${s.page}&q=${encodeURIComponent(s.q)}${s.filters.action ? `&action=${encodeURIComponent(s.filters.action)}` : ''}`),
      filters: [{ name: 'action', label: 'All actions', server: true, options: names }],
      columns: [
        { label: 'Time', key: 'created_at', type: 'datetime' }, { label: 'User', key: 'username' },
        { label: 'Role', render: r => esc(titleCase(r.role)) }, { label: 'Action', key: 'action' },
        { label: 'Record', render: r => r.entity_type ? `${esc(r.entity_type)} #${esc(r.entity_id)}` : '—' },
        { label: 'What happened', key: 'description' }, { label: 'IP address', key: 'ip_address' },
      ],
      emptyHint: 'Nothing has been logged yet.',
    });
  },
});
