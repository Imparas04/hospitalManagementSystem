import pytest

NORMAL_VITALS = {"blood_pressure_systolic": 120, "blood_pressure_diastolic": 80,
                  "heart_rate": 75, "oxygen_level": 98, "temperature": 98.6}
CRITICAL_VITALS = {"blood_pressure_systolic": 200, "blood_pressure_diastolic": 110,
                    "heart_rate": 150, "oxygen_level": 85, "temperature": 103.0}


def test_priority_calculation_low(client, auth_header, patient_id):
    r = client.post("/api/triage", headers=auth_header(client, "nurse"),
                     json={"patient_id": patient_id, "symptoms": "Mild headache", **NORMAL_VITALS})
    body = r.get_json()
    assert r.status_code == 201
    assert body["data"]["priority_level"] == "low"
    assert body["data"]["status"] == "waiting"


def test_priority_calculation_critical(client, auth_header, patient_id):
    r = client.post("/api/triage", headers=auth_header(client, "nurse"),
                     json={"patient_id": patient_id, "symptoms": "Unconscious after accident",
                           "emergency_condition": "Road accident", **CRITICAL_VITALS})
    body = r.get_json()
    assert r.status_code == 201
    assert body["data"]["priority_level"] == "critical"
    assert body["data"]["priority_score"] >= 7


def test_triage_validation(client, auth_header):
    r = client.post("/api/triage", headers=auth_header(client, "nurse"), json={})
    errors = r.get_json()["errors"]
    assert r.status_code == 400
    for field in ("patient_id", "blood_pressure_systolic", "heart_rate", "oxygen_level", "temperature", "symptoms"):
        assert field in errors


@pytest.mark.parametrize("role", ["receptionist", "doctor", "lab_technician", "pharmacist", "billing_staff"])
def test_only_nurse_and_admin_create_triage(client, auth_header, patient_id, role):
    r = client.post("/api/triage", headers=auth_header(client, role),
                     json={"patient_id": patient_id, "symptoms": "Pain", **NORMAL_VITALS})
    assert r.status_code == 403


def test_queue_sorted_most_urgent_first(client, auth_header, patient_id):
    h = auth_header(client, "nurse")
    low = client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Minor cut", **NORMAL_VITALS}).get_json()["data"]
    critical = client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Severe trauma", **CRITICAL_VITALS}).get_json()["data"]

    queue = client.get("/api/triage/queue", headers=h).get_json()["data"]
    assert len(queue) == 2
    assert queue[0]["id"] == critical["id"]  # critical comes first despite being recorded second
    assert queue[1]["id"] == low["id"]


def test_doctor_can_read_queue_but_not_create(client, auth_header, patient_id):
    h_n = auth_header(client, "nurse")
    client.post("/api/triage", headers=h_n, json={"patient_id": patient_id, "symptoms": "Pain", **NORMAL_VITALS})
    r = client.get("/api/triage/queue", headers=auth_header(client, "doctor"))
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1


def test_update_status(client, auth_header, patient_id):
    h = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Pain", **NORMAL_VITALS}).get_json()["data"]
    r = client.put(f"/api/triage/{record['id']}/status", headers=auth_header(client, "doctor"), json={"status": "in_treatment"})
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "in_treatment"
    r = client.put(f"/api/triage/{record['id']}/status", headers=h, json={"status": "bad_status"})
    assert r.status_code == 400


def test_resolve_triage(client, auth_header, patient_id):
    h = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Pain", **NORMAL_VITALS}).get_json()["data"]
    r = client.post(f"/api/triage/{record['id']}/resolve", headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "resolved"


def test_get_unknown_triage_404(client, auth_header):
    assert client.get("/api/triage/9999", headers=auth_header(client, "nurse")).status_code == 404


# ------------------------------------------------------- smart bed allocation --

def test_smart_allocation_picks_matching_bed_type(client, auth_header, doctor_setup, patient_id, icu_ward_and_bed, ward_and_bed):
    """Patient needs ICU -> must get the ICU bed, not the general bed, even though both exist."""
    h_n = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h_n, json={
        "patient_id": patient_id, "symptoms": "Cardiac arrest", "icu_required": True, **CRITICAL_VITALS
    }).get_json()["data"]

    r = client.post(f"/api/triage/{record['id']}/allocate-bed", headers=h_n,
                     json={"doctor_id": doctor_setup["doctor"]["id"]})
    body = r.get_json()
    assert r.status_code == 201
    assert body["data"]["admission"]["bed_number"] == icu_ward_and_bed["bed"]["bed_number"]
    assert body["data"]["triage"]["status"] == "bed_assigned"


def test_smart_allocation_no_matching_bed(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    """Patient needs isolation but only a general bed exists -> should fail with a clear message."""
    h_n = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h_n, json={
        "patient_id": patient_id, "symptoms": "Suspected infectious disease", "isolation_required": True, **NORMAL_VITALS
    }).get_json()["data"]
    r = client.post(f"/api/triage/{record['id']}/allocate-bed", headers=h_n,
                     json={"doctor_id": doctor_setup["doctor"]["id"]})
    assert r.status_code == 409
    assert "isolation" in r.get_json()["message"]


def test_smart_allocation_respects_gender_restricted_ward(client, auth_header, doctor_setup, patient_id):
    """patient_id fixture is male. A female-only ward's bed must NOT be allocated to him."""
    h_admin = auth_header(client, "admin")
    ward = client.post("/api/wards", headers=h_admin,
                        json={"name": "Maternity Ward", "ward_type": "maternity", "gender_restriction": "female"}).get_json()["data"]
    client.post(f"/api/wards/{ward['id']}/beds", headers=h_admin, json={"bed_number": "M-1", "bed_type": "general"})

    h_n = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h_n, json={"patient_id": patient_id, "symptoms": "Fever", **NORMAL_VITALS}).get_json()["data"]
    r = client.post(f"/api/triage/{record['id']}/allocate-bed", headers=h_n,
                     json={"doctor_id": doctor_setup["doctor"]["id"]})
    assert r.status_code == 409  # no eligible bed for a male patient


def test_allocate_bed_requires_doctor_id(client, auth_header, patient_id, ward_and_bed):
    h = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h, json={"patient_id": patient_id, "symptoms": "Pain", **NORMAL_VITALS}).get_json()["data"]
    r = client.post(f"/api/triage/{record['id']}/allocate-bed", headers=h, json={})
    assert r.status_code == 400


def test_cannot_allocate_bed_twice(client, auth_header, doctor_setup, patient_id, ward_and_bed):
    h_n = auth_header(client, "nurse")
    record = client.post("/api/triage", headers=h_n, json={"patient_id": patient_id, "symptoms": "Pain", **NORMAL_VITALS}).get_json()["data"]
    client.post(f"/api/triage/{record['id']}/allocate-bed", headers=h_n, json={"doctor_id": doctor_setup["doctor"]["id"]})
    r = client.post(f"/api/triage/{record['id']}/allocate-bed", headers=h_n, json={"doctor_id": doctor_setup["doctor"]["id"]})
    assert r.status_code == 400  # already bed_assigned, not waiting
