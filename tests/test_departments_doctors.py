import pytest


def test_admin_can_create_department(client, auth_header):
    r = client.post("/api/departments", headers=auth_header(client, "admin"), json={"name": "Orthopedics"})
    assert r.status_code == 201 and r.get_json()["data"]["name"] == "Orthopedics"


def test_duplicate_department_rejected(client, auth_header):
    h = auth_header(client, "admin")
    client.post("/api/departments", headers=h, json={"name": "Orthopedics"})
    r = client.post("/api/departments", headers=h, json={"name": "Orthopedics"})
    assert r.status_code == 409


def test_department_validation(client, auth_header):
    r = client.post("/api/departments", headers=auth_header(client, "admin"), json={"name": "A"})
    assert r.status_code == 400 and "name" in r.get_json()["errors"]


@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse"])
def test_non_admin_cannot_create_department(client, auth_header, role):
    r = client.post("/api/departments", headers=auth_header(client, role), json={"name": "X Dept"})
    assert r.status_code == 403


@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse", "admin"])
def test_these_roles_can_read_departments(client, auth_header, role):
    client.post("/api/departments", headers=auth_header(client, "admin"), json={"name": "ENT"})
    r = client.get("/api/departments", headers=auth_header(client, role))
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1


def test_lab_tech_cannot_read_departments(client, auth_header):
    r = client.get("/api/departments", headers=auth_header(client, "lab_technician"))
    assert r.status_code == 403


def test_update_department(client, auth_header):
    h = auth_header(client, "admin")
    dept = client.post("/api/departments", headers=h, json={"name": "ENT"}).get_json()["data"]
    r = client.put(f"/api/departments/{dept['id']}", headers=h, json={"is_active": False})
    assert r.status_code == 200 and r.get_json()["data"]["is_active"] is False
    assert client.put("/api/departments/9999", headers=h, json={"is_active": True}).status_code == 404


# ------------------------------------------------------------------ doctors --

def test_create_doctor_profile(client, doctor_setup):
    assert doctor_setup["doctor"]["specialization"] == "Cardiologist"
    assert doctor_setup["doctor"]["department"] == "Cardiology"


def test_create_doctor_requires_user_with_doctor_role(client, auth_header):
    h = auth_header(client, "admin")
    dept = client.post("/api/departments", headers=h, json={"name": "Neurology"}).get_json()["data"]
    nurse_id = client.get("/api/auth/me", headers=auth_header(client, "nurse")).get_json()["data"]["id"]
    r = client.post("/api/doctors", headers=h, json={
        "user_id": nurse_id, "department_id": dept["id"], "specialization": "Neuro"})
    assert r.status_code == 400 and "user_id" in r.get_json()["errors"]


def test_cannot_create_doctor_profile_twice_for_same_user(client, auth_header, doctor_setup):
    h = auth_header(client, "admin")
    doctor_user_id = client.get("/api/auth/me", headers=auth_header(client, "doctor")).get_json()["data"]["id"]
    r = client.post("/api/doctors", headers=h, json={
        "user_id": doctor_user_id, "department_id": doctor_setup["department"]["id"], "specialization": "Again"})
    assert r.status_code == 400 and "user_id" in r.get_json()["errors"]


def test_create_doctor_unknown_department(client, auth_header):
    h = auth_header(client, "admin")
    doctor_user_id = client.get("/api/auth/me", headers=auth_header(client, "doctor")).get_json()["data"]["id"]
    r = client.post("/api/doctors", headers=h, json={
        "user_id": doctor_user_id, "department_id": 9999, "specialization": "X"})
    assert r.status_code == 400 and "department_id" in r.get_json()["errors"]


def test_only_admin_creates_doctor_profile(client, auth_header):
    h = auth_header(client, "receptionist")
    r = client.post("/api/doctors", headers=h, json={"user_id": 1, "department_id": 1, "specialization": "X"})
    assert r.status_code == 403


def test_list_and_filter_doctors(client, auth_header, doctor_setup):
    h = auth_header(client, "receptionist")
    r = client.get(f"/api/doctors?department_id={doctor_setup['department']['id']}", headers=h)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1
    r = client.get("/api/doctors?specialization=Cardio", headers=h)
    assert len(r.get_json()["data"]) == 1
    r = client.get("/api/doctors?emergency_duty=true", headers=h)
    assert len(r.get_json()["data"]) == 0


def test_get_doctor_includes_schedule(client, auth_header, doctor_setup):
    doctor_id = doctor_setup["doctor"]["id"]
    h = auth_header(client, "admin")
    client.post(f"/api/doctors/{doctor_id}/schedule", headers=h,
                json={"day_of_week": 0, "start_time": "09:00", "end_time": "13:00", "slot_minutes": 15})
    r = client.get(f"/api/doctors/{doctor_id}", headers=auth_header(client, "nurse"))
    assert r.status_code == 200 and len(r.get_json()["data"]["schedules"]) == 1
    assert client.get("/api/doctors/9999", headers=h).status_code == 404


def test_update_doctor(client, auth_header, doctor_setup):
    h = auth_header(client, "admin")
    doctor_id = doctor_setup["doctor"]["id"]
    r = client.put(f"/api/doctors/{doctor_id}", headers=h, json={"is_on_emergency_duty": True})
    assert r.status_code == 200 and r.get_json()["data"]["is_on_emergency_duty"] is True


# ----------------------------------------------------------------- schedule --

def test_add_schedule_validation(client, auth_header, doctor_setup):
    h = auth_header(client, "admin")
    doctor_id = doctor_setup["doctor"]["id"]
    bad = {"day_of_week": 9, "start_time": "25:00", "end_time": "13:00", "slot_minutes": 1}
    r = client.post(f"/api/doctors/{doctor_id}/schedule", headers=h, json=bad)
    errors = r.get_json()["errors"]
    assert r.status_code == 400
    assert "day_of_week" in errors and "start_time" in errors and "slot_minutes" in errors


def test_schedule_end_before_start_rejected(client, auth_header, doctor_setup):
    h = auth_header(client, "admin")
    doctor_id = doctor_setup["doctor"]["id"]
    r = client.post(f"/api/doctors/{doctor_id}/schedule", headers=h,
                     json={"day_of_week": 0, "start_time": "13:00", "end_time": "09:00"})
    assert r.status_code == 400 and "end_time" in r.get_json()["errors"]


def test_only_admin_adds_schedule(client, auth_header, doctor_setup):
    doctor_id = doctor_setup["doctor"]["id"]
    r = client.post(f"/api/doctors/{doctor_id}/schedule", headers=auth_header(client, "doctor"),
                     json={"day_of_week": 0, "start_time": "09:00", "end_time": "13:00"})
    assert r.status_code == 403


def test_availability_endpoint(client, auth_header, doctor_setup):
    h = auth_header(client, "admin")
    doctor_id = doctor_setup["doctor"]["id"]
    # Monday = day_of_week 0
    client.post(f"/api/doctors/{doctor_id}/schedule", headers=h,
                json={"day_of_week": 0, "start_time": "09:00", "end_time": "09:30", "slot_minutes": 15})
    r = client.get(f"/api/doctors/{doctor_id}/availability?date=2026-10-05",  # a Monday
                    headers=auth_header(client, "receptionist"))
    assert r.status_code == 200
    assert r.get_json()["data"]["slots"] == ["09:00", "09:15"]


def test_availability_requires_date(client, auth_header, doctor_setup):
    r = client.get(f"/api/doctors/{doctor_setup['doctor']['id']}/availability",
                    headers=auth_header(client, "receptionist"))
    assert r.status_code == 400
