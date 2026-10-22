import pytest

VALID_PATIENT = {
    "full_name": "Ramesh Kulkarni", "date_of_birth": "1990-05-15", "gender": "male",
    "blood_group": "B+", "phone": "+919876500001", "email": "ramesh@test.com",
}


def test_receptionist_can_create_patient(client, auth_header):
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json=VALID_PATIENT)
    body = r.get_json()
    assert r.status_code == 201
    assert body["data"]["patient_code"].startswith("P")
    assert body["data"]["age"] is not None
    assert body["data"]["is_active"] is True


def test_patient_code_increments_and_is_unique(client, auth_header):
    h = auth_header(client, "receptionist")
    codes = []
    for _ in range(3):
        r = client.post("/api/patients", headers=h, json=VALID_PATIENT)
        codes.append(r.get_json()["data"]["patient_code"])
    assert len(set(codes)) == 3  # all unique
    nums = [int(c[-6:]) for c in codes]
    assert nums == sorted(nums)  # increasing


def test_create_patient_validation_errors(client, auth_header):
    bad = {"full_name": "A", "date_of_birth": "2099-01-01", "gender": "unknown_x",
           "phone": "abc", "email": "not-an-email", "blood_group": "ZZ"}
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json=bad)
    errors = r.get_json()["errors"]
    assert r.status_code == 400
    for field in ("full_name", "date_of_birth", "gender", "phone", "email", "blood_group"):
        assert field in errors


def test_create_patient_missing_required_fields(client, auth_header):
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json={})
    errors = r.get_json()["errors"]
    assert r.status_code == 400
    assert set(errors) == {"full_name", "date_of_birth", "gender", "phone"}


@pytest.mark.parametrize("role", ["doctor", "nurse", "lab_technician", "pharmacist", "billing_staff"])
def test_only_receptionist_and_admin_can_create(client, auth_header, role):
    r = client.post("/api/patients", headers=auth_header(client, role), json=VALID_PATIENT)
    assert r.status_code == 403


@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse", "admin"])
def test_these_roles_can_read_patients(client, auth_header, role):
    client.post("/api/patients", headers=auth_header(client, "receptionist"), json=VALID_PATIENT)
    r = client.get("/api/patients", headers=auth_header(client, role))
    assert r.status_code == 200


@pytest.mark.parametrize("role", ["lab_technician", "pharmacist", "billing_staff"])
def test_these_roles_cannot_read_patients(client, auth_header, role):
    r = client.get("/api/patients", headers=auth_header(client, role))
    assert r.status_code == 403


def test_no_token_on_patients_is_401(client):
    assert client.get("/api/patients").status_code == 401


def test_get_single_patient_and_404(client, auth_header):
    h = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h, json=VALID_PATIENT).get_json()["data"]["id"]
    assert client.get(f"/api/patients/{pid}", headers=h).status_code == 200
    assert client.get("/api/patients/9999", headers=h).status_code == 404


def test_update_patient(client, auth_header):
    h = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.put(f"/api/patients/{pid}", headers=h, json={"phone": "+919876500099"})
    assert r.status_code == 200 and r.get_json()["data"]["phone"] == "+919876500099"
    assert client.put(f"/api/patients/{pid}", headers=h, json={}).status_code == 400
    assert client.put(f"/api/patients/{pid}", headers=h, json={"gender": "bad"}).status_code == 400


def test_nurse_cannot_update_patient(client, auth_header):
    h_r = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h_r, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.put(f"/api/patients/{pid}", headers=auth_header(client, "nurse"), json={"phone": "+919876500001"})
    assert r.status_code == 403


def test_doctor_can_update_patient(client, auth_header):
    h_r = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h_r, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.put(f"/api/patients/{pid}", headers=auth_header(client, "doctor"), json={"phone": "+919876500001"})
    assert r.status_code == 200


def test_deactivate_patient(client, auth_header):
    h = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.delete(f"/api/patients/{pid}", headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["is_active"] is False
    # by default, list excludes inactive patients
    listed = client.get("/api/patients", headers=h).get_json()["data"]["items"]
    assert pid not in [p["id"] for p in listed]
    listed_all = client.get("/api/patients?is_active=false", headers=h).get_json()["data"]["items"]
    assert pid in [p["id"] for p in listed_all]


def test_emergency_registration_minimal_data(client, auth_header):
    h = auth_header(client, "receptionist")
    payload = {"full_name": "Unknown Male", "date_of_birth": "1985-01-01", "gender": "male",
               "phone": "0000000000", "is_emergency_registration": True}
    r = client.post("/api/patients", headers=h, json=payload)
    body = r.get_json()
    assert r.status_code == 201
    assert body["data"]["is_emergency_registration"] is True
    assert body["data"]["registration_pending"] is True


def test_search_and_filter_patients(client, auth_header):
    h = auth_header(client, "receptionist")
    client.post("/api/patients", headers=h, json=VALID_PATIENT)
    client.post("/api/patients", headers=h, json={**VALID_PATIENT, "full_name": "Sita Devi", "gender": "female", "phone": "+919876500002"})
    r = client.get("/api/patients?q=Sita", headers=h)
    assert r.get_json()["data"]["total"] == 1
    r = client.get("/api/patients?gender=female", headers=h)
    assert r.get_json()["data"]["total"] == 1
    r = client.get("/api/patients?blood_group=B%2B", headers=h)  # '+' must be URL-encoded in query strings
    assert r.get_json()["data"]["total"] == 2
    assert client.get("/api/patients?min_age=abc", headers=h).status_code == 400


def test_pagination_on_patients(client, auth_header):
    h = auth_header(client, "receptionist")
    for i in range(5):
        client.post("/api/patients", headers=h, json={**VALID_PATIENT, "phone": f"+91987650{i:04d}"})
    r = client.get("/api/patients?per_page=2&page=1", headers=h)
    d = r.get_json()["data"]
    assert len(d["items"]) == 2 and d["total"] == 5 and d["pages"] == 3
    assert client.get("/api/patients?page=0", headers=h).status_code == 400


# ---------------------------------------------------------- medical history / visits --

def test_add_and_list_medical_history(client, auth_header):
    h_r = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h_r, json=VALID_PATIENT).get_json()["data"]["id"]
    h_d = auth_header(client, "doctor")
    r = client.post(f"/api/patients/{pid}/medical-history", headers=h_d,
                     json={"condition_type": "allergy", "description": "Penicillin allergy"})
    assert r.status_code == 201 and r.get_json()["data"]["recorded_by"] == "Test doctor"
    r = client.get(f"/api/patients/{pid}/medical-history", headers=h_r)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1


def test_medical_history_validation(client, auth_header):
    h = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.post(f"/api/patients/{pid}/medical-history", headers=h, json={"condition_type": "bad", "description": "x"})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and "condition_type" in errors and "description" in errors


def test_nurse_cannot_add_medical_history(client, auth_header):
    h_r = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h_r, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.post(f"/api/patients/{pid}/medical-history", headers=auth_header(client, "nurse"),
                     json={"condition_type": "note", "description": "fine"})
    assert r.status_code == 403


def test_add_and_list_visits_and_included_in_patient_detail(client, auth_header):
    h = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.post(f"/api/patients/{pid}/visits", headers=h, json={"visit_type": "opd", "reason": "Fever checkup"})
    assert r.status_code == 201
    r = client.get(f"/api/patients/{pid}/visits", headers=h)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1
    full = client.get(f"/api/patients/{pid}?include_history=true", headers=h).get_json()["data"]
    assert len(full["visits"]) == 1 and "medical_history" in full


def test_visit_validation(client, auth_header):
    h = auth_header(client, "receptionist")
    pid = client.post("/api/patients", headers=h, json=VALID_PATIENT).get_json()["data"]["id"]
    r = client.post(f"/api/patients/{pid}/visits", headers=h, json={"visit_type": "bad", "reason": ""})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and "visit_type" in errors and "reason" in errors


def test_medical_history_404_for_unknown_patient(client, auth_header):
    h = auth_header(client, "doctor")
    r = client.post("/api/patients/9999/medical-history", headers=h, json={"condition_type": "note", "description": "x"})
    assert r.status_code == 404
