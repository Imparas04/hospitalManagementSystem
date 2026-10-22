import pytest


def test_admin_creates_test_type(client, auth_header):
    r = client.post("/api/lab/tests", headers=auth_header(client, "admin"),
                     json={"name": "Lipid Profile", "code": "LIPID"})
    assert r.status_code == 201 and r.get_json()["data"]["code"] == "LIPID"


def test_lab_tech_can_also_create_test_type(client, auth_header):
    r = client.post("/api/lab/tests", headers=auth_header(client, "lab_technician"),
                     json={"name": "Blood Sugar", "code": "SUGAR"})
    assert r.status_code == 201


def test_duplicate_test_code_rejected(client, auth_header):
    h = auth_header(client, "admin")
    client.post("/api/lab/tests", headers=h, json={"name": "A", "code": "DUP"})
    r = client.post("/api/lab/tests", headers=h, json={"name": "B", "code": "DUP"})
    assert r.status_code == 409


def test_receptionist_cannot_create_test_type(client, auth_header):
    r = client.post("/api/lab/tests", headers=auth_header(client, "receptionist"), json={"name": "X", "code": "X1"})
    assert r.status_code == 403


def test_list_test_types(client, auth_header, lab_test_type):
    r = client.get("/api/lab/tests", headers=auth_header(client, "lab_technician"))
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1


def test_doctor_orders_test(client, auth_header, doctor_setup, patient_id, lab_test_type):
    r = client.post("/api/lab/orders", headers=auth_header(client, "doctor"),
                     json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"], "notes": "Fasting required"})
    body = r.get_json()
    assert r.status_code == 201 and body["data"]["status"] == "ordered"
    assert body["data"]["test_code"] == "CBC"


def test_order_requires_doctor_profile(client, auth_header, patient_id, lab_test_type):
    """A user with role=doctor but no linked Doctor profile (not created via /api/doctors) can't order."""
    r = client.post("/api/lab/orders", headers=auth_header(client, "doctor"),
                     json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]})
    assert r.status_code == 400
    assert "doctor profile" in r.get_json()["message"]


def test_order_validation_and_unknown_refs(client, auth_header):
    h = auth_header(client, "doctor")
    r = client.post("/api/lab/orders", headers=h, json={})
    assert r.status_code == 400
    r = client.post("/api/lab/orders", headers=h, json={"patient_id": 9999, "lab_test_id": 9999})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and "patient_id" in errors and "lab_test_id" in errors


@pytest.mark.parametrize("role", ["receptionist", "nurse", "pharmacist", "billing_staff"])
def test_only_doctor_orders_tests(client, auth_header, patient_id, lab_test_type, role):
    r = client.post("/api/lab/orders", headers=auth_header(client, role),
                     json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]})
    assert r.status_code == 403


def test_full_lab_workflow(client, auth_header, doctor_setup, patient_id, lab_test_type):
    h_doc = auth_header(client, "doctor")
    h_lab = auth_header(client, "lab_technician")

    order = client.post("/api/lab/orders", headers=h_doc,
                         json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"]

    r = client.put(f"/api/lab/orders/{order['id']}/status", headers=h_lab, json={"status": "sample_collected"})
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "sample_collected"

    r = client.put(f"/api/lab/orders/{order['id']}/status", headers=h_lab, json={"status": "processing"})
    assert r.status_code == 200

    r = client.post(f"/api/lab/orders/{order['id']}/result", headers=h_lab,
                     json={"result_value": "WBC 7.2 x10^9/L - normal", "is_abnormal": False})
    assert r.status_code == 201 and r.get_json()["data"]["status"] == "result_entered"

    r = client.post(f"/api/lab/orders/{order['id']}/review", headers=h_doc,
                     json={"reviewer_notes": "Looks fine, no action needed"})
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "reviewed"
    assert r.get_json()["data"]["result"]["reviewer_notes"] == "Looks fine, no action needed"


def test_cannot_enter_result_twice(client, auth_header, doctor_setup, patient_id, lab_test_type):
    h_doc = auth_header(client, "doctor")
    h_lab = auth_header(client, "lab_technician")
    order = client.post("/api/lab/orders", headers=h_doc,
                         json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"]
    client.post(f"/api/lab/orders/{order['id']}/result", headers=h_lab, json={"result_value": "Normal"})
    r = client.post(f"/api/lab/orders/{order['id']}/result", headers=h_lab, json={"result_value": "Again"})
    assert r.status_code == 400


def test_cannot_review_without_result(client, auth_header, doctor_setup, patient_id, lab_test_type):
    h_doc = auth_header(client, "doctor")
    order = client.post("/api/lab/orders", headers=h_doc,
                         json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"]
    r = client.post(f"/api/lab/orders/{order['id']}/review", headers=h_doc, json={})
    assert r.status_code == 400


def test_lab_tech_cannot_review(client, auth_header, doctor_setup, patient_id, lab_test_type):
    h_doc = auth_header(client, "doctor")
    h_lab = auth_header(client, "lab_technician")
    order = client.post("/api/lab/orders", headers=h_doc,
                         json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"]
    client.post(f"/api/lab/orders/{order['id']}/result", headers=h_lab, json={"result_value": "Normal"})
    r = client.post(f"/api/lab/orders/{order['id']}/review", headers=h_lab, json={})
    assert r.status_code == 403


def test_get_and_filter_orders(client, auth_header, doctor_setup, patient_id, lab_test_type):
    h_doc = auth_header(client, "doctor")
    client.post("/api/lab/orders", headers=h_doc, json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]})
    r = client.get(f"/api/lab/orders?patient_id={patient_id}&status=ordered", headers=h_doc)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1
    assert client.get("/api/lab/orders/9999", headers=h_doc).status_code == 404
