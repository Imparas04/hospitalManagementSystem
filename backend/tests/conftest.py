import pytest

from app import create_app
from app.cli import seed_roles
from app.config import TestingConfig
from app.extensions import db
from app.models.role import ALL_ROLES
from app.services import user_service

PASSWORD = "Test1234"


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        seed_roles()
        # one user per role: admin_user, doctor_user, ...
        for role in ALL_ROLES:
            user_service.create_user({
                "username": f"t_{role}", "email": f"t_{role}@test.com",
                "password": PASSWORD, "full_name": f"Test {role}", "role": role})
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, role):
    resp = client.post("/api/auth/login", json={"username": f"t_{role}", "password": PASSWORD})
    return resp.get_json()["data"]["access_token"]


@pytest.fixture()
def auth_header():
    """auth_header(client, 'doctor') -> {'Authorization': 'Bearer ...'}"""
    def _make(client, role):
        return {"Authorization": f"Bearer {login(client, role)}"}
    return _make


@pytest.fixture()
def doctor_setup(client, auth_header):
    """Creates a department and a Doctor profile for the standard t_doctor user.
    Returns {"department": {...}, "doctor": {...}}."""
    admin = auth_header(client, "admin")
    dept = client.post("/api/departments", headers=admin, json={"name": "Cardiology"}).get_json()["data"]
    doctor_user_id = client.get("/api/auth/me", headers=auth_header(client, "doctor")).get_json()["data"]["id"]
    doc = client.post("/api/doctors", headers=admin, json={
        "user_id": doctor_user_id, "department_id": dept["id"], "specialization": "Cardiologist",
    }).get_json()["data"]
    return {"department": dept, "doctor": doc}


@pytest.fixture()
def patient_id(client, auth_header):
    """Registers one standard patient and returns its id."""
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json={
        "full_name": "Ramesh Kulkarni", "date_of_birth": "1990-05-15", "gender": "male",
        "phone": "+919876543210",
    })
    return r.get_json()["data"]["id"]


@pytest.fixture()
def ward_and_bed(client, auth_header):
    """Creates one general ward with one available bed. Returns {"ward": {...}, "bed": {...}}."""
    admin = auth_header(client, "admin")
    ward = client.post("/api/wards", headers=admin, json={"name": "General Ward A", "ward_type": "general"}).get_json()["data"]
    bed = client.post(f"/api/wards/{ward['id']}/beds", headers=admin,
                       json={"bed_number": "A-101", "bed_type": "general"}).get_json()["data"]
    return {"ward": ward, "bed": bed}


@pytest.fixture()
def lab_test_type(client, auth_header):
    """Creates one lab test type (CBC). Returns the dict."""
    r = client.post("/api/lab/tests", headers=auth_header(client, "admin"),
                     json={"name": "Complete Blood Count", "code": "CBC", "normal_range": "4.5-11.0"})
    return r.get_json()["data"]


@pytest.fixture()
def medicine_with_stock(client, auth_header):
    """Creates one medicine with one non-expired batch of 20 units. Returns the dict with 'id'."""
    h = auth_header(client, "admin")
    med = client.post("/api/pharmacy/medicines", headers=h,
                       json={"name": "Paracetamol", "unit": "tablet", "reorder_level": 10}).get_json()["data"]
    client.post(f"/api/pharmacy/medicines/{med['id']}/batches", headers=h,
                json={"batch_number": "B001", "expiry_date": "2027-12-31", "purchase_quantity": 20})
    return med


@pytest.fixture()
def icu_ward_and_bed(client, auth_header):
    """Creates one ICU ward with one available ICU bed."""
    admin = auth_header(client, "admin")
    ward = client.post("/api/wards", headers=admin, json={"name": "ICU Block", "ward_type": "icu"}).get_json()["data"]
    bed = client.post(f"/api/wards/{ward['id']}/beds", headers=admin,
                       json={"bed_number": "ICU-1", "bed_type": "icu"}).get_json()["data"]
    return {"ward": ward, "bed": bed}


@pytest.fixture()
def scenario(client, auth_header, doctor_setup, patient_id):
    """Returns build(discharge=True, ...) which creates a full hospital story for `patient_id`:
    completed appointment + admission + lab test with result + issued medicine (+ nurse discharge).
    Prices are chosen so totals are easy to check:  600 (consult) + 1500 (1 bed day) + 250 (lab)
    + 4 x 12.50 (medicine) = 2400.00"""
    def build(discharge=True, fee=600, daily=1500, lab_price=250, med_price=12.5, qty=4):
        admin = auth_header(client, "admin")
        rec = auth_header(client, "receptionist")
        doc = auth_header(client, "doctor")
        lab = auth_header(client, "lab_technician")
        pharm = auth_header(client, "pharmacist")
        nurse = auth_header(client, "nurse")
        doctor_id = doctor_setup["doctor"]["id"]

        # consultation: schedule -> book -> complete
        client.put(f"/api/doctors/{doctor_id}", headers=admin, json={"consultation_fee": fee})
        from app.utils.timeutils import local_today      # the appointment is TODAY, so date-range tests never go stale
        today = local_today()
        client.post(f"/api/doctors/{doctor_id}/schedule", headers=admin,
                    json={"day_of_week": today.weekday(), "start_time": "09:00", "end_time": "09:30"})
        appt = client.post("/api/appointments", headers=rec, json={
            "patient_id": patient_id, "doctor_id": doctor_id, "appointment_date": today.isoformat(),
            "appointment_time": "09:00", "reason": "Fever and cough"}).get_json()["data"]
        client.post(f"/api/appointments/{appt['id']}/complete", headers=doc)

        # admission
        ward = client.post("/api/wards", headers=admin, json={
            "name": "General Ward A", "ward_type": "general", "daily_charge": daily}).get_json()["data"]
        bed = client.post(f"/api/wards/{ward['id']}/beds", headers=admin,
                          json={"bed_number": "A-1", "bed_type": "general"}).get_json()["data"]
        adm = client.post("/api/admissions", headers=rec, json={
            "patient_id": patient_id, "bed_id": bed["id"], "doctor_id": doctor_id,
            "reason": "Pneumonia observation"}).get_json()["data"]

        # lab test with result
        test = client.post("/api/lab/tests", headers=admin, json={
            "name": "Complete Blood Count", "code": "CBC", "price": lab_price}).get_json()["data"]
        order = client.post("/api/lab/orders", headers=doc, json={
            "patient_id": patient_id, "lab_test_id": test["id"]}).get_json()["data"]
        client.post(f"/api/lab/orders/{order['id']}/result", headers=lab,
                    json={"result_value": "WBC 12.8 - elevated", "is_abnormal": True})

        # medicine issued
        med = client.post("/api/pharmacy/medicines", headers=admin, json={
            "name": "Paracetamol", "unit": "tablet", "unit_price": med_price}).get_json()["data"]
        client.post(f"/api/pharmacy/medicines/{med['id']}/batches", headers=admin,
                    json={"batch_number": "B1", "expiry_date": "2027-12-31", "purchase_quantity": 20})
        presc = client.post("/api/prescriptions", headers=doc, json={
            "patient_id": patient_id,
            "items": [{"medicine_id": med["id"], "dosage": "1 tablet 3x daily", "quantity": qty}]}).get_json()["data"]
        client.post(f"/api/prescriptions/{presc['id']}/issue", headers=pharm)

        if discharge:
            client.post(f"/api/admissions/{adm['id']}/discharge", headers=nurse)
        return {"patient_id": patient_id, "doctor_id": doctor_id, "appointment_id": appt["id"],
                "admission_id": adm["id"], "bed_id": bed["id"], "ward_id": ward["id"],
                "lab_order_id": order["id"], "prescription_id": presc["id"], "medicine_id": med["id"]}
    return build
