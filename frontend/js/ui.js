/* ui.js — small building blocks used by every page:
   formatting helpers, toast messages, the pop-up dialog, the form builder and the table builder. */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/* ---------- text + number formatting ---------- */

// Make text safe to put inside HTML. Empty values are shown as a dash.
function esc(value, dash = true) {
  if (value === null || value === undefined || value === '') return dash ? '—' : '';
  return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
const attr = value => esc(value, false);                     // for HTML attribute values
const titleCase = text => String(text ?? '').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());

function money(value) {
  if (value === null || value === undefined || value === '') return '—';
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value);
}

// The server stores times in UTC and sends them without a "Z"; add it so the browser shows local time.
function parseServerDate(text) {
  if (!text) return null;
  const s = String(text);
  if (s.length <= 10) return new Date(`${s}T00:00:00`);
  return new Date(/[zZ]$|[+-]\d\d:?\d\d$/.test(s) ? s : `${s}Z`);
}
function dateOnly(text) {
  const d = parseServerDate(text);
  return d && !isNaN(d) ? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
}
function dateTime(text) {
  const d = parseServerDate(text);
  return d && !isNaN(d) ? d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
}
function todayISO() {                                        // today's date on THIS computer, as YYYY-MM-DD
  const d = new Date(), pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Coloured pill for statuses (scheduled, paid, critical ...). Colours are defined in style.css (.status.<name>).
function badge(value) {
  if (value === null || value === undefined || value === '') return '—';
  const css = String(value).toLowerCase().replace(/[^a-z0-9_]/g, '_');
  return `<span class="status ${css}">${esc(titleCase(value))}</span>`;
}
const yesNo = value => badge(value ? 'yes' : 'no');

/* ---------- toast (small message in the corner) ---------- */
let toastTimer;
function toast(message, isError = false) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.toggle('error', isError);
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), isError ? 8000 : 4000);
}

/* ---------- the pop-up dialog (one shared <dialog> in index.html) ---------- */
const Dialog = {
  /* open({title, eyebrow, body, wide, buttons, onOpen})
     buttons: [{label, kind:'primary'|'secondary'|'danger', submit:true, onClick: async () => {}, keepOpen:true}] */
  open({ title, eyebrow = 'Smart Hospital', body = '', wide = false, buttons = [], onOpen }) {
    const dialog = $('#dialog');
    $('#dialog-title').textContent = title;
    $('#dialog-eyebrow').textContent = eyebrow;
    $('#dialog-body').innerHTML = body;
    Dialog.error('');
    dialog.classList.toggle('wide', wide);

    const bar = $('#dialog-actions');
    bar.innerHTML = '';
    buttons.forEach(b => {
      const btn = document.createElement('button');
      btn.className = `btn ${b.kind === 'danger' ? 'danger' : b.kind === 'primary' ? 'primary' : 'secondary'}`;
      btn.textContent = b.label;
      if (b.submit) { btn.type = 'submit'; btn.setAttribute('form', 'dialog-form'); }
      else {
        btn.type = 'button';
        btn.addEventListener('click', async () => {
          if (b.onClick) {
            Dialog.busy(true);
            try { await b.onClick(); } catch (e) { Dialog.error(e.message); Dialog.busy(false); return; }
            Dialog.busy(false);
          }
          if (!b.keepOpen) Dialog.close();
        });
      }
      bar.appendChild(btn);
    });
    if (!dialog.open) dialog.showModal();
    if (onOpen) onOpen($('#dialog-body'));
  },
  close() { const d = $('#dialog'); if (d.open) d.close(); },
  error(message) { $('#dialog-error').textContent = message || ''; },
  busy(on) { $$('#dialog-actions button').forEach(b => { b.disabled = on; }); },
};

/* ---------- confirm before something risky ---------- */
const confirmAction = message => window.confirm(message);

/* ---------- search boxes that look up records while you type ("lookups") ---------- */
const Lookups = {
  patients: async q => {
    const data = await Api.get(`/patients?per_page=8&q=${encodeURIComponent(q)}`);
    return (data.items || []).map(p => ({ value: p.id, label: p.full_name, sub: `${p.patient_code} · ${p.phone || 'no phone'}` }));
  },
};

/* ---------- form builder ----------
   A field is a small object:
     { name, label, type, required, options, load, value, hint, wide, min, max, numeric, placeholder }
   types: text number date time email tel password textarea checkbox select lookup rows
   - select:  options = ['a','b'] or [{value,label}]   OR   load = async () => [{value,label}]
   - lookup:  lookup = 'patients'  (search-as-you-type), selected = {value,label} to pre-fill
   - rows:    repeatable lines (e.g. medicines on a prescription), columns = [field, field ...]  */

function optionList(options, selected) {
  return (options || []).map(o => {
    const value = typeof o === 'object' ? o.value : o;
    const label = typeof o === 'object' ? o.label : titleCase(o);
    return `<option value="${attr(value)}" ${String(value) === String(selected ?? '') ? 'selected' : ''}>${esc(label)}</option>`;
  }).join('');
}

function inputHtml(f, value) {
  const req = f.required ? 'required' : '';
  const common = `name="${attr(f.name)}" ${req} ${f.disabled ? 'disabled' : ''}`;
  switch (f.type) {
    case 'textarea':
      return `<textarea ${common} rows="${f.rows || 3}" placeholder="${attr(f.placeholder)}">${attr(value)}</textarea>`;
    case 'select':
      return `<select ${common} data-numeric="${f.numeric ? 1 : ''}" data-value="${attr(value)}"><option value="">${f.load ? 'Loading…' : 'Select…'}</option>${f.options ? optionList(f.options, value) : ''}</select>`;
    case 'number':
      return `<input ${common} type="number" step="${f.step || 'any'}" ${f.min !== undefined ? `min="${f.min}"` : ''} ${f.max !== undefined ? `max="${f.max}"` : ''} value="${attr(value)}" placeholder="${attr(f.placeholder)}">`;
    default:
      return `<input ${common} type="${f.type || 'text'}" value="${attr(value)}" placeholder="${attr(f.placeholder)}" ${f.min !== undefined ? `min="${attr(f.min)}"` : ''} ${f.max !== undefined ? `max="${attr(f.max)}"` : ''} ${f.type === 'password' ? 'autocomplete="new-password"' : ''}>`;
  }
}

function fieldHtml(f) {
  const span = f.wide ? ' span-2' : '';
  const star = f.required ? ' *' : '';
  const hint = f.hint ? `<small class="field-hint">${esc(f.hint)}</small>` : '';
  const value = f.value ?? '';
  if (f.type === 'hidden') return `<input type="hidden" name="${attr(f.name)}" value="${attr(value)}">`;
  if (f.type === 'checkbox') {
    return `<label class="check-row${span}"><input type="checkbox" name="${attr(f.name)}" ${f.value ? 'checked' : ''}> <span>${esc(f.label)}${hint}</span></label>`;
  }
  if (f.type === 'lookup') {
    const sel = f.selected;
    return `<div class="field${span}"><span class="field-label">${esc(f.label)}${star}</span>
      <div class="lookup" data-lookup="${attr(f.lookup)}" data-field="${attr(f.name)}">
        <input type="text" class="lookup-input" placeholder="${attr(f.placeholder || 'Type a name, code or phone…')}" autocomplete="off" value="${attr(sel ? sel.label : '')}">
        <input type="hidden" name="${attr(f.name)}" value="${attr(sel ? sel.value : '')}">
        <div class="lookup-results hidden"></div>
      </div>${hint}</div>`;
  }
  if (f.type === 'rows') {
    return `<div class="field span-2"><span class="field-label">${esc(f.label)}${star}</span>
      <div class="rows" data-rows="${attr(f.name)}"><div class="rows-body"></div>
      <button type="button" class="btn secondary add-row">＋ ${esc(f.addLabel || 'Add row')}</button></div>${hint}</div>`;
  }
  if (f.type === 'custom') return `<div class="field span-2" id="${attr(f.id)}">${f.html || ''}</div>`;
  return `<label class="${span.trim()}">${esc(f.label)}${star}${inputHtml(f, value)}${hint}</label>`;
}

// Fill dropdowns that load their options from the server, and switch on lookups and row editors.
async function hydrateForm(form, fields) {
  for (const f of fields) {
    if (f.type === 'select' && f.load) {
      const select = form.elements[f.name];
      try {
        const options = await f.load();
        select.innerHTML = `<option value="">${options.length ? 'Select…' : (f.emptyText || 'Nothing available yet')}</option>${optionList(options, select.dataset.value)}`;
      } catch (e) { select.innerHTML = `<option value="">Could not load (${esc(e.message)})</option>`; }
    }
    if (f.type === 'lookup') wireLookup($(`[data-field="${f.name}"]`, form));
    if (f.type === 'rows') await wireRows($(`[data-rows="${f.name}"]`, form), f);
  }
}

function wireLookup(box) {
  const input = $('.lookup-input', box), hidden = $('input[type=hidden]', box), list = $('.lookup-results', box);
  const search = Lookups[box.dataset.lookup];
  let timer;
  const run = async () => {
    try {
      const items = await search(input.value.trim());
      list.innerHTML = items.length
        ? items.map(i => `<button type="button" class="lookup-item" data-id="${attr(i.value)}" data-label="${attr(i.label)}">${esc(i.label)}<small>${esc(i.sub)}</small></button>`).join('')
        : '<div class="lookup-empty">No match found</div>';
    } catch (e) { list.innerHTML = `<div class="lookup-empty">${esc(e.message)}</div>`; }
    list.classList.remove('hidden');
  };
  input.addEventListener('input', () => { hidden.value = ''; clearTimeout(timer); timer = setTimeout(run, 250); });
  input.addEventListener('focus', run);
  input.addEventListener('blur', () => setTimeout(() => list.classList.add('hidden'), 180));
  list.addEventListener('mousedown', e => {
    const item = e.target.closest('.lookup-item');
    if (!item) return;
    e.preventDefault();
    hidden.value = item.dataset.id;
    input.value = item.dataset.label;
    list.classList.add('hidden');
    hidden.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

async function wireRows(box, spec) {
  const body = $('.rows-body', box);
  const choices = {};                                         // options for select columns, loaded once
  for (const col of spec.columns) {
    if (col.type !== 'select' || !col.load) continue;
    try { choices[col.name] = await col.load(); }
    catch (e) { box.insertAdjacentHTML('afterbegin', `<small class="error-text">Could not load the ${esc(col.label)} list: ${esc(e.message)}</small>`); choices[col.name] = []; }
  }

  const addRow = () => {
    const line = document.createElement('div');
    line.className = 'row-line';
    line.innerHTML = spec.columns.map(col => {
      const input = col.type === 'select'
        ? `<select data-col="${attr(col.name)}"><option value="">${esc(col.label)}…</option>${optionList(choices[col.name] || col.options, '')}</select>`
        : `<input data-col="${attr(col.name)}" type="${col.type || 'text'}" ${col.min !== undefined ? `min="${col.min}"` : ''} ${col.type === 'number' ? 'step="any"' : ''} placeholder="${attr(col.label)}">`;
      return `<label>${esc(col.label)}${input}</label>`;
    }).join('') + '<button type="button" class="icon-btn remove-row" title="Remove">✕</button>';
    $('.remove-row', line).onclick = () => line.remove();
    body.appendChild(line);
  };
  $('.add-row', box).onclick = addRow;
  for (let i = 0; i < (spec.minRows ?? 1); i++) addRow();
}

// Read the form into a plain object. Returns {values, error}.
function readForm(form, fields) {
  const values = {};
  for (const f of fields) {
    if (f.skip || f.type === 'custom') continue;
    if (f.type === 'checkbox') { values[f.name] = form.elements[f.name].checked; continue; }

    if (f.type === 'rows') {
      const rows = [];
      let problem = '';
      $$(`[data-rows="${f.name}"] .row-line`, form).forEach((line, index) => {
        const row = {};
        spec_loop: for (const col of f.columns) {
          const el = $(`[data-col="${col.name}"]`, line);
          const text = el.value.trim();
          if (text === '') { if (col.required) { problem = problem || `Line ${index + 1}: ${col.label} is required`; } continue spec_loop; }
          row[col.name] = (col.type === 'number' || col.numeric) ? Number(text) : text;
        }
        if (Object.keys(row).length) rows.push(row);
      });
      if (problem) return { error: problem };
      if (f.required && !rows.length) return { error: `Add at least one line to “${f.label}”` };
      values[f.name] = rows;
      continue;
    }

    const el = form.elements[f.name];
    const text = (el.value || '').trim();
    if (text === '') {
      if (f.required) return { error: f.type === 'lookup' ? `Please pick a ${f.label.toLowerCase()} from the list` : `${f.label} is required` };
      if (f.sendEmpty) values[f.name] = null;
      continue;
    }
    values[f.name] = (f.type === 'number' || f.numeric) ? Number(text) : text;
  }
  return { values };
}

/* openForm({title, fields, submitLabel, onSubmit, onOpen, intro, wide}) — shows a form in the dialog.
   onSubmit(values) runs when the form is valid; return a message to show as a toast. Throw to show an error. */
function openForm({ title, eyebrow, intro = '', fields, submitLabel = 'Save', onSubmit, onOpen, after, wide = false }) {
  Dialog.open({
    title, eyebrow, wide,
    body: `${intro ? `<p class="muted dialog-intro">${intro}</p>` : ''}<form id="dialog-form" class="form-grid">${fields.map(fieldHtml).join('')}</form>`,
    buttons: [{ label: 'Cancel', kind: 'secondary' }, { label: submitLabel, kind: 'primary', submit: true }],
    onOpen: async () => {
      const form = $('#dialog-form');
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const { values, error } = readForm(form, fields);
        if (error) return Dialog.error(error);
        Dialog.error(''); Dialog.busy(true);
        try {
          const message = await onSubmit(values, form);
          Dialog.close();
          toast(message || 'Saved');
          if (after) after();
        } catch (err) { Dialog.error(err.message); }
        Dialog.busy(false);
      });
      await hydrateForm(form, fields);
      if (onOpen) onOpen(form);
    },
  });
}

/* ---------- tables ---------- */

// column = {label, key, type:'status'|'money'|'date'|'datetime'|'bool', render:(row)=>html}
function cellHtml(col, row) {
  if (col.render) return col.render(row);
  const v = row[col.key];
  switch (col.type) {
    case 'status': return badge(v);
    case 'money': return esc(money(v));
    case 'date': return esc(dateOnly(v));
    case 'datetime': return esc(dateTime(v));
    case 'bool': return yesNo(v);
    default: return esc(v);
  }
}

// Returns the table HTML. Call wireTable() afterwards so the action buttons work.
function tableHtml(columns, rows, actionsOf) {
  if (!rows.length) return '<div class="empty-state"><strong>Nothing here yet</strong><span>Records will appear here as soon as they are added.</span></div>';
  const withActions = typeof actionsOf === 'function';
  const head = columns.map(c => `<th>${esc(c.label)}</th>`).join('') + (withActions ? '<th>Actions</th>' : '');
  const body = rows.map((row, r) => {
    const cells = columns.map(c => `<td>${cellHtml(c, row)}</td>`).join('');
    const buttons = withActions ? actionsOf(row).map((a, i) =>
      `<button class="text-btn ${a.danger ? 'danger-text' : ''}" data-row="${r}" data-act="${i}">${esc(a.label)}</button>`).join('') : '';
    return `<tr>${cells}${withActions ? `<td><div class="row-actions">${buttons}</div></td>` : ''}</tr>`;
  }).join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function wireTable(root, rows, actionsOf) {
  if (typeof actionsOf !== 'function') return;
  $$('[data-act]', root).forEach(btn => {
    btn.addEventListener('click', async () => {
      const row = rows[Number(btn.dataset.row)];
      const action = actionsOf(row)[Number(btn.dataset.act)];
      if (action.confirm && !confirmAction(action.confirm)) return;
      try { await action.onClick(row); } catch (e) { toast(e.message, true); }
    });
  });
}

/* ---------- a full list page: toolbar + search + filters + table + pager ----------
   renderList({id, load, columns, rowActions, buttons, search, filters, emptyHint})
   - load({page, q}) must return an array, or the paged object {items, page, pages, total}
   - search: {placeholder}  -> the typed text is passed to load() as q (server-side search)
   - filters: [{name, label, options:[...], test:(row, value) => boolean}]  (applied in the browser) */
const listState = {};                                        // remembers search/page per list while you stay logged in

async function renderList(cfg) {
  const host = typeof cfg.host === 'string' ? $(cfg.host) : (cfg.host || $('#page-content'));
  const state = listState[cfg.id] || (listState[cfg.id] = { page: 1, q: '', filters: { ...(cfg.defaultFilters || {}) } });
  const filterOf = name => (cfg.filters || []).find(f => f.name === name);

  host.innerHTML = `
    <div class="page-toolbar">
      <div class="toolbar-left">
        ${cfg.search ? `<input class="search-input list-search" placeholder="${attr(cfg.search.placeholder || 'Search…')}" value="${attr(state.q)}">` : ''}
        ${(cfg.filters || []).map(f => `<select class="filter-select" data-filter="${attr(f.name)}"><option value="">${esc(f.label)}</option>${optionList(f.options, state.filters[f.name])}</select>`).join('')}
        <span class="muted list-count"></span>
      </div>
      <div class="toolbar-right list-buttons"></div>
    </div>
    <div class="table-wrap list-table"><div class="empty-state">Loading…</div></div>
    <div class="pagination list-pager"></div>`;

  (cfg.buttons || []).forEach(b => {
    const btn = document.createElement('button');
    btn.className = `btn ${b.kind === 'secondary' ? 'secondary' : 'primary'}`;
    btn.textContent = b.label;
    btn.onclick = () => b.onClick();
    $('.list-buttons', host).appendChild(btn);
  });

  let lastData = null;
  const draw = () => {
    let rows = Array.isArray(lastData) ? lastData : (lastData.items || []);
    for (const f of (cfg.filters || [])) {
      if (state.filters[f.name] && !f.server) rows = rows.filter(r => f.test(r, state.filters[f.name]));
    }
    const table = $('.list-table', host);
    table.innerHTML = tableHtml(cfg.columns, rows, cfg.rowActions);
    wireTable(table, rows, cfg.rowActions);
    const paged = !Array.isArray(lastData) && lastData.pages;
    $('.list-count', host).textContent = paged
      ? `${lastData.total} record${lastData.total === 1 ? '' : 's'}`
      : `${rows.length} record${rows.length === 1 ? '' : 's'}`;
    const pager = $('.list-pager', host);
    pager.innerHTML = paged && lastData.pages > 1
      ? `<span>Page ${lastData.page} of ${lastData.pages}</span><span><button class="btn secondary pg-prev" ${lastData.page <= 1 ? 'disabled' : ''}>← Previous</button> <button class="btn secondary pg-next" ${lastData.page >= lastData.pages ? 'disabled' : ''}>Next →</button></span>`
      : `<span>${cfg.emptyHint && !rows.length ? esc(cfg.emptyHint) : ''}</span>`;
    if ($('.pg-prev', pager)) $('.pg-prev', pager).onclick = () => { state.page--; fetchRows(); };
    if ($('.pg-next', pager)) $('.pg-next', pager).onclick = () => { state.page++; fetchRows(); };
  };
  async function fetchRows() {
    try { lastData = await cfg.load(state); draw(); }
    catch (e) { $('.list-table', host).innerHTML = `<div class="empty-state"><strong>Could not load this list</strong><span>${esc(e.message)}</span></div>`; }
  }

  if (cfg.search) {
    let timer;
    $('.list-search', host).addEventListener('input', e => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = e.target.value.trim(); state.page = 1; fetchRows(); }, 300);
    });
  }
  $$('.filter-select', host).forEach(sel => sel.addEventListener('change', () => {
    state.filters[sel.dataset.filter] = sel.value;
    if (filterOf(sel.dataset.filter).server) { state.page = 1; fetchRows(); }   // the server does the filtering
    else if (lastData) draw();                                                     // filter what we already have
  }));
  await fetchRows();
}

/* ---------- read-only "label: value" grid used in detail dialogs ---------- */
function detailGrid(pairs) {
  return `<dl class="detail-grid">${pairs.map(([label, html]) => `<div><dt>${esc(label)}</dt><dd>${html ?? '—'}</dd></div>`).join('')}</dl>`;
}
