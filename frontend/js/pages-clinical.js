/* pages-clinical.js — patients, doctors, departments, appointments, emergency, wards & beds, admissions. */

const reload = () => window.reloadPage();                   // refresh the page that is open (defined in main.js)

/* =====================================================================  PATIENTS  */
function patientFields(p = {}, editing = false) {
  const clearable = editing;                                // when editing, an emptied box clears the saved value
  return [
    { name: 'full_name', label: 'Full name', required: true, value: p.full_name },
    { name: 'date_of_birth', label: 'Date of birth', type: 'date', required: true, max: todayISO(), value: p.date_of_birth },
    { name: 'gender', label: 'Gender', type: 'select', required: true, options: ['male', 'female', 'other'], value: p.gender },
    { name: 'phone', label: 'Phone', type: 'tel', required: true, value: p.phone, hint: '7-15 digits' },
    { name: 'email', label: 'Email', type: 'email', value: p.email, sendEmpty: clearable },
    { name: 'blood_group', label: 'Blood group', type: 'select', options: BLOOD_GROUPS, value: p.blood_group && p.blood_group !== 'unknown' ? p.blood_group : '' },
    { name: 'address', label: 'Address', wide: true, value: p.address, sendEmpty: clearable },
    { name: 'emergency_contact_name', label: 'Emergency contact name', value: p.emergency_contact_name, sendEmpty: clearable },
    { name: 'emergency_contact_phone', label: 'Emergency contact phone', type: 'tel', value: p.emergency_contact_phone, sendEmpty: clearable },
    editing
      ? { name: 'registration_pending', label: 'Registration details are still incomplete', type: 'checkbox', value: p.registration_pending }
      : { name: 'is_emergency_registration', label: 'Emergency registration (details will be completed later)', type: 'checkbox' },
  ];
}

function openPatientForm(patient) {
  const editing = Boolean(patient);
  openForm({
    title: editing ? `Edit ${patient.full_name}` : 'Register patient',
    eyebrow: editing ? patient.patient_code : 'New patient',
    fields: patientFields(patient || {}, editing),
    submitLabel: editing ? 'Save changes' : 'Register patient',
    onSubmit: async values => {
      if (editing) await Api.put(`/patients/${patient.id}`, values);
      else await Api.post('/patients', values);
      reload();
      return editing ? 'Patient updated' : 'Patient registered';
    },
  });
}

async function openPatientView(id) {
  const [patient, history, visits] = await Promise.all([
    Api.get(`/patients/${id}`), Api.get(`/patients/${id}/medical-history`), Api.get(`/patients/${id}/visits`)]);
  const canEdit = hasRole('admin', 'receptionist', 'doctor');
  const list = (rows, line) => rows.length ? `<ul class="plain-list">${rows.map(line).join('')}</ul>` : '<p class="muted">Nothing recorded yet.</p>';

  const body = `
    ${detailGrid([
      ['Patient ID', esc(patient.patient_code)], ['Age / gender', `${esc(patient.age)} · ${esc(titleCase(patient.gender))}`],
      ['Date of birth', esc(dateOnly(patient.date_of_birth))], ['Phone', esc(patient.phone)],
      ['Email', esc(patient.email)], ['Blood group', esc(patient.blood_group)],
      ['Address', esc(patient.address)], ['Emergency contact', `${esc(patient.emergency_contact_name)} ${patient.emergency_contact_phone ? '· ' + esc(patient.emergency_contact_phone) : ''}`],
    ])}
    ${patient.registration_pending ? '<p class="notice">Registration is not complete yet — use “Edit” to finish the details.</p>' : ''}
    <h3 class="section-title">Medical history</h3>
    ${list(history, h => `<li><strong>${esc(titleCase(h.condition_type))}</strong> — ${esc(h.description)}<small>${esc(h.recorded_by)} · ${esc(dateTime(h.recorded_at))}</small></li>`)}
    ${canEdit ? `<form class="inline-form" data-kind="history">
        <select name="condition_type" required><option value="">Type…</option><option value="allergy">Allergy</option><option value="chronic_condition">Chronic condition</option><option value="surgery">Surgery</option><option value="note">Note</option></select>
        <input name="description" required placeholder="Describe it (e.g. Penicillin allergy)">
        <button class="btn secondary" type="submit">Add</button></form>` : ''}
    <h3 class="section-title">Visits</h3>
    ${list(visits, v => `<li><strong>${esc(titleCase(v.visit_type))}</strong> — ${esc(v.reason)}<small>${esc(v.recorded_by)} · ${esc(dateTime(v.visit_date))}</small></li>`)}
    ${canEdit ? `<form class="inline-form" data-kind="visits">
        <select name="visit_type" required><option value="">Type…</option><option value="opd">OPD</option><option value="emergency">Emergency</option><option value="follow_up">Follow-up</option></select>
        <input name="reason" required placeholder="Reason for the visit">
        <button class="btn secondary" type="submit">Add</button></form>` : ''}`;

  Dialog.open({
    title: patient.full_name, eyebrow: 'Patient record', wide: true, body,
    buttons: [
      ...(canEdit ? [{ label: 'Edit details', kind: 'secondary', keepOpen: true, onClick: () => openPatientForm(patient) }] : []),
      { label: 'Close', kind: 'primary' }],
    onOpen: root => $$('.inline-form', root).forEach(form => form.addEventListener('submit', async e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      try {
        await Api.post(`/patients/${id}/${form.dataset.kind === 'history' ? 'medical-history' : 'visits'}`, data);
        toast('Saved');
        openPatientView(id);                                // show the refreshed record
      } catch (err) { Dialog.error(err.message); }
    })),
  });
}

definePage('patients', {
  title: 'Patients', group: 'Care management', icon: '♙', roles: ['admin', 'receptionist', 'doctor', 'nurse'],
  render: () => renderList({
    id: 'patients', search: { placeholder: 'Search by name, patient ID or phone…' },
    load: s => Api.get(`/patients?per_page=15&page=${s.page}&q=${encodeURIComponent(s.q)}`),
    columns: [
      { label: 'Patient ID', key: 'patient_code' },
      { label: 'Name', render: r => `${esc(r.full_name)}${r.registration_pending ? ' <span class="status pending">Details pending</span>' : ''}` },
      { label: 'Age / gender', render: r => `${esc(r.age)} · ${esc(titleCase(r.gender))}` },
      { label: 'Phone', key: 'phone' }, { label: 'Blood group', key: 'blood_group' },
      { label: 'Registered', key: 'created_at', type: 'date' },
    ],
    rowActions: r => [
      { label: 'View', onClick: () => openPatientView(r.id) },
      ...(hasRole('admin', 'receptionist', 'doctor') ? [{ label: 'Edit', onClick: () => openPatientForm(r) }] : []),
    ],
    buttons: hasRole('admin', 'receptionist') ? [{ label: '＋ Register patient', onClick: () => openPatientForm() }] : [],
    emptyHint: 'No patients found. Use “Register patient” to add the first one.',
  }),
});

/* =====================================================================  DEPARTMENTS  */
function openDepartmentForm(dept) {
  const editing = Boolean(dept);
  openForm({
    title: editing ? `Edit ${dept.name}` : 'Add department', eyebrow: 'Departments',
    fields: [
      { name: 'name', label: 'Department name', required: true, value: dept?.name, wide: true },
      { name: 'description', label: 'Description', type: 'textarea', value: dept?.description, wide: true, sendEmpty: editing },
      ...(editing ? [{ name: 'is_active', label: 'Department is active', type: 'checkbox', value: dept.is_active }] : []),
    ],
    onSubmit: async values => {
      if (editing) await Api.put(`/departments/${dept.id}`, values); else await Api.post('/departments', values);
      reload();
      return editing ? 'Department updated' : 'Department added';
    },
  });
}

definePage('departments', {
  title: 'Departments', group: 'Care management', icon: '▣', roles: ['admin', 'receptionist', 'doctor', 'nurse'],
  render: () => renderList({
    id: 'departments',
    load: () => Api.get(`/departments${Session.isAdmin ? '?is_active=all' : ''}`),
    columns: [
      { label: 'ID', key: 'id' }, { label: 'Department', key: 'name' }, { label: 'Description', key: 'description' },
      { label: 'Status', render: r => badge(r.is_active ? 'active' : 'inactive') },
    ],
    rowActions: Session.isAdmin ? r => [{ label: 'Edit', onClick: () => openDepartmentForm(r) }] : undefined,
    buttons: Session.isAdmin ? [{ label: '＋ Add department', onClick: () => openDepartmentForm() }] : [],
    emptyHint: Session.isAdmin ? 'No departments yet. Add one, or run “flask --app run.py seed-demo-data”.' : 'No departments yet — ask an administrator.',
  }),
});

/* =====================================================================  DOCTORS  */
function openDoctorForm(doctor) {
  const editing = Boolean(doctor);
  const heading = text => ({ type: 'custom', id: `h-${text.length}`, html: `<h4 class="form-heading">${text}</h4>` });
  const common = [
    { name: 'department_id', label: 'Department', type: 'select', numeric: true, required: true, load: Loaders.departments, value: doctor?.department_id, emptyText: 'Add a department first' },
    { name: 'specialization', label: 'Specialization', required: true, value: doctor?.specialization, placeholder: 'e.g. Cardiologist' },
    { name: 'consultation_fee', label: 'Consultation fee (₹)', type: 'number', min: 0, value: doctor?.consultation_fee ?? 500 },
    { name: 'is_on_emergency_duty', label: 'On emergency duty', type: 'checkbox', value: doctor?.is_on_emergency_duty },
  ];
  const fields = editing ? common : [
    heading('Doctor login'),
    { name: 'user_id', label: 'Use an existing doctor login', type: 'select', numeric: true, load: Loaders.doctorAccountsWithoutProfile, emptyText: 'No unused doctor logins', hint: 'Leave empty to create a new login below.', wide: true },
    { name: 'full_name', label: 'New login: full name', placeholder: 'Dr. Full Name' },
    { name: 'username', label: 'New login: username' },
    { name: 'email', label: 'New login: email', type: 'email' },
    { name: 'phone', label: 'New login: phone', type: 'tel' },
    { name: 'password', label: 'New login: password', type: 'password', hint: 'At least 8 characters with a letter and a digit.', wide: true },
    heading('Doctor profile'),
    ...common,
  ];

  openForm({
    title: editing ? `Edit ${doctor.full_name}` : 'Add doctor', eyebrow: 'Doctors', fields, wide: true,
    submitLabel: editing ? 'Save changes' : 'Add doctor',
    onSubmit: async values => {
      const profile = { department_id: values.department_id, specialization: values.specialization, is_on_emergency_duty: values.is_on_emergency_duty };
      if (values.consultation_fee !== undefined) profile.consultation_fee = values.consultation_fee;
      if (editing) { await Api.put(`/doctors/${doctor.id}`, profile); reload(); return 'Doctor updated'; }

      let userId = values.user_id, created = false;
      if (!userId) {
        for (const key of ['full_name', 'username', 'email', 'password']) {
          if (!values[key]) throw new Error('Pick an existing doctor login, or fill in full name, username, email and password for a new one.');
        }
        const user = await Api.post('/users', { username: values.username, email: values.email, full_name: values.full_name, password: values.password, phone: values.phone, role: 'doctor' });
        userId = user.id; created = true;
      }
      try { await Api.post('/doctors', { user_id: userId, ...profile }); }
      catch (e) {
        throw new Error(created ? `${e.message}. The login “${values.username}” was created — choose it in “Use an existing doctor login” and save again.` : e.message);
      }
      reload();
      return 'Doctor added — now set the weekly timetable with “Schedule”.';
    },
  });
}

async function openSchedule(doctor) {
  const slots = await Api.get(`/doctors/${doctor.id}/schedule`);
  const table = slots.length
    ? `<div class="table-wrap"><table><thead><tr><th>Day</th><th>From</th><th>To</th><th>Slot length</th></tr></thead><tbody>${
      [...slots].sort((a, b) => a.day_of_week - b.day_of_week || a.start_time.localeCompare(b.start_time))
        .map(s => `<tr><td>${DAY_NAMES[s.day_of_week]}</td><td>${esc(s.start_time)}</td><td>${esc(s.end_time)}</td><td>${s.slot_minutes} min</td></tr>`).join('')}</tbody></table></div>`
    : '<p class="muted">No working hours added yet, so patients cannot book this doctor.</p>';
  const form = Session.isAdmin ? `
    <h3 class="section-title">Add working hours</h3>
    <form class="inline-form" id="schedule-form">
      <select name="day_of_week" required><option value="">Day…</option>${DAY_NAMES.map((d, i) => `<option value="${i}">${d}</option>`).join('')}</select>
      <input name="start_time" type="time" required value="09:00"><input name="end_time" type="time" required value="13:00">
      <input name="slot_minutes" type="number" min="5" max="120" value="15" title="Minutes per appointment">
      <button class="btn secondary" type="submit">Add</button></form>
    <p class="muted tiny">Tip: add the morning and the evening shift as two separate rows. Removing a row is not supported yet.</p>` : '';

  Dialog.open({
    title: `${doctor.full_name} — timetable`, eyebrow: doctor.department, body: table + form, wide: true,
    buttons: [{ label: 'Close', kind: 'primary' }],
    onOpen: root => {
      const f = $('#schedule-form', root);
      if (!f) return;
      f.addEventListener('submit', async e => {
        e.preventDefault();
        const d = Object.fromEntries(new FormData(f).entries());
        try {
          await Api.post(`/doctors/${doctor.id}/schedule`, { day_of_week: Number(d.day_of_week), start_time: d.start_time, end_time: d.end_time, slot_minutes: Number(d.slot_minutes) });
          toast('Working hours added');
          openSchedule(doctor);
        } catch (err) { Dialog.error(err.message); }
      });
    },
  });
}

definePage('doctors', {
  title: 'Doctors', group: 'Care management', icon: '⚕', roles: ['admin', 'receptionist', 'doctor', 'nurse'],
  render: async () => {
    const departments = await Loaders.departments().catch(() => []);
    return renderList({
      id: 'doctors',
      load: () => Api.get(`/doctors${Session.isAdmin ? '?is_active=all' : ''}`),
      filters: [{ name: 'department', label: 'All departments', options: departments.map(d => ({ value: d.label, label: d.label })), test: (r, v) => r.department === v }],
      columns: [
        { label: 'Doctor', key: 'full_name' }, { label: 'Department', key: 'department' }, { label: 'Specialization', key: 'specialization' },
        { label: 'Fee', key: 'consultation_fee', type: 'money' },
        { label: 'Emergency duty', key: 'is_on_emergency_duty', type: 'bool' },
        { label: 'Status', render: r => badge(r.is_active ? 'active' : 'inactive') },
      ],
      rowActions: r => [
        { label: 'Timetable', onClick: () => openSchedule(r) },
        ...(Session.isAdmin ? [
          { label: 'Edit', onClick: () => openDoctorForm(r) },
          { label: r.is_active ? 'Deactivate' : 'Activate', danger: r.is_active, confirm: r.is_active ? `Deactivate ${r.full_name}? They will no longer appear for new bookings.` : undefined,
            onClick: async () => { await Api.put(`/doctors/${r.id}`, { is_active: !r.is_active }); toast('Doctor updated'); reload(); } }] : []),
      ],
      buttons: Session.isAdmin ? [{ label: '＋ Add doctor', onClick: () => openDoctorForm() }] : [],
      emptyHint: Session.isAdmin ? 'No doctors yet. Add a department first, then use “Add doctor”.' : 'No doctors yet — ask an administrator.',
    });
  },
});

/* =====================================================================  APPOINTMENTS  */
function openBookingForm() {
  openForm({
    title: 'Book appointment', eyebrow: 'Appointments', wide: true, submitLabel: 'Book appointment',
    fields: [
      { name: 'patient_id', label: 'Patient', type: 'lookup', lookup: 'patients', required: true, numeric: true, wide: true },
      { name: 'doctor_id', label: 'Doctor', type: 'select', numeric: true, required: true, load: Loaders.doctors, emptyText: 'No doctors yet' },
      { name: 'appointment_date', label: 'Date', type: 'date', required: true, min: todayISO() },
      slotPickerField,
      { name: 'appointment_time', label: 'Time', type: 'time', required: true, hint: 'Click a free time above, or type one.' },
      { name: 'reason', label: 'Reason', required: true, placeholder: 'e.g. Fever for 3 days' },
      { name: 'notes', label: 'Notes', type: 'textarea', wide: true },
      { name: 'allow_waitlist', label: 'Put on the waiting list if this time is already taken', type: 'checkbox' },
    ],
    onOpen: form => attachSlotPicker(form),
    onSubmit: async values => {
      const result = await Api.post('/appointments', values);
      reload();
      return result.status === 'waitlisted' ? 'That time was taken — added to the waiting list.' : 'Appointment booked';
    },
  });
}

function openRescheduleForm(appt) {
  openForm({
    title: 'Reschedule appointment', eyebrow: `${appt.patient_name} · ${appt.doctor_name}`, submitLabel: 'Reschedule',
    fields: [
      { name: 'doctor_id', type: 'hidden', value: appt.doctor_id, skip: true },
      { name: 'appointment_date', label: 'New date', type: 'date', required: true, min: todayISO(), value: appt.appointment_date },
      slotPickerField,
      { name: 'appointment_time', label: 'New time', type: 'time', required: true, value: appt.appointment_time },
    ],
    onOpen: form => attachSlotPicker(form),
    onSubmit: async values => {
      await Api.put(`/appointments/${appt.id}`, { appointment_date: values.appointment_date, appointment_time: values.appointment_time });
      reload();
      return 'Appointment rescheduled';
    },
  });
}

definePage('appointments', {
  title: 'Appointments', group: 'Care management', icon: '▦', roles: ['admin', 'receptionist', 'doctor', 'nurse'],
  render: () => renderList({
    id: 'appointments',
    load: s => Api.get(`/appointments?per_page=15&page=${s.page}${s.filters.status ? `&status=${s.filters.status}` : ''}`),
    filters: [{ name: 'status', label: 'All statuses', server: true, options: ['scheduled', 'waitlisted', 'completed', 'cancelled', 'no_show'] }],
    columns: [
      { label: 'ID', key: 'id' }, { label: 'Patient', key: 'patient_name' }, { label: 'Doctor', key: 'doctor_name' },
      { label: 'Department', key: 'department' }, { label: 'Date', key: 'appointment_date', type: 'date' }, { label: 'Time', key: 'appointment_time' },
      { label: 'Status', key: 'status', type: 'status' }, { label: 'Reason', key: 'reason' },
    ],
    rowActions: r => {
      if (!hasRole('admin', 'receptionist', 'doctor')) return [];
      const act = (label, path, extra = {}) => ({ label, ...extra, onClick: async () => { await Api.post(`/appointments/${r.id}/${path}`); toast(`${label} done`); reload(); } });
      if (r.status === 'scheduled') return [act('Complete', 'complete'), { label: 'Reschedule', onClick: () => openRescheduleForm(r) }, act('No-show', 'no-show', { confirm: 'Mark this patient as a no-show?' }), act('Cancel', 'cancel', { danger: true, confirm: 'Cancel this appointment?' })];
      if (r.status === 'waitlisted') return [act('Promote', 'promote', { confirm: 'Move this booking from the waiting list into the schedule?' }), act('Cancel', 'cancel', { danger: true, confirm: 'Cancel this booking?' })];
      return [];
    },
    buttons: hasRole('admin', 'receptionist') ? [{ label: '＋ Book appointment', onClick: openBookingForm }] : [],
    emptyHint: 'No appointments found.',
  }),
});

/* =====================================================================  EMERGENCY & TRIAGE  */
function openTriageForm() {
  openForm({
    title: 'Record triage', eyebrow: 'Emergency', wide: true, submitLabel: 'Record triage',
    intro: 'Enter the vitals measured now. The system gives the case a priority automatically.',
    fields: [
      { name: 'patient_id', label: 'Patient', type: 'lookup', lookup: 'patients', required: true, numeric: true, wide: true },
      { name: 'blood_pressure_systolic', label: 'Blood pressure — top (systolic)', type: 'number', required: true, step: 1 },
      { name: 'blood_pressure_diastolic', label: 'Blood pressure — bottom (diastolic)', type: 'number', required: true, step: 1 },
      { name: 'heart_rate', label: 'Heart rate (beats/min)', type: 'number', required: true, step: 1 },
      { name: 'oxygen_level', label: 'Oxygen level SpO₂ (%)', type: 'number', required: true, step: 1, max: 100 },
      { name: 'temperature', label: 'Temperature (°F)', type: 'number', required: true, step: 0.1 },
      { name: 'symptoms', label: 'Symptoms', type: 'textarea', required: true, wide: true },
      { name: 'icu_required', label: 'ICU required', type: 'checkbox' },
      { name: 'isolation_required', label: 'Isolation required', type: 'checkbox' },
    ],
    onSubmit: async values => {
      const t = await Api.post('/triage', values);
      reload();
      return `Triage recorded — priority: ${titleCase(t.priority_level)}`;
    },
  });
}

function openAllocateBed(row) {
  openForm({
    title: 'Allocate a bed', eyebrow: `${row.patient_name} · ${titleCase(row.priority_level)} priority`, submitLabel: 'Find bed and admit',
    intro: 'The system picks the best free bed (ICU / isolation / gender rules) and admits the patient.',
    fields: [{ name: 'doctor_id', label: 'Treating doctor', type: 'select', numeric: true, required: true, load: Loaders.doctors, wide: true }],
    onSubmit: async values => {
      const result = await Api.post(`/triage/${row.id}/allocate-bed`, values);
      reload();
      return `Admitted to ${result.admission.ward_name} · bed ${result.admission.bed_number}`;
    },
  });
}

definePage('emergency', {
  title: 'Emergency & Triage', group: 'Care management', icon: '✚', roles: ['admin', 'doctor', 'nurse'],
  render: () => renderList({
    id: 'emergency',
    // /triage lists every case. (/triage/queue only holds patients still WAITING, so cases that already have a bed
    // would vanish from the screen and could never be moved on to "in treatment" or "resolved".)
    load: () => Api.get('/triage'),
    defaultFilters: { status: 'active' },
    filters: [{ name: 'status', label: 'All cases', options: [{ value: 'active', label: 'Active cases' }, 'waiting', 'bed_assigned', 'in_treatment', 'resolved'],
      test: (r, v) => v === 'active' ? r.status !== 'resolved' : r.status === v }],
    columns: [
      { label: 'Case', key: 'id' }, { label: 'Patient', key: 'patient_name' },
      { label: 'Priority', key: 'priority_level', type: 'status' }, { label: 'Score', key: 'priority_score' },
      { label: 'Vitals', render: r => r.vitals ? `BP ${esc(r.vitals.blood_pressure)} · HR ${esc(r.vitals.heart_rate)} · SpO₂ ${esc(r.vitals.oxygen_level)}% · ${esc(r.vitals.temperature)}°F` : '—' },
      { label: 'Symptoms', render: r => esc((r.symptoms || '').slice(0, 60)) },
      { label: 'Status', key: 'status', type: 'status' }, { label: 'Reported', key: 'recorded_at', type: 'datetime' },
    ],
    rowActions: r => {
      if (!hasRole('admin', 'doctor', 'nurse')) return [];
      const setStatus = (label, status) => ({ label, onClick: async () => { await Api.put(`/triage/${r.id}/status`, { status }); toast('Status updated'); reload(); } });
      const resolve = { label: 'Resolve', confirm: 'Mark this emergency case as resolved?', onClick: async () => { await Api.post(`/triage/${r.id}/resolve`); toast('Case resolved'); reload(); } };
      if (r.status === 'waiting') return [{ label: 'Allocate bed', onClick: () => openAllocateBed(r) }, setStatus('Start treatment', 'in_treatment'), resolve];
      if (r.status === 'bed_assigned') return [setStatus('Start treatment', 'in_treatment'), resolve];
      if (r.status === 'in_treatment') return [resolve];
      return [];
    },
    buttons: hasRole('admin', 'nurse') ? [{ label: '＋ Record triage', onClick: openTriageForm }] : [],
    emptyHint: 'No emergency cases right now.',
  }),
});

/* =====================================================================  WARDS & BEDS  */
function openWardForm() {
  openForm({
    title: 'Add ward', eyebrow: 'Wards & beds',
    fields: [
      { name: 'name', label: 'Ward name', required: true, wide: true, placeholder: 'e.g. General Ward (Male)' },
      { name: 'ward_type', label: 'Ward type', type: 'select', required: true, options: ['general', 'icu', 'isolation', 'maternity', 'pediatric'] },
      { name: 'gender_restriction', label: 'Only for', type: 'select', options: ['male', 'female'], hint: 'Leave empty for a mixed ward.' },
      { name: 'daily_charge', label: 'Charge per day (₹)', type: 'number', min: 0, value: 1000 },
    ],
    onSubmit: async values => { await Api.post('/wards', values); reload(); return 'Ward added'; },
  });
}

function openBedForm(ward) {
  openForm({
    title: 'Add bed', eyebrow: 'Wards & beds',
    fields: [
      { name: 'ward_id', label: 'Ward', type: 'select', numeric: true, required: true, load: Loaders.wards, value: ward?.id, wide: true, emptyText: 'Add a ward first' },
      { name: 'bed_number', label: 'Bed number', required: true, placeholder: 'e.g. GM-07' },
      { name: 'bed_type', label: 'Bed type', type: 'select', required: true, options: ['general', 'icu', 'isolation'], value: ward ? (ward.ward_type === 'icu' ? 'icu' : ward.ward_type === 'isolation' ? 'isolation' : 'general') : '' },
    ],
    onSubmit: async values => {
      const { ward_id, ...bed } = values;
      await Api.post(`/wards/${ward_id}/beds`, bed);
      reload();
      return 'Bed added';
    },
  });
}

definePage('beds', {
  title: 'Wards & Beds', group: 'Resources', icon: '▤', roles: ['admin', 'receptionist', 'doctor', 'nurse'],
  render: async () => {
    $('#page-content').innerHTML = '<h3 class="section-title first">Wards</h3><div id="wards-host"></div><h3 class="section-title">Beds</h3><div id="beds-host"></div>';
    const wards = await Api.get('/wards').catch(() => []);
    await renderList({
      id: 'wards', host: '#wards-host',
      load: () => Api.get('/wards'),
      columns: [
        { label: 'Ward', key: 'name' }, { label: 'Type', key: 'ward_type', type: 'status' },
        { label: 'Only for', render: r => esc(r.gender_restriction ? titleCase(r.gender_restriction) : 'Everyone') },
        { label: 'Charge / day', key: 'daily_charge', type: 'money' },
        { label: 'Free beds', render: r => `${r.available_beds} of ${r.total_beds}` },
      ],
      rowActions: Session.isAdmin ? r => [{ label: 'Add bed', onClick: () => openBedForm(r) }] : undefined,
      buttons: Session.isAdmin ? [{ label: '＋ Add ward', onClick: openWardForm }, { label: '＋ Add bed', kind: 'secondary', onClick: () => openBedForm() }] : [],
      emptyHint: Session.isAdmin ? 'No wards yet. Add a ward, then add beds to it (or run “flask --app run.py seed-demo-data”).' : 'No wards yet — ask an administrator.',
    });
    await renderList({
      id: 'beds', host: '#beds-host',
      load: () => Api.get('/beds'),
      filters: [
        { name: 'ward', label: 'All wards', options: wards.map(w => ({ value: w.name, label: w.name })), test: (r, v) => r.ward_name === v },
        { name: 'status', label: 'All statuses', options: ['available', 'occupied', 'maintenance'], test: (r, v) => r.status === v },
      ],
      columns: [
        { label: 'Bed', key: 'bed_number' }, { label: 'Ward', key: 'ward_name' }, { label: 'Type', key: 'bed_type', type: 'status' },
        { label: 'Status', key: 'status', type: 'status' },
        { label: 'Only for', render: r => esc(r.gender_restriction ? titleCase(r.gender_restriction) : 'Everyone') },
      ],
      rowActions: r => {
        if (!hasRole('admin', 'nurse') || r.status === 'occupied') return [];
        const next = r.status === 'available' ? 'maintenance' : 'available';
        return [{ label: next === 'maintenance' ? 'Mark for maintenance' : 'Make available', onClick: async () => { await Api.put(`/beds/${r.id}`, { status: next }); toast('Bed updated'); reload(); } }];
      },
      emptyHint: 'No beds yet.',
    });
  },
});

/* =====================================================================  ADMISSIONS  */
function openAdmitForm() {
  openForm({
    title: 'Admit patient', eyebrow: 'Admissions', wide: true, submitLabel: 'Admit patient',
    fields: [
      { name: 'patient_id', label: 'Patient', type: 'lookup', lookup: 'patients', required: true, numeric: true, wide: true },
      { name: 'doctor_id', label: 'Doctor', type: 'select', numeric: true, required: true, load: Loaders.doctors, emptyText: 'No doctors yet' },
      { name: 'bed_id', label: 'Free bed', type: 'select', numeric: true, required: true, load: Loaders.availableBeds, emptyText: 'No free beds' },
      { name: 'reason', label: 'Reason for admission', required: true, wide: true },
    ],
    onSubmit: async values => { await Api.post('/admissions', values); reload(); return 'Patient admitted'; },
  });
}

function openDischargeSummaryForm(adm) {
  openForm({
    title: 'Discharge with summary', eyebrow: `${adm.patient_name} · ${adm.ward_name} ${adm.bed_number}`, wide: true, submitLabel: 'Discharge patient',
    intro: 'This frees the bed and creates the discharge summary (PDF).',
    fields: [
      { name: 'diagnosis', label: 'Diagnosis', required: true, wide: true },
      { name: 'treatment_summary', label: 'Treatment summary', type: 'textarea', rows: 4, required: true, wide: true },
      { name: 'doctor_instructions', label: 'Instructions for the patient', type: 'textarea', wide: true },
      { name: 'follow_up_date', label: 'Follow-up date', type: 'date', min: todayISO() },
    ],
    onSubmit: async values => { await Api.post(`/discharge/${adm.id}`, values); reload(); return 'Patient discharged'; },
  });
}

definePage('admissions', {
  title: 'Admissions', group: 'Resources', icon: '⌂', roles: ['admin', 'receptionist', 'doctor', 'nurse'],
  render: () => renderList({
    id: 'admissions',
    load: s => Api.get(`/admissions?per_page=15&page=${s.page}${s.filters.status ? `&status=${s.filters.status}` : ''}`),
    filters: [{ name: 'status', label: 'All admissions', server: true, options: ['admitted', 'discharged'] }],
    columns: [
      { label: 'ID', key: 'id' }, { label: 'Patient', key: 'patient_name' },
      { label: 'Bed', render: r => `${esc(r.ward_name)} · ${esc(r.bed_number)}` }, { label: 'Doctor', key: 'doctor_name' },
      { label: 'Reason', key: 'reason' }, { label: 'Status', key: 'status', type: 'status' },
      { label: 'Admitted', key: 'admission_date', type: 'datetime' }, { label: 'Discharged', key: 'discharge_date', type: 'datetime' },
    ],
    rowActions: r => {
      const out = [];
      if (r.status === 'admitted') {
        if (hasRole('admin', 'doctor')) out.push({ label: 'Discharge with summary', onClick: () => openDischargeSummaryForm(r) });
        if (hasRole('admin', 'receptionist', 'nurse')) out.push({ label: 'Discharge (bed only)', danger: true, confirm: 'Discharge this patient without a summary? The bed will be freed.', onClick: async () => { await Api.post(`/admissions/${r.id}/discharge`); toast('Patient discharged'); reload(); } });
      } else if (hasRole('admin', 'doctor', 'nurse', 'receptionist')) {
        out.push({ label: 'Summary PDF', onClick: () => Api.download(`/discharge/${r.id}/pdf`, `discharge_${r.id}.pdf`) });
      }
      return out;
    },
    buttons: hasRole('admin', 'receptionist') ? [{ label: '＋ Admit patient', onClick: openAdmitForm }] : [],
    emptyHint: 'No admissions yet.',
  }),
});
