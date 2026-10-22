import pytest

from app.utils.timeutils import local_today

ROLES = ["admin", "receptionist", "doctor", "nurse", "lab_technician", "pharmacist", "billing_staff"]

ROLE_KEYS = {
    "admin": {"total_patients", "today_appointments", "available_beds", "occupied_beds", "emergency_patients",
              "pending_lab_tests", "low_stock_medicines", "today_revenue"},
    "receptionist": {"today_appointments", "waiting_list", "patients_registered_today", "current_admissions", "available_beds"},
    "doctor": {"my_appointments_today", "my_upcoming_appointments", "lab_results_to_review", "my_admitted_patients", "emergency_queue_waiting"},
    "nurse": {"emergency_waiting", "critical_waiting", "admitted_patients", "available_beds", "occupied_beds", "beds_in_maintenance"},
    "lab_technician": {"pending_tests", "awaiting_sample", "in_processing", "results_entered_today", "abnormal_today"},
    "pharmacist": {"low_stock_medicines", "expiring_soon_batches", "expired_batches_with_stock", "pending_prescriptions"},
    "billing_staff": {"today_revenue", "outstanding_amount", "unpaid_bills", "bills_generated_today", "payments_today"},
}

CRITICAL = {"blood_pressure_systolic": 200, "blood_pressure_diastolic": 110, "heart_rate": 150, "oxygen_level": 85, "temperature": 103.0}


def _stats(client, auth_header, role):
    return client.get("/api/dashboard", headers=auth_header(client, role)).get_json()["data"]["stats"]


def _book_today(client, auth_header, doctor_id, patient_id):
    client.post(f"/api/doctors/{doctor_id}/schedule", headers=auth_header(client, "admin"),
                json={"day_of_week": local_today().weekday(), "start_time": "09:00", "end_time": "10:00"})
    return client.post("/api/appointments", headers=auth_header(client, "receptionist"), json={
        "patient_id": patient_id, "doctor_id": doctor_id, "appointment_date": local_today().isoformat(),
        "appointment_time": "09:00", "reason": "Fever checkup"}).get_json()["data"]


def _bill_and_pay(client, auth_header, patient_id, amount=500, pay=500):
    h = auth_header(client, "billing_staff")
    bill = client.post("/api/bills", headers=h, json={"patient_id": patient_id, "tax_percent": 0, "other_services": [
        {"description": "Consumables", "unit_price": amount}]}).get_json()["data"]
    if pay:
        client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": pay, "method": "cash"})
    return bill


# ------------------------------------------------------------- shape and access --

@pytest.mark.parametrize("role", ROLES)
def test_each_role_gets_its_own_dashboard(client, auth_header, role):
    data = client.get("/api/dashboard", headers=auth_header(client, role)).get_json()["data"]
    assert data["role"] == role and data["date"] == local_today().isoformat()
    assert set(data["stats"]) == ROLE_KEYS[role]                       # exactly its own widgets, nobody else's
    assert [c["key"] for c in data["cards"]] == list(data["stats"])
    assert all({"key", "label", "value", "format"} <= set(c) for c in data["cards"])


def test_dashboards_are_different_per_role(client, auth_header):
    keysets = {role: frozenset(_stats(client, auth_header, role)) for role in ROLES}
    assert len(set(keysets.values())) == len(ROLES)


def test_dashboard_needs_a_token(client):
    assert client.get("/api/dashboard").status_code == 401


def test_empty_hospital_shows_zeros(client, auth_header):
    stats = _stats(client, auth_header, "admin")
    assert all(v == 0 for v in stats.values())


# ---------------------------------------------------------------- admin cards --

def test_admin_cards_count_real_data(client, auth_header, doctor_setup, patient_id, ward_and_bed, lab_test_type):
    doctor_id = doctor_setup["doctor"]["id"]
    rec, nurse, doc = auth_header(client, "receptionist"), auth_header(client, "nurse"), auth_header(client, "doctor")
    _book_today(client, auth_header, doctor_id, patient_id)
    client.post("/api/admissions", headers=rec, json={"patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
                                                      "doctor_id": doctor_id, "reason": "Observation"})
    client.post("/api/triage", headers=nurse, json={"patient_id": patient_id, "symptoms": "Chest pain", **CRITICAL})
    client.post("/api/lab/orders", headers=doc, json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]})
    client.post("/api/pharmacy/medicines", headers=auth_header(client, "admin"),
                json={"name": "Cetirizine", "unit": "tablet", "reorder_level": 50})
    _bill_and_pay(client, auth_header, patient_id, amount=750, pay=750)

    s = _stats(client, auth_header, "admin")
    assert s["total_patients"] == 1 and s["today_appointments"] == 1
    assert s["occupied_beds"] == 1 and s["available_beds"] == 0
    assert s["emergency_patients"] == 1 and s["pending_lab_tests"] == 1
    assert s["low_stock_medicines"] == 1 and s["today_revenue"] == 750.0


def test_cancelled_appointment_is_not_counted_today(client, auth_header, doctor_setup, patient_id):
    appt = _book_today(client, auth_header, doctor_setup["doctor"]["id"], patient_id)
    assert _stats(client, auth_header, "admin")["today_appointments"] == 1
    client.post(f"/api/appointments/{appt['id']}/cancel", headers=auth_header(client, "receptionist"))
    data = client.get("/api/dashboard", headers=auth_header(client, "admin")).get_json()["data"]
    assert data["stats"]["today_appointments"] == 0
    assert data["today_appointments_by_status"]["cancelled"] == 1


def test_deactivated_patients_are_not_counted(client, auth_header, patient_id):
    client.delete(f"/api/patients/{patient_id}", headers=auth_header(client, "receptionist"))
    assert _stats(client, auth_header, "admin")["total_patients"] == 0


def test_resolved_emergencies_leave_the_active_count(client, auth_header, patient_id):
    nurse = auth_header(client, "nurse")
    rec = client.post("/api/triage", headers=nurse, json={"patient_id": patient_id, "symptoms": "Pain", **CRITICAL}).get_json()["data"]
    assert _stats(client, auth_header, "admin")["emergency_patients"] == 1
    client.post(f"/api/triage/{rec['id']}/resolve", headers=nurse)
    assert _stats(client, auth_header, "admin")["emergency_patients"] == 0


def test_today_revenue_ignores_other_days(client, auth_header, patient_id):
    from datetime import timedelta
    from app.extensions import db
    from app.models.billing import Payment
    _bill_and_pay(client, auth_header, patient_id, amount=900, pay=900)
    pay = Payment.query.first()
    pay.paid_at = pay.paid_at - timedelta(days=3)
    db.session.commit()
    assert _stats(client, auth_header, "admin")["today_revenue"] == 0


def test_revenue_uses_the_hospital_timezone(app, client, auth_header, patient_id):
    """A payment at 01:30 IST belongs to the NEW Indian day even though UTC still says yesterday."""
    from datetime import date, datetime
    from app.extensions import db
    from app.models.billing import Payment
    from app.services import stats_service
    from app.utils.timeutils import day_bounds_utc
    _bill_and_pay(client, auth_header, patient_id, amount=300, pay=300)
    pay = Payment.query.first()
    pay.paid_at = datetime(2026, 10, 10, 20, 0)          # = 2026-10-11 01:30 IST
    db.session.commit()
    app.config["HOSPITAL_TIMEZONE"] = "Asia/Kolkata"
    assert float(stats_service._revenue_between(*day_bounds_utc(date(2026, 10, 11)))) == 300.0
    assert float(stats_service._revenue_between(*day_bounds_utc(date(2026, 10, 10)))) == 0.0


# ------------------------------------------------------------------ role cards --

def test_receptionist_cards(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    doctor_id = doctor_setup["doctor"]["id"]
    rec = auth_header(client, "receptionist")
    _book_today(client, auth_header, doctor_id, patient_id)
    _book_today(client, auth_header, doctor_id, patient_id)           # same slot -> waiting list
    client.post("/api/admissions", headers=rec, json={"patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
                                                      "doctor_id": doctor_id, "reason": "Observation"})
    s = _stats(client, auth_header, "receptionist")
    assert s["today_appointments"] == 2 and s["waiting_list"] == 1 and s["patients_registered_today"] == 1
    assert s["current_admissions"] == 1 and s["available_beds"] == 0


def test_doctor_cards_are_personal(client, auth_header, doctor_setup, patient_id, lab_test_type):
    doc, lab = auth_header(client, "doctor"), auth_header(client, "lab_technician")
    doctor_id = doctor_setup["doctor"]["id"]
    _book_today(client, auth_header, doctor_id, patient_id)
    order = client.post("/api/lab/orders", headers=doc, json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"]
    assert _stats(client, auth_header, "doctor")["lab_results_to_review"] == 0
    client.post(f"/api/lab/orders/{order['id']}/result", headers=lab, json={"result_value": "Normal"})
    s = _stats(client, auth_header, "doctor")
    assert s["my_appointments_today"] == 1 and s["lab_results_to_review"] == 1
    client.post(f"/api/lab/orders/{order['id']}/review", headers=doc, json={})
    assert _stats(client, auth_header, "doctor")["lab_results_to_review"] == 0


def test_doctor_without_profile_gets_zeros_and_a_note(client, auth_header):
    data = client.get("/api/dashboard", headers=auth_header(client, "doctor")).get_json()["data"]
    assert all(v == 0 for v in data["stats"].values()) and "No doctor profile" in data["note"]


def test_doctor_sees_only_their_own_patients(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    """An admission handled by ANOTHER doctor must not appear on this doctor's dashboard."""
    admin = auth_header(client, "admin")
    client.post("/api/users", headers=admin, json={"username": "doc2", "email": "doc2@test.com", "password": "Secret123",
                                                    "full_name": "Other Doctor", "role": "doctor"})
    uid = client.get("/api/users?q=doc2", headers=admin).get_json()["data"]["items"][0]["id"]
    other = client.post("/api/doctors", headers=admin, json={"user_id": uid, "department_id": doctor_setup["department"]["id"],
                                                             "specialization": "ENT"}).get_json()["data"]
    client.post("/api/admissions", headers=auth_header(client, "receptionist"), json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"], "doctor_id": other["id"], "reason": "Observation"})
    assert _stats(client, auth_header, "doctor")["my_admitted_patients"] == 0
    assert _stats(client, auth_header, "nurse")["admitted_patients"] == 1


def test_nurse_cards(client, auth_header, patient_id, ward_and_bed):
    h = auth_header(client, "nurse")
    client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Chest pain", **CRITICAL})
    client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Cut", "blood_pressure_systolic": 120,
                                                "blood_pressure_diastolic": 80, "heart_rate": 75, "oxygen_level": 98, "temperature": 98.6})
    client.put(f"/api/beds/{ward_and_bed['bed']['id']}", headers=h, json={"status": "maintenance"})
    s = _stats(client, auth_header, "nurse")
    assert s["emergency_waiting"] == 2 and s["critical_waiting"] == 1
    assert s["beds_in_maintenance"] == 1 and s["available_beds"] == 0


def test_lab_technician_cards(client, auth_header, doctor_setup, patient_id, lab_test_type):
    doc, lab = auth_header(client, "doctor"), auth_header(client, "lab_technician")
    orders = [client.post("/api/lab/orders", headers=doc, json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"] for _ in range(3)]
    client.put(f"/api/lab/orders/{orders[0]['id']}/status", headers=lab, json={"status": "sample_collected"})
    client.post(f"/api/lab/orders/{orders[1]['id']}/result", headers=lab, json={"result_value": "High", "is_abnormal": True})
    s = _stats(client, auth_header, "lab_technician")
    assert s["pending_tests"] == 2 and s["awaiting_sample"] == 1 and s["in_processing"] == 1
    assert s["results_entered_today"] == 1 and s["abnormal_today"] == 1


def test_pharmacist_cards(client, auth_header, doctor_setup, patient_id):
    from datetime import timedelta
    from app.extensions import db
    from app.models.pharmacy import MedicineBatch
    admin, doc = auth_header(client, "admin"), auth_header(client, "doctor")
    med = client.post("/api/pharmacy/medicines", headers=admin, json={"name": "Amoxicillin", "unit": "tablet", "reorder_level": 5}).get_json()["data"]
    soon = (local_today() + timedelta(days=10)).isoformat()
    client.post(f"/api/pharmacy/medicines/{med['id']}/batches", headers=admin, json={"batch_number": "SOON", "expiry_date": soon, "purchase_quantity": 100})
    client.post(f"/api/pharmacy/medicines/{med['id']}/batches", headers=admin, json={"batch_number": "OLD", "expiry_date": "2028-01-01", "purchase_quantity": 100})
    MedicineBatch.query.filter_by(batch_number="OLD").first().expiry_date = local_today() - timedelta(days=1)
    db.session.commit()
    client.post("/api/prescriptions", headers=doc, json={"patient_id": patient_id, "items": [{"medicine_id": med["id"], "dosage": "x", "quantity": 3}]})
    s = _stats(client, auth_header, "pharmacist")
    assert s["expiring_soon_batches"] == 1 and s["expired_batches_with_stock"] == 1 and s["pending_prescriptions"] == 1
    assert s["low_stock_medicines"] == 0          # 100 usable units >= reorder level 5


def test_billing_cards(client, auth_header, patient_id):
    _bill_and_pay(client, auth_header, patient_id, amount=1000, pay=400)
    s = _stats(client, auth_header, "billing_staff")
    assert s["today_revenue"] == 400.0 and s["outstanding_amount"] == 600.0
    assert s["unpaid_bills"] == 1 and s["bills_generated_today"] == 1 and s["payments_today"] == 1


# ============================================================ CHART ANALYTICS ==

CHART_ACCESS = {
    "patient-registrations": {"admin", "receptionist"},
    "department-patients": {"admin", "receptionist", "doctor"},
    "bed-occupancy": {"admin", "receptionist", "nurse"},
    "emergency-cases": {"admin", "nurse", "doctor"},
    "monthly-revenue": {"admin", "billing_staff"},
    "lab-statistics": {"admin", "lab_technician", "doctor"},
    "medicine-consumption": {"admin", "pharmacist"},
}


@pytest.mark.parametrize("chart,role", [(c, r) for c in CHART_ACCESS for r in ROLES])
def test_chart_access_matrix(client, auth_header, chart, role):
    r = client.get(f"/api/analytics/{chart}", headers=auth_header(client, role))
    assert r.status_code == (200 if role in CHART_ACCESS[chart] else 403)


@pytest.mark.parametrize("chart", list(CHART_ACCESS))
def test_chart_needs_a_token(client, chart):
    assert client.get(f"/api/analytics/{chart}").status_code == 401


@pytest.mark.parametrize("chart", list(CHART_ACCESS))
def test_every_chart_has_the_chartjs_shape(client, auth_header, chart):
    d = client.get(f"/api/analytics/{chart}", headers=auth_header(client, "admin")).get_json()["data"]
    assert {"title", "chart_type", "labels", "datasets"} <= set(d)
    assert d["chart_type"] in ("line", "bar", "doughnut")
    for ds in d["datasets"]:
        assert {"label", "data", "backgroundColor", "borderColor"} <= set(ds)
        assert len(ds["data"]) == len(d["labels"])           # Chart.js needs equal lengths


def test_registration_trend_is_zero_filled(client, auth_header, patient_id):
    d = client.get("/api/analytics/patient-registrations?days=7", headers=auth_header(client, "admin")).get_json()["data"]
    assert len(d["labels"]) == 7 and d["labels"][-1] == local_today().isoformat()
    assert d["datasets"][0]["data"] == [0, 0, 0, 0, 0, 0, 1] and d["total"] == 1


@pytest.mark.parametrize("query", ["days=0", "days=366", "days=abc", "days=-5"])
def test_day_range_validation(client, auth_header, query):
    r = client.get(f"/api/analytics/patient-registrations?{query}", headers=auth_header(client, "admin"))
    assert r.status_code == 400 and "days" in r.get_json()["errors"]


def test_department_chart(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    doctor_id = doctor_setup["doctor"]["id"]
    _book_today(client, auth_header, doctor_id, patient_id)
    client.post("/api/departments", headers=auth_header(client, "admin"), json={"name": "Orthopedics"})
    d = client.get("/api/analytics/department-patients", headers=auth_header(client, "admin")).get_json()["data"]
    counts = dict(zip(d["labels"], d["datasets"][0]["data"]))
    assert counts == {"Cardiology": 1, "Orthopedics": 0}
    # the same patient admitted under the same department is still ONE patient, not two
    client.post("/api/admissions", headers=auth_header(client, "receptionist"), json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"], "doctor_id": doctor_id, "reason": "Observation"})
    d = client.get("/api/analytics/department-patients", headers=auth_header(client, "admin")).get_json()["data"]
    assert dict(zip(d["labels"], d["datasets"][0]["data"]))["Cardiology"] == 1


def test_bed_occupancy_chart(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    client.post("/api/admissions", headers=auth_header(client, "receptionist"), json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"], "doctor_id": doctor_setup["doctor"]["id"], "reason": "Observation"})
    d = client.get("/api/analytics/bed-occupancy", headers=auth_header(client, "nurse")).get_json()["data"]
    assert d["labels"] == ["General Ward A"] and d["stacked"] is True
    assert {ds["label"]: ds["data"] for ds in d["datasets"]} == {"Occupied": [1], "Available": [0], "Maintenance": [0]}
    assert d["summary"]["total"] == 1 and d["summary"]["occupancy_percent"] == 100.0


def test_bed_occupancy_with_no_beds_has_no_division_by_zero(client, auth_header):
    d = client.get("/api/analytics/bed-occupancy", headers=auth_header(client, "admin")).get_json()["data"]
    assert d["summary"]["occupancy_percent"] == 0.0 and d["labels"] == []


def test_emergency_chart_orders_priorities(client, auth_header, patient_id):
    h = auth_header(client, "nurse")
    client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Chest pain", **CRITICAL})
    client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Cut", "blood_pressure_systolic": 120,
                                                "blood_pressure_diastolic": 80, "heart_rate": 75, "oxygen_level": 98, "temperature": 98.6})
    d = client.get("/api/analytics/emergency-cases?days=7", headers=auth_header(client, "doctor")).get_json()["data"]
    assert [ds["label"] for ds in d["datasets"]] == ["Critical", "High", "Medium", "Low"]
    assert d["datasets"][0]["data"][-1] == 1 and d["datasets"][3]["data"][-1] == 1 and d["total"] == 2


def test_monthly_revenue_chart(client, auth_header, patient_id):
    _bill_and_pay(client, auth_header, patient_id, amount=1000, pay=400)
    d = client.get("/api/analytics/monthly-revenue?months=6", headers=auth_header(client, "billing_staff")).get_json()["data"]
    today = local_today()
    assert len(d["labels"]) == 6 and d["labels"][-1] == f"{today.year}-{today.month:02d}"
    ds = {x["label"]: x["data"] for x in d["datasets"]}
    assert ds["Billed (Rs.)"][-1] == 1000.0 and ds["Collected (Rs.)"][-1] == 400.0
    assert sum(ds["Billed (Rs.)"][:-1]) == 0


@pytest.mark.parametrize("query", ["months=0", "months=25", "months=x"])
def test_month_range_validation(client, auth_header, query):
    assert client.get(f"/api/analytics/monthly-revenue?{query}", headers=auth_header(client, "admin")).status_code == 400


def test_lab_statistics_chart(client, auth_header, scenario):
    scenario(discharge=False)
    d = client.get("/api/analytics/lab-statistics", headers=auth_header(client, "lab_technician")).get_json()["data"]
    assert d["labels"] == ["CBC"]
    assert {ds["label"]: ds["data"] for ds in d["datasets"]} == {"Tests ordered": [1], "Abnormal results": [1]}


def test_medicine_consumption_chart(client, auth_header, scenario):
    scenario(discharge=False)
    d = client.get("/api/analytics/medicine-consumption", headers=auth_header(client, "pharmacist")).get_json()["data"]
    assert d["labels"] == ["Paracetamol"] and d["datasets"][0]["data"] == [4]
    assert client.get("/api/analytics/medicine-consumption?limit=0", headers=auth_header(client, "admin")).status_code == 400
    assert client.get("/api/analytics/medicine-consumption?days=7&limit=1", headers=auth_header(client, "admin")).status_code == 200
