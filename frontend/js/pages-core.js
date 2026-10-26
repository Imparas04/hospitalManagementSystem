/* pages-core.js — who is logged in, which pages exist, and the dropdown lists shared by many forms. */

/* ---------- the logged-in person ---------- */
const Session = {
  user: null,
  get role() { return (this.user && (this.user.role?.name || this.user.role)) || ''; },
  get isAdmin() { return this.role === 'admin'; },
};
// hasRole('doctor', 'nurse') -> true if the logged-in person has one of these roles.
// (The buttons you see depend on this, but the SERVER always re-checks permissions on every request.)
const hasRole = (...roles) => roles.includes(Session.role);

const ROLES = ['admin', 'receptionist', 'doctor', 'nurse', 'lab_technician', 'pharmacist', 'billing_staff'];
const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/* ---------- page registry ----------
   Each page: {title, group, icon, roles: [who sees it in the menu], render: async () => {...}}  */
const Pages = {};
function definePage(id, config) { Pages[id] = config; }

/* ---------- dropdown lists loaded from the server (used inside forms) ---------- */
const Loaders = {
  doctors: async () => (await Api.get('/doctors')).map(d => ({ value: d.id, label: `${d.full_name} — ${d.specialization}` })),
  departments: async () => (await Api.get('/departments')).map(d => ({ value: d.id, label: d.name })),
  wards: async () => (await Api.get('/wards')).map(w => ({ value: w.id, label: `${w.name} (${w.available_beds}/${w.total_beds} free)` })),
  availableBeds: async () => (await Api.get('/beds?status=available')).map(b => ({ value: b.id, label: `${b.ward_name} · ${b.bed_number} (${b.bed_type})` })),
  labTests: async () => (await Api.get('/lab/tests')).map(t => ({ value: t.id, label: `${t.name} (${t.code}) — ${money(t.price)}` })),
  medicines: async () => (await Api.get('/pharmacy/medicines')).map(m => ({ value: m.id, label: `${m.name} — ${m.total_available} in stock` })),
  // Doctor LOGIN accounts that do not have a doctor profile yet (so they can be turned into doctors).
  doctorAccountsWithoutProfile: async () => {
    const [users, doctors] = await Promise.all([Api.get('/users?per_page=100&role=doctor'), Api.get('/doctors?is_active=all')]);
    const taken = new Set(doctors.map(d => d.user_id));
    return (users.items || []).filter(u => u.role === 'doctor' && u.is_active && !taken.has(u.id))
      .map(u => ({ value: u.id, label: `${u.full_name} (${u.username})` }));
  },
};

/* ---------- appointment time picker: shows the doctor's free slots as clickable chips ---------- */
function attachSlotPicker(form) {
  const doctor = form.elements.doctor_id, date = form.elements.appointment_date, time = form.elements.appointment_time;
  const chips = $('#slot-chips', form);
  const refresh = async () => {
    if (!doctor.value || !date.value) { chips.innerHTML = '<small class="muted">Choose a doctor and a date to see the free times.</small>'; return; }
    chips.innerHTML = '<small class="muted">Checking free times…</small>';
    try {
      const data = await Api.get(`/doctors/${doctor.value}/availability?date=${date.value}`);
      chips.innerHTML = data.slots.length
        ? data.slots.map(t => `<button type="button" class="chip" data-time="${t}">${t}</button>`).join('')
        : '<small class="muted">No free times on this day (the doctor may not work that day, or it is fully booked).</small>';
      $$('.chip', chips).forEach(chip => chip.onclick = () => {
        time.value = chip.dataset.time;
        $$('.chip', chips).forEach(c => c.classList.toggle('active', c === chip));
      });
    } catch (e) { chips.innerHTML = `<small class="muted">${esc(e.message)}</small>`; }
  };
  doctor.addEventListener('change', refresh);
  date.addEventListener('change', refresh);
  refresh();
}
const slotPickerField = { type: 'custom', id: 'slot-chips-box', html: '<span class="field-label">Free times</span><div class="chips" id="slot-chips"></div>' };
