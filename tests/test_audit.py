import pytest

from app.middleware.audit import AUDIT_EXEMPT, AUDIT_RULES


def _logs(client, auth_header, **params):
    q = "&".join(f"{k}={v}" for k, v in {"per_page": 100, **params}.items())
    return client.get(f"/api/audit-logs?{q}", headers=auth_header(client, "admin")).get_json()["data"]["items"]


def test_every_write_endpoint_has_an_audit_rule(app):
    """If you add a POST/PUT/DELETE endpoint, add it to AUDIT_RULES (or AUDIT_EXEMPT with a reason)."""
    missing = [(m, r.rule) for r in app.url_map.iter_rules() for m in r.methods & {"POST", "PUT", "DELETE", "PATCH"}
               if r.rule.startswith("/api") and (m, r.rule) not in AUDIT_RULES and (m, r.rule) not in AUDIT_EXEMPT]
    assert missing == []


def test_no_audit_rule_points_at_a_missing_endpoint(app):
    real = {(m, r.rule) for r in app.url_map.iter_rules() for m in r.methods}
    assert [k for k in AUDIT_RULES if k not in real] == []


def test_successful_login_is_logged(client, auth_header):
    auth_header(client, "doctor")
    entry = _logs(client, auth_header, action="auth.login", username="t_doctor")[0]
    assert entry["role"] == "doctor" and entry["user_id"] is not None and "logged in" in entry["description"]


def test_failed_login_is_logged_without_password(client, auth_header):
    client.post("/api/auth/login", json={"username": "t_doctor", "password": "SuperSecret-Wrong1"})
    client.post("/api/auth/login", json={"username": "ghost\nuser", "password": "x"})
    entries = _logs(client, auth_header, action="auth.login_failed")
    assert len(entries) == 2
    assert all(e["user_id"] is None and e["role"] is None for e in entries)
    assert "SuperSecret-Wrong1" not in str(entries)
    assert not any("\n" in (e["username"] or "") for e in entries)  # control characters stripped


def test_action_is_logged_with_user_role_entity_and_description(client, auth_header):
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json={
        "full_name": "Ramesh Kulkarni", "date_of_birth": "1990-05-15", "gender": "male", "phone": "+919876543210"})
    patient = r.get_json()["data"]
    entry = _logs(client, auth_header, action="patient.create")[0]
    assert entry["username"] == "t_receptionist" and entry["role"] == "receptionist"
    assert entry["entity_type"] == "Patient" and entry["entity_id"] == patient["id"]
    assert patient["patient_code"] in entry["description"] and "Ramesh Kulkarni" in entry["description"]
    assert entry["ip_address"] and entry["created_at"]


def test_failed_requests_are_not_logged(client, auth_header):
    client.post("/api/patients", headers=auth_header(client, "receptionist"), json={})                      # 400
    client.post("/api/users", headers=auth_header(client, "receptionist"), json={"username": "x"})          # 403
    client.put("/api/patients/9999", headers=auth_header(client, "receptionist"), json={"phone": "+911234567"})  # 404
    assert _logs(client, auth_header, action="patient.create") == []
    assert _logs(client, auth_header, action="user.create") == []
    assert _logs(client, auth_header, action="patient.update") == []


def test_read_requests_are_not_logged(client, auth_header):
    admin, h = auth_header(client, "admin"), auth_header(client, "receptionist")   # log in once; logins are audited too
    count = lambda: client.get("/api/audit-logs?per_page=1", headers=admin).get_json()["data"]["total"]
    before = count()
    client.get("/api/patients", headers=h)
    client.get("/api/appointments", headers=h)
    assert count() == before


def test_entity_id_from_url_and_nested_data(client, auth_header, scenario, patient_id):
    scenario()
    bill = client.post("/api/bills", headers=auth_header(client, "billing_staff"), json={"patient_id": patient_id}).get_json()["data"]
    pay = client.post(f"/api/bills/{bill['id']}/payments", headers=auth_header(client, "billing_staff"),
                      json={"amount": 500, "method": "upi"}).get_json()["data"]["payment"]
    bill_entry = _logs(client, auth_header, action="bill.create")[0]
    pay_entry = _logs(client, auth_header, action="payment.create")[0]
    assert bill_entry["entity_type"] == "Bill" and bill_entry["entity_id"] == bill["id"]
    assert pay_entry["entity_type"] == "Payment" and pay_entry["entity_id"] == pay["id"]   # id read from data.payment.id
    assert pay["receipt_number"] in pay_entry["description"] and "500" in pay_entry["description"]


def test_whole_patient_story_is_traceable(client, auth_header, scenario, patient_id):
    """Matches the requirement-document example: created -> doctor assigned -> lab ordered -> result -> prescription -> discharged."""
    scenario()
    actions = [e["action"] for e in _logs(client, auth_header)]
    for expected in ("patient.create", "appointment.book", "appointment.complete", "admission.create", "lab_order.create",
                     "lab_order.result_entered", "prescription.create", "prescription.issue", "admission.discharge"):
        assert expected in actions, f"{expected} missing from audit trail"


def test_per_entity_history(client, auth_header, patient_id):
    h = auth_header(client, "receptionist")
    client.put(f"/api/patients/{patient_id}", headers=h, json={"phone": "+919999999999"})
    client.post(f"/api/patients/{patient_id}/visits", headers=h, json={"visit_type": "opd", "reason": "Fever"})
    history = _logs(client, auth_header, entity_type="Patient", entity_id=patient_id)
    assert [e["action"] for e in history] == ["patient.visit_add", "patient.update", "patient.create"]  # newest first


def test_username_and_role_are_snapshots(client, auth_header, patient_id):
    """Changing a user's role later must not rewrite history."""
    admin = auth_header(client, "admin")
    uid = client.get("/api/auth/me", headers=auth_header(client, "receptionist")).get_json()["data"]["id"]
    client.post("/api/patients", headers=auth_header(client, "receptionist"), json={
        "full_name": "Sita Devi", "date_of_birth": "1992-01-01", "gender": "female", "phone": "+919876500002"})
    client.put(f"/api/users/{uid}", headers=admin, json={"role": "nurse", "full_name": "Renamed"})
    entry = _logs(client, auth_header, action="patient.create", user_id=uid)[0]
    assert entry["role"] == "receptionist"
    changed = _logs(client, auth_header, action="user.update")[0]
    assert "role" in changed["description"] and "full_name" in changed["description"]


def test_password_values_never_appear_in_logs(client, auth_header):
    admin = auth_header(client, "admin")
    uid = client.get("/api/auth/me", headers=auth_header(client, "nurse")).get_json()["data"]["id"]
    client.post(f"/api/users/{uid}/reset-password", headers=admin, json={"new_password": "TopSecret999"})
    client.post("/api/auth/change-password", headers=auth_header(client, "doctor"),
                json={"old_password": "Test1234", "new_password": "AnotherSecret77"})
    dump = str(_logs(client, auth_header))
    assert "TopSecret999" not in dump and "AnotherSecret77" not in dump
    assert _logs(client, auth_header, action="user.reset_password") and _logs(client, auth_header, action="auth.change_password")


def test_audit_failure_never_breaks_the_real_request(client, auth_header, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("audit table unavailable")
    monkeypatch.setattr("app.middleware.audit.audit_service.record", boom)
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json={
        "full_name": "Still Created", "date_of_birth": "1990-01-01", "gender": "male", "phone": "+919876500003"})
    assert r.status_code == 201


# --------------------------------------------------------------- the viewer API --

@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse", "lab_technician", "pharmacist", "billing_staff"])
def test_only_admin_can_read_audit_logs(client, auth_header, role):
    h = auth_header(client, role)
    assert client.get("/api/audit-logs", headers=h).status_code == 403
    assert client.get("/api/audit-logs/actions", headers=h).status_code == 403


def test_audit_logs_need_a_token(client):
    assert client.get("/api/audit-logs").status_code == 401


def test_audit_log_is_read_only(client, auth_header):
    h = auth_header(client, "admin")
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/audit-logs", headers=h).status_code == 405
        assert getattr(client, method)("/api/audit-logs/1", headers=h).status_code in (404, 405)


def test_filters_and_pagination(client, auth_header, patient_id):
    admin = auth_header(client, "admin")
    h = auth_header(client, "receptionist")
    for i in range(3):
        client.post(f"/api/patients/{patient_id}/visits", headers=h, json={"visit_type": "opd", "reason": f"Visit {i}"})
    page = client.get("/api/audit-logs?action=patient.visit_add&per_page=2&page=1", headers=admin).get_json()["data"]
    assert page["total"] == 3 and len(page["items"]) == 2 and page["pages"] == 2
    assert client.get("/api/audit-logs?q=Registered", headers=admin).get_json()["data"]["total"] == 1
    assert client.get("/api/audit-logs?role=receptionist&action=patient.create", headers=admin).get_json()["data"]["total"] == 1
    actions = client.get("/api/audit-logs/actions", headers=admin).get_json()["data"]
    assert "patient.create" in actions and actions == sorted(actions)


def test_date_filters(client, auth_header, patient_id):
    from app.utils.timeutils import local_today
    admin = auth_header(client, "admin")
    today = local_today().isoformat()
    assert client.get(f"/api/audit-logs?date_from={today}&date_to={today}&action=patient.create", headers=admin).get_json()["data"]["total"] == 1
    assert client.get("/api/audit-logs?date_to=2020-01-01", headers=admin).get_json()["data"]["total"] == 0
    assert client.get("/api/audit-logs?date_from=2999-01-01", headers=admin).get_json()["data"]["total"] == 0


def test_audit_validation(client, auth_header):
    admin = auth_header(client, "admin")
    r = client.get("/api/audit-logs?date_from=10-10-2026&user_id=abc&page=0", headers=admin)
    assert r.status_code == 400 and {"date_from", "user_id", "page"} <= set(r.get_json()["errors"])
