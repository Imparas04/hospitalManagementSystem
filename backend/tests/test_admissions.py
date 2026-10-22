import pytest


def test_admin_can_create_ward_and_bed(client, auth_header):
    h = auth_header(client, "admin")
    ward = client.post("/api/wards", headers=h, json={"name": "ICU Block", "ward_type": "icu"}).get_json()["data"]
    assert ward["ward_type"] == "icu" and ward["total_beds"] == 0
    bed = client.post(f"/api/wards/{ward['id']}/beds", headers=h,
                       json={"bed_number": "ICU-1", "bed_type": "icu"}).get_json()["data"]
    assert bed["status"] == "available"


def test_ward_validation(client, auth_header):
    r = client.post("/api/wards", headers=auth_header(client, "admin"), json={"name": "", "ward_type": "bad"})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and "name" in errors and "ward_type" in errors


def test_duplicate_bed_number_in_same_ward_rejected(client, auth_header, ward_and_bed):
    h = auth_header(client, "admin")
    r = client.post(f"/api/wards/{ward_and_bed['ward']['id']}/beds", headers=h,
                     json={"bed_number": "A-101", "bed_type": "general"})
    assert r.status_code == 400 and "bed_number" in r.get_json()["errors"]


@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse"])
def test_non_admin_cannot_create_ward(client, auth_header, role):
    r = client.post("/api/wards", headers=auth_header(client, role), json={"name": "X", "ward_type": "general"})
    assert r.status_code == 403


def test_list_wards_and_beds(client, auth_header, ward_and_bed):
    h = auth_header(client, "nurse")
    assert client.get("/api/wards", headers=h).get_json()["data"][0]["available_beds"] == 1
    r = client.get(f"/api/beds?ward_id={ward_and_bed['ward']['id']}", headers=h)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1


def test_nurse_can_update_bed_status_but_not_free_occupied_directly(client, auth_header, ward_and_bed):
    h_n = auth_header(client, "nurse")
    bed_id = ward_and_bed["bed"]["id"]
    r = client.put(f"/api/beds/{bed_id}", headers=h_n, json={"status": "maintenance"})
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "maintenance"

    client.put(f"/api/beds/{bed_id}", headers=h_n, json={"status": "available"})
    client.put(f"/api/beds/{bed_id}", headers=h_n, json={"status": "occupied"})
    r = client.put(f"/api/beds/{bed_id}", headers=h_n, json={"status": "available"})
    assert r.status_code == 400  # must discharge instead


def test_lab_tech_cannot_update_bed(client, auth_header, ward_and_bed):
    r = client.put(f"/api/beds/{ward_and_bed['bed']['id']}", headers=auth_header(client, "lab_technician"),
                    json={"status": "maintenance"})
    assert r.status_code == 403


def test_bed_status_validation(client, auth_header, ward_and_bed):
    r = client.put(f"/api/beds/{ward_and_bed['bed']['id']}", headers=auth_header(client, "nurse"),
                    json={"status": "sleeping"})
    assert r.status_code == 400


# ------------------------------------------------------------ admissions --

def test_admit_patient_occupies_bed(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    h = auth_header(client, "receptionist")
    r = client.post("/api/admissions", headers=h, json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
        "doctor_id": doctor_setup["doctor"]["id"], "reason": "Observation"})
    body = r.get_json()
    assert r.status_code == 201 and body["data"]["status"] == "admitted"
    assert body["data"]["bed_number"] == "A-101"

    bed = client.get(f"/api/beds?ward_id={ward_and_bed['ward']['id']}", headers=h).get_json()["data"][0]
    assert bed["status"] == "occupied"


def test_cannot_admit_to_occupied_bed(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    h = auth_header(client, "receptionist")
    payload = {"patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
               "doctor_id": doctor_setup["doctor"]["id"], "reason": "Observation"}
    client.post("/api/admissions", headers=h, json=payload)
    r = client.post("/api/admissions", headers=h, json=payload)
    assert r.status_code == 409


def test_admission_validation(client, auth_header):
    r = client.post("/api/admissions", headers=auth_header(client, "receptionist"), json={})
    errors = r.get_json()["errors"]
    assert r.status_code == 400
    for field in ("patient_id", "bed_id", "doctor_id", "reason"):
        assert field in errors


def test_admission_unknown_patient_or_doctor(client, auth_header, ward_and_bed):
    r = client.post("/api/admissions", headers=auth_header(client, "receptionist"), json={
        "patient_id": 9999, "bed_id": ward_and_bed["bed"]["id"], "doctor_id": 9999, "reason": "Checkup"})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and "patient_id" in errors and "doctor_id" in errors


@pytest.mark.parametrize("role", ["doctor", "lab_technician", "pharmacist", "billing_staff"])
def test_only_receptionist_nurse_admin_can_admit(client, auth_header, doctor_setup, patient_id, ward_and_bed, role):
    r = client.post("/api/admissions", headers=auth_header(client, role), json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
        "doctor_id": doctor_setup["doctor"]["id"], "reason": "Checkup"})
    assert r.status_code == 403


def test_discharge_frees_bed(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    h = auth_header(client, "receptionist")
    admission = client.post("/api/admissions", headers=h, json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
        "doctor_id": doctor_setup["doctor"]["id"], "reason": "Observation"}).get_json()["data"]

    r = client.post(f"/api/admissions/{admission['id']}/discharge", headers=auth_header(client, "nurse"))
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "discharged"
    assert r.get_json()["data"]["discharge_date"] is not None

    bed = client.get(f"/api/beds?ward_id={ward_and_bed['ward']['id']}", headers=h).get_json()["data"][0]
    assert bed["status"] == "available"

    r = client.post(f"/api/admissions/{admission['id']}/discharge", headers=h)
    assert r.status_code == 400  # already discharged


def test_list_and_filter_admissions(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    h = auth_header(client, "receptionist")
    client.post("/api/admissions", headers=h, json={
        "patient_id": patient_id, "bed_id": ward_and_bed["bed"]["id"],
        "doctor_id": doctor_setup["doctor"]["id"], "reason": "Observation"})
    r = client.get(f"/api/admissions?patient_id={patient_id}&status=admitted", headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["total"] == 1
    r = client.get(f"/api/admissions?ward_id={ward_and_bed['ward']['id']}", headers=h)
    assert r.get_json()["data"]["total"] == 1


def test_get_unknown_admission_404(client, auth_header):
    assert client.get("/api/admissions/9999", headers=auth_header(client, "receptionist")).status_code == 404
