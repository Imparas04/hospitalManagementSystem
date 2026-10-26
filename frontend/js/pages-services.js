/* pages-services.js — laboratory, pharmacy (medicines + prescriptions) and billing. */

/* =====================================================================  LABORATORY  */
function openLabOrderForm() {
  openForm({
    title: 'Order a lab test', eyebrow: 'Laboratory', wide: true, submitLabel: 'Order test',
    fields: [
      { name: 'patient_id', label: 'Patient', type: 'lookup', lookup: 'patients', required: true, numeric: true, wide: true },
      { name: 'lab_test_id', label: 'Test', type: 'select', numeric: true, required: true, load: Loaders.labTests, emptyText: 'No lab tests yet — a lab technician or admin must add them', wide: true },
      { name: 'notes', label: 'Notes for the lab', type: 'textarea', wide: true },
    ],
    onSubmit: async values => { await Api.post('/lab/orders', values); reload(); return 'Lab test ordered'; },
  });
}

function openLabTestForm() {
  openForm({
    title: 'Add lab test', eyebrow: 'Test catalogue',
    fields: [
      { name: 'name', label: 'Test name', required: true, placeholder: 'e.g. Complete Blood Count' },
      { name: 'code', label: 'Short code', required: true, placeholder: 'e.g. CBC', hint: 'Up to 20 characters, must be unique.' },
      { name: 'normal_range', label: 'Normal range', placeholder: 'e.g. 70-100 mg/dL', wide: true },
      { name: 'price', label: 'Price (₹)', type: 'number', min: 0, value: 300 },
    ],
    onSubmit: async values => { await Api.post('/lab/tests', values); reload(); return 'Lab test added'; },
  });
}

function openLabResultForm(order) {
  openForm({
    title: 'Enter result', eyebrow: `${order.test_name} · ${order.patient_name}`, submitLabel: 'Save result',
    fields: [
      { name: 'result_value', label: 'Result', type: 'textarea', required: true, wide: true, hint: 'e.g. “WBC 8,200 per µL”' },
      { name: 'is_abnormal', label: 'Result is outside the normal range', type: 'checkbox' },
    ],
    onSubmit: async values => { await Api.post(`/lab/orders/${order.id}/result`, values); reload(); return 'Result saved'; },
  });
}

function openLabReviewForm(order) {
  openForm({
    title: 'Review result', eyebrow: `${order.test_name} · ${order.patient_name}`, submitLabel: 'Mark as reviewed',
    intro: `Result: <strong>${esc(order.result?.result_value)}</strong>${order.result?.is_abnormal ? ' — flagged abnormal' : ''}`,
    fields: [{ name: 'reviewer_notes', label: 'Your notes', type: 'textarea', wide: true }],
    onSubmit: async values => { await Api.post(`/lab/orders/${order.id}/review`, values); reload(); return 'Result reviewed'; },
  });
}

definePage('laboratory', {
  title: 'Laboratory', group: 'Resources', icon: '⚗', roles: ['admin', 'doctor', 'lab_technician'],
  render: () => renderList({
    id: 'laboratory',
    load: () => Api.get('/lab/orders'),
    filters: [{ name: 'status', label: 'All statuses', options: ['ordered', 'sample_collected', 'processing', 'result_entered', 'reviewed'], test: (r, v) => r.status === v }],
    columns: [
      { label: 'Order', key: 'id' }, { label: 'Patient', key: 'patient_name' },
      { label: 'Test', render: r => `${esc(r.test_name)} <small class="muted">(${esc(r.test_code)})</small>` },
      { label: 'Ordered by', key: 'doctor_name' }, { label: 'Status', key: 'status', type: 'status' },
      { label: 'Ordered', key: 'ordered_at', type: 'datetime' },
      { label: 'Result', render: r => r.result ? `${esc(r.result.result_value)} ${r.result.is_abnormal ? '<span class="status critical">Abnormal</span>' : ''}` : '—' },
      { label: 'Reviewer notes', render: r => esc(r.result?.reviewer_notes) },
    ],
    rowActions: r => {
      const move = (label, status) => ({ label, onClick: async () => { await Api.put(`/lab/orders/${r.id}/status`, { status }); toast('Order updated'); reload(); } });
      const tech = hasRole('admin', 'lab_technician');
      if (r.status === 'ordered' && tech) return [move('Collect sample', 'sample_collected')];
      if (r.status === 'sample_collected' && tech) return [move('Start processing', 'processing')];
      if (r.status === 'processing' && tech) return [{ label: 'Enter result', onClick: () => openLabResultForm(r) }];
      if (r.status === 'result_entered' && hasRole('admin', 'doctor')) return [{ label: 'Review', onClick: () => openLabReviewForm(r) }];
      return [];
    },
    buttons: [
      ...(hasRole('doctor') ? [{ label: '＋ Order test', onClick: openLabOrderForm }] : []),
      ...(hasRole('admin', 'lab_technician') ? [{ label: '＋ Add lab test', kind: hasRole('doctor') ? 'secondary' : 'primary', onClick: openLabTestForm }] : []),
    ],
    emptyHint: hasRole('doctor') ? 'No lab orders yet. Use “Order test”.' : 'No lab orders yet.',
  }),
});

/* =====================================================================  PHARMACY  */
function openMedicineForm() {
  openForm({
    title: 'Add medicine', eyebrow: 'Pharmacy',
    fields: [
      { name: 'name', label: 'Medicine name', required: true, wide: true, placeholder: 'e.g. Paracetamol 500mg' },
      { name: 'unit', label: 'Form', type: 'select', required: true, options: ['tablet', 'syrup', 'injection', 'ointment', 'drops'] },
      { name: 'unit_price', label: 'Price per unit (₹)', type: 'number', required: true, min: 0 },
      { name: 'reorder_level', label: 'Warn me when stock falls to', type: 'number', min: 0, step: 1, value: 10, wide: true },
    ],
    onSubmit: async values => { await Api.post('/pharmacy/medicines', values); reload(); return 'Medicine added — now add its stock.'; },
  });
}

function openStockForm(medicine) {
  const nextYear = new Date(); nextYear.setFullYear(nextYear.getFullYear() + 1);
  openForm({
    title: 'Add stock', eyebrow: medicine.name, submitLabel: 'Add stock',
    fields: [
      { name: 'batch_number', label: 'Batch number', required: true },
      { name: 'expiry_date', label: 'Expiry date', type: 'date', required: true, min: todayISO() },
      { name: 'purchase_quantity', label: `Quantity received (${medicine.unit}s)`, type: 'number', required: true, min: 1, step: 1, wide: true },
    ],
    onSubmit: async values => { await Api.post(`/pharmacy/medicines/${medicine.id}/batches`, values); reload(); return 'Stock added'; },
  });
}

definePage('pharmacy', {
  title: 'Pharmacy & Stock', group: 'Resources', icon: '℞', roles: ['admin', 'pharmacist'],
  render: () => renderList({
    id: 'pharmacy', search: { placeholder: 'Search medicines…' },
    load: s => Api.get(`/pharmacy/medicines?q=${encodeURIComponent(s.q)}`),
    filters: [{ name: 'stock', label: 'All stock levels', options: [{ value: 'low', label: 'Low stock only' }], test: r => r.is_low_stock }],
    columns: [
      { label: 'Medicine', key: 'name' }, { label: 'Form', key: 'unit' }, { label: 'Price / unit', key: 'unit_price', type: 'money' },
      { label: 'In stock', key: 'total_available' }, { label: 'Warn at', key: 'reorder_level' },
      { label: 'Stock level', render: r => badge(r.is_low_stock ? 'low stock' : 'ok') },
    ],
    rowActions: r => hasRole('admin', 'pharmacist') ? [{ label: 'Add stock', onClick: () => openStockForm(r) }] : [],
    buttons: hasRole('admin', 'pharmacist') ? [{ label: '＋ Add medicine', onClick: openMedicineForm }] : [],
    emptyHint: 'No medicines yet. Use “Add medicine”, or run “flask --app run.py seed-demo-data”.',
  }),
});

/* =====================================================================  PRESCRIPTIONS  */
function openPrescriptionForm() {
  openForm({
    title: 'New prescription', eyebrow: 'Prescriptions', wide: true, submitLabel: 'Save prescription',
    fields: [
      { name: 'patient_id', label: 'Patient', type: 'lookup', lookup: 'patients', required: true, numeric: true, wide: true },
      { name: 'items', label: 'Medicines', type: 'rows', required: true, addLabel: 'Add medicine', columns: [
        { name: 'medicine_id', label: 'Medicine', type: 'select', numeric: true, required: true, load: Loaders.medicines },
        { name: 'dosage', label: 'Dosage', required: true },
        { name: 'quantity', label: 'Quantity', type: 'number', min: 1, required: true },
      ] },
      { name: 'notes', label: 'Notes for the pharmacist', type: 'textarea', wide: true },
    ],
    onSubmit: async values => { await Api.post('/prescriptions', values); reload(); return 'Prescription saved'; },
  });
}

definePage('prescriptions', {
  title: 'Prescriptions', group: 'Resources', icon: '✎', roles: ['admin', 'doctor', 'pharmacist'],
  render: () => renderList({
    id: 'prescriptions',
    load: s => Api.get(`/prescriptions?per_page=15&page=${s.page}${s.filters.status ? `&status=${s.filters.status}` : ''}`),
    filters: [{ name: 'status', label: 'All statuses', server: true, options: ['pending', 'partially_issued', 'issued'] }],
    columns: [
      { label: 'Rx', key: 'id' }, { label: 'Patient', key: 'patient_name' }, { label: 'Doctor', key: 'doctor_name' },
      { label: 'Medicines', render: r => (r.items || []).map(i => `${esc(i.medicine_name)} — ${esc(i.dosage)} × ${i.quantity_prescribed}${i.quantity_issued ? ` <small class="muted">(${i.quantity_issued} given)</small>` : ''}`).join('<br>') || '—' },
      { label: 'Status', key: 'status', type: 'status' }, { label: 'Created', key: 'created_at', type: 'datetime' },
    ],
    rowActions: r => hasRole('admin', 'pharmacist') && r.status !== 'issued'
      ? [{ label: 'Issue medicines', confirm: 'Give these medicines to the patient and reduce the stock?', onClick: async () => { await Api.post(`/prescriptions/${r.id}/issue`); toast('Medicines issued'); reload(); } }] : [],
    buttons: hasRole('doctor') ? [{ label: '＋ New prescription', onClick: openPrescriptionForm }] : [],
    emptyHint: 'No prescriptions yet.',
  }),
});

/* =====================================================================  BILLING  */
const PAYMENT_METHODS = ['cash', 'card', 'upi', 'bank_transfer', 'insurance'];

function openBillForm() {
  openForm({
    title: 'Generate bill', eyebrow: 'Billing', wide: true, submitLabel: 'Generate bill',
    intro: 'Consultations, lab tests, issued medicines and bed days recorded for this patient are added automatically. Add anything else below.',
    fields: [
      // Billing staff are not allowed to read patient records, so they identify the patient by the patient ID (e.g. P2026000001).
      hasRole('billing_staff')
        ? { name: 'patient_code', label: 'Patient ID', required: true, wide: true, placeholder: 'e.g. P2026000001', hint: 'The ID printed on the patient card or admission slip.' }
        : { name: 'patient_id', label: 'Patient', type: 'lookup', lookup: 'patients', required: true, numeric: true, wide: true },
      { name: 'discount_percent', label: 'Discount %', type: 'number', min: 0, max: 100 },
      { name: 'tax_percent', label: 'Tax %', type: 'number', min: 0, max: 100 },
      { name: 'other_services', label: 'Other services (optional)', type: 'rows', minRows: 0, addLabel: 'Add service', columns: [
        { name: 'description', label: 'Description', required: true },
        { name: 'quantity', label: 'Qty', type: 'number', min: 1 },
        { name: 'unit_price', label: 'Price (₹)', type: 'number', min: 0, required: true },
      ] },
    ],
    onSubmit: async values => {
      if (!values.other_services.length) delete values.other_services;
      const bill = await Api.post('/bills', values);
      reload();
      return `Bill ${bill.bill_number} created — total ${money(bill.total_amount)}`;
    },
  });
}

function openPaymentForm(bill) {
  openForm({
    title: 'Take payment', eyebrow: `${bill.bill_number} · ${bill.patient_name} · due ${money(bill.outstanding_amount)}`, submitLabel: 'Record payment',
    fields: [
      { name: 'amount', label: 'Amount (₹)', type: 'number', required: true, min: 0.01, value: bill.outstanding_amount },
      { name: 'method', label: 'Method', type: 'select', required: true, options: PAYMENT_METHODS, value: 'cash' },
      { name: 'reference', label: 'Reference / transaction ID', wide: true },
    ],
    onSubmit: async values => { const r = await Api.post(`/bills/${bill.id}/payments`, values); reload(); return `Payment recorded — receipt ${r.payment.receipt_number}`; },
    after: () => openBillView(bill.id),
  });
}

function openBillItemForm(bill) {
  openForm({
    title: 'Add item to bill', eyebrow: bill.bill_number, submitLabel: 'Add item',
    fields: [
      { name: 'description', label: 'Description', required: true, wide: true },
      { name: 'quantity', label: 'Quantity', type: 'number', min: 1, step: 1, value: 1 },
      { name: 'unit_price', label: 'Price (₹)', type: 'number', required: true, min: 0 },
    ],
    onSubmit: async values => { await Api.post(`/bills/${bill.id}/items`, values); reload(); return 'Item added'; },
    after: () => openBillView(bill.id),
  });
}

function openAdjustForm(bill) {
  openForm({
    title: 'Change discount / tax', eyebrow: bill.bill_number, submitLabel: 'Apply',
    fields: [
      { name: 'discount_percent', label: 'Discount %', type: 'number', min: 0, max: 100, value: bill.discount_percent },
      { name: 'tax_percent', label: 'Tax %', type: 'number', min: 0, max: 100, value: bill.tax_percent },
    ],
    onSubmit: async values => { await Api.put(`/bills/${bill.id}/adjust`, values); reload(); return 'Bill updated'; },
    after: () => openBillView(bill.id),
  });
}

async function openBillView(id) {
  const bill = await Api.get(`/bills/${id}`);
  const canEdit = hasRole('admin', 'billing_staff');
  const items = `<div class="table-wrap"><table><thead><tr><th>Item</th><th>Type</th><th>Qty</th><th>Price</th><th>Amount</th></tr></thead><tbody>${
    (bill.items || []).map(i => `<tr><td>${esc(i.description)}</td><td>${esc(titleCase(i.category))}</td><td>${i.quantity}</td><td>${esc(money(i.unit_price))}</td><td>${esc(money(i.amount))}</td></tr>`).join('') || '<tr><td colspan="5">No items</td></tr>'}</tbody></table></div>`;
  const payments = (bill.payments || []).length
    ? `<div class="table-wrap"><table><thead><tr><th>Receipt</th><th>Date</th><th>Method</th><th>Amount</th><th></th></tr></thead><tbody>${
      bill.payments.map(p => `<tr><td>${esc(p.receipt_number)}</td><td>${esc(dateTime(p.paid_at))}</td><td>${esc(titleCase(p.method))}</td><td>${esc(money(p.amount))}</td><td><button class="text-btn" data-receipt="${p.id}" data-no="${attr(p.receipt_number)}">Receipt PDF</button></td></tr>`).join('')}</tbody></table></div>`
    : '<p class="muted">No payments yet.</p>';

  Dialog.open({
    title: `Bill ${bill.bill_number}`, eyebrow: bill.patient_name, wide: true,
    body: `${detailGrid([
      ['Status', badge(bill.status)], ['Created', esc(dateTime(bill.created_at))],
      ['Subtotal', esc(money(bill.subtotal))], ['Discount', `${esc(money(bill.discount_amount))} (${bill.discount_percent}%)`],
      ['Tax', `${esc(money(bill.tax_amount))} (${bill.tax_percent}%)`], ['Total', `<strong>${esc(money(bill.total_amount))}</strong>`],
      ['Paid', esc(money(bill.amount_paid))], ['Outstanding', `<strong>${esc(money(bill.outstanding_amount))}</strong>`],
    ])}<h3 class="section-title">Items</h3>${items}<h3 class="section-title">Payments</h3>${payments}`,
    buttons: [
      ...(canEdit && bill.status !== 'paid' ? [{ label: 'Take payment', kind: 'primary', keepOpen: true, onClick: () => openPaymentForm(bill) }] : []),
      ...(canEdit ? [{ label: 'Add item', kind: 'secondary', keepOpen: true, onClick: () => openBillItemForm(bill) }, { label: 'Discount / tax', kind: 'secondary', keepOpen: true, onClick: () => openAdjustForm(bill) }] : []),
      { label: 'Download PDF', kind: 'secondary', keepOpen: true, onClick: () => Api.download(`/bills/${bill.id}/pdf`, `${bill.bill_number}.pdf`) },
      { label: 'Close', kind: 'secondary' },
    ],
    onOpen: root => $$('[data-receipt]', root).forEach(b => b.onclick = () =>
      Api.download(`/payments/${b.dataset.receipt}/receipt/pdf`, `${b.dataset.no}.pdf`).catch(e => Dialog.error(e.message))),
  });
}

definePage('billing', {
  title: 'Billing & Payments', group: 'Finance', icon: '₹', roles: ['admin', 'billing_staff'],
  render: () => renderList({
    id: 'billing',
    load: s => Api.get(`/bills?per_page=15&page=${s.page}${s.filters.status ? `&status=${s.filters.status}` : ''}`),
    filters: [{ name: 'status', label: 'All bills', server: true, options: ['unpaid', 'partially_paid', 'paid'] }],
    columns: [
      { label: 'Bill', key: 'bill_number' }, { label: 'Patient', key: 'patient_name' },
      { label: 'Total', key: 'total_amount', type: 'money' }, { label: 'Paid', key: 'amount_paid', type: 'money' },
      { label: 'Outstanding', key: 'outstanding_amount', type: 'money' }, { label: 'Status', key: 'status', type: 'status' },
      { label: 'Created', key: 'created_at', type: 'datetime' },
    ],
    rowActions: r => [
      { label: 'View', onClick: () => openBillView(r.id) },
      ...(hasRole('admin', 'billing_staff') && r.status !== 'paid' ? [{ label: 'Take payment', onClick: () => openPaymentForm(r) }] : []),
      { label: 'PDF', onClick: () => Api.download(`/bills/${r.id}/pdf`, `${r.bill_number}.pdf`) },
    ],
    buttons: hasRole('admin', 'billing_staff') ? [{ label: '＋ Generate bill', onClick: openBillForm }] : [],
    emptyHint: 'No bills yet.',
  }),
});
