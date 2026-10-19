// Local Database & Initial State Store
const initialHospitalData = {
  kpis: {
    totalPatients: 1420,
    todayAppointments: 48,
    availableBeds: 24,
    occupiedBeds: 76,
    emergencyPatients: 7,
    pendingLabTests: 18,
    lowStockMedicines: 5,
    todayRevenue: 284500
  },
  patients: [
    { id: "P-1001", name: "Rahul Sharma", age: 34, gender: "Male", phone: "9876543210", dept: "Cardiology", doctor: "Dr. A. Verma", status: "Admitted", date: "2026-03-28" },
    { id: "P-1002", name: "Pooja Patel", age: 29, gender: "Female", phone: "9812345678", dept: "Neurology", doctor: "Dr. S. Mehta", status: "Outpatient", date: "2026-03-29" },
    { id: "P-1003", name: "Amitabh Sen", age: 62, gender: "Male", phone: "9765432180", dept: "Orthopedics", doctor: "Dr. K. Rao", status: "Discharged", date: "2026-03-25" },
    { id: "P-1004", name: "Sunita Devi", age: 45, gender: "Female", phone: "9123456789", dept: "General Medicine", doctor: "Dr. R. Iyer", status: "In Consultation", date: "2026-03-30" }
  ],
  emergency: [
    { id: "EM-501", patient: "Vikas Joshi", triage: "Critical", vitals: "BP: 85/50, SpO2: 88%", doctor: "Dr. A. Verma", bed: "ICU-02", arrival: "10 mins ago" },
    { id: "EM-502", patient: "Sneha Roy", triage: "High", vitals: "BP: 145/95, SpO2: 94%", doctor: "Dr. R. Iyer", bed: "ER-04", arrival: "25 mins ago" },
    { id: "EM-503", patient: "Mohan Lal", triage: "Medium", vitals: "BP: 120/80, SpO2: 98%", doctor: "Dr. S. Mehta", bed: "ER-09", arrival: "40 mins ago" }
  ],
  beds: [
    { id: "B-101", ward: "General Ward", type: "Standard", status: "occupied" },
    { id: "B-102", ward: "General Ward", type: "Standard", status: "available" },
    { id: "B-201", ward: "ICU", type: "Ventilator", status: "occupied" },
    { id: "B-202", ward: "ICU", type: "Standard", status: "available" },
    { id: "B-301", ward: "Emergency", type: "Trauma Bed", status: "reserved" },
    { id: "B-302", ward: "Emergency", type: "Standard", status: "maintenance" }
  ]
};

// Check if data already exists in browser localStorage, else initialize
if (!localStorage.getItem("hospitalData")) {
  localStorage.setItem("hospitalData", JSON.stringify(initialHospitalData));
}

const Store = {
  getData() {
    return JSON.parse(localStorage.getItem("hospitalData")) || initialHospitalData;
  },
  saveData(data) {
    localStorage.setItem("hospitalData", JSON.stringify(data));
  }
};