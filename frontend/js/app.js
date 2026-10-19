// Application Main Controller
document.addEventListener("DOMContentLoaded", async () => {
  // Real-time Clock
  setInterval(() => {
    const clockEl = document.getElementById("live-clock");
    if (clockEl) {
      clockEl.innerText = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }, 1000);

  // Load Initial Data
  await loadDashboardKPIs();
  initDashboardCharts();
  await loadPatientsTable();
  await loadEmergencyQueue();
  setupRoleSwitcher();
  setupPatientForm();
});

// 1. KPI Cards Loader
async function loadDashboardKPIs() {
  const res = await ApiService.get('/kpis');
  if (!res.success) return;
  const kpis = res.data;

  document.getElementById('kpi-total-patients').innerText = kpis.totalPatients.toLocaleString();
  document.getElementById('kpi-today-appts').innerText = kpis.todayAppointments;
  document.getElementById('kpi-available-beds').innerText = kpis.availableBeds;
  document.getElementById('kpi-occupied-beds').innerText = kpis.occupiedBeds;
  document.getElementById('kpi-emergency').innerText = kpis.emergencyPatients;
  document.getElementById('kpi-lab-tests').innerText = kpis.pendingLabTests;
  document.getElementById('kpi-low-stock').innerText = kpis.lowStockMedicines;
  document.getElementById('kpi-revenue').innerText = '₹' + kpis.todayRevenue.toLocaleString();
}

// 2. Chart.js Initializer
function initDashboardCharts() {
  // Patient Registration Trend (Line Chart)
  const ctxTrend = document.getElementById('chart-patient-trend');
  if (ctxTrend) {
    new Chart(ctxTrend, {
      type: 'line',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
          label: 'Registrations',
          data: [65, 78, 90, 81, 105, 120, 95],
          borderColor: '#0d6efd',
          backgroundColor: 'rgba(13, 110, 253, 0.08)',
          fill: true,
          tension: 0.35
        }]
      },
      options: { responsive: true, plugins: { legend: { display: false } } }
    });
  }

  // Bed Occupancy (Doughnut Chart)
  const ctxBeds = document.getElementById('chart-bed-status');
  if (ctxBeds) {
    new Chart(ctxBeds, {
      type: 'doughnut',
      data: {
        labels: ['Occupied', 'Available', 'Reserved', 'Maintenance'],
        datasets: [{
          data: [76, 24, 8, 4],
          backgroundColor: ['#ef4444', '#22c55e', '#eab308', '#64748b']
        }]
      },
      options: { responsive: true, cutout: '70%' }
    });
  }
}

// 3. Patients Table Loader
async function loadPatientsTable() {
  const res = await ApiService.get('/patients');
  if (!res.success) return;
  const tbody = document.getElementById('patients-table-body');
  if (!tbody) return;

  tbody.innerHTML = res.data.map(p => `
    <tr>
      <td><span class="badge bg-light text-dark border">${p.id}</span></td>
      <td class="fw-semibold text-primary">${p.name}</td>
      <td>${p.gender}, ${p.age}y</td>
      <td>${p.phone}</td>
      <td>${p.dept}</td>
      <td>${p.doctor}</td>
      <td><span class="badge ${p.status === 'Admitted' ? 'bg-danger' : 'bg-success'}">${p.status}</span></td>
      <td>
        <button class="btn btn-sm btn-outline-primary" onclick="alert('Viewing patient details for: ${p.name}')">
          <i class="bi bi-eye"></i> View
        </button>
      </td>
    </tr>
  `).join('');
}

// 4. Emergency Queue Loader
async function loadEmergencyQueue() {
  const res = await ApiService.get('/emergency');
  if (!res.success) return;
  const tbody = document.getElementById('emergency-table-body');
  if (!tbody) return;

  tbody.innerHTML = res.data.map(e => `
    <tr>
      <td><span class="badge badge-${e.triage.toLowerCase()}">${e.triage}</span></td>
      <td class="fw-bold">${e.patient}</td>
      <td><code>${e.vitals}</code></td>
      <td>${e.doctor}</td>
      <td><span class="badge bg-secondary">${e.bed}</span></td>
      <td class="text-muted small">${e.arrival}</td>
    </tr>
  `).join('');
}

// 5. Patient Intake Form (Modal)
function setupPatientForm() {
  const form = document.getElementById('add-patient-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById('pt-name').value,
      age: document.getElementById('pt-age').value,
      gender: document.getElementById('pt-gender').value,
      phone: document.getElementById('pt-phone').value,
      dept: document.getElementById('pt-dept').value,
      doctor: document.getElementById('pt-doctor').value
    };

    const res = await ApiService.post('/patients', payload);
    if (res.success) {
      bootstrap.Modal.getInstance(document.getElementById('modalAddPatient')).hide();
      form.reset();
      await loadPatientsTable();
      await loadDashboardKPIs();
      alert(`Patient registered successfully! Assigned ID: ${res.data.id}`);
    }
  });
}

// 6. Role Switcher Logic (RBAC Preview)
function setupRoleSwitcher() {
  const roleSelect = document.getElementById('role-select');
  if (!roleSelect) return;

  roleSelect.addEventListener('change', (e) => {
    const role = e.target.value;
    const badge = document.getElementById('current-role-badge');
    if (badge) badge.innerText = role;
    alert(`Switched role to: ${role}. Access permissions re-scoped.`);
  });
}