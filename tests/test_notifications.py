from datetime import timedelta

import pytest

from app.utils.timeutils import local_today


def _notes(client, auth_header, role, **params):
    q = "&".join(f"{k}={v}" for k, v in {"per_page": 100, **params}.items())
    return client.get(f"/api/notifications?{q}", headers=auth_header(client, role)).get_json()["data"]


def _types(data):
    return [n["type"] for n in data["items"]]


def _medicine(client, auth_header, name="Cetirizine", reorder=10, stock=None, expiry="2028-12-31"):
    h = auth_header(client, "admin")
    med = client.post("/api/pharmacy/medicines", headers=h, json={"name": name, "unit": "tablet", "reorder_level": reorder}).get_json()["data"]
    if stock is not None:
        client.post(f"/api/pharmacy/medicines/{med['id']}/batches", headers=h,
                    json={"batch_number": "B1", "expiry_date": expiry, "purchase_quantity": stock})
    return med


# ------------------------------------------------------------ event notifications --

def test_lab_result_notifies_the_ordering_doctor_only(client, auth_header, scenario):
    scenario(discharge=False)
    doctor = _notes(client, auth_header, "doctor")
    assert _types(doctor) == ["lab_result"]
    note = doctor["items"][0]
    assert "ABNORMAL" in note["title"] and note["severity"] == "warning" and note["is_read"] is False
    assert "Ramesh Kulkarni" in note["message"] and "Complete Blood Count" in note["message"]
    for role in ("nurse", "lab_technician", "receptionist", "billing_staff"):
        assert "lab_result" not in _types(_notes(client, auth_header, role))


def test_normal_lab_result_is_info_not_warning(client, auth_header, doctor_setup, patient_id, lab_test_type):
    order = client.post("/api/lab/orders", headers=auth_header(client, "doctor"),
                        json={"patient_id": patient_id, "lab_test_id": lab_test_type["id"]}).get_json()["data"]
    client.post(f"/api/lab/orders/{order['id']}/result", headers=auth_header(client, "lab_technician"),
                json={"result_value": "All normal", "is_abnormal": False})
    note = _notes(client, auth_header, "doctor")["items"][0]
    assert note["severity"] == "info" and "ABNORMAL" not in note["title"]


def test_discharge_notifies_billing_and_reception(client, auth_header, scenario):
    scenario(discharge=True)
    for role in ("billing_staff", "receptionist"):
        data = _notes(client, auth_header, role)
        assert "patient_discharge" in _types(data)
        assert "Ramesh Kulkarni" in next(n for n in data["items"] if n["type"] == "patient_discharge")["message"]
    for role in ("pharmacist", "lab_technician"):
        assert "patient_discharge" not in _types(_notes(client, auth_header, role))


def test_doctor_discharge_with_summary_also_notifies(client, auth_header, scenario):
    ids = scenario(discharge=False)
    client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"),
                json={"diagnosis": "Pneumonia", "treatment_summary": "Antibiotics given."})
    assert "patient_discharge" in _types(_notes(client, auth_header, "billing_staff"))


# --------------------------------------------------------------- low medicine stock --

def test_low_stock_alert_for_pharmacist_only(client, auth_header):
    _medicine(client, auth_header, reorder=50, stock=5)
    data = _notes(client, auth_header, "pharmacist")
    note = next(n for n in data["items"] if n["type"] == "low_stock")
    assert note["severity"] == "warning" and "only 5" in note["message"] and "reorder level 50" in note["message"]
    for role in ("doctor", "nurse", "billing_staff", "lab_technician", "receptionist"):
        assert "low_stock" not in _types(_notes(client, auth_header, role))


def test_out_of_stock_is_critical(client, auth_header):
    _medicine(client, auth_header, reorder=10, stock=None)   # catalog entry, no batches at all
    note = next(n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "low_stock")
    assert note["severity"] == "critical" and "OUT OF STOCK" in note["message"]


def test_stock_above_reorder_level_creates_no_alert(client, auth_header):
    _medicine(client, auth_header, reorder=10, stock=100)
    assert "low_stock" not in _types(_notes(client, auth_header, "pharmacist"))


def test_alert_resolves_on_restock_and_returns_unread_when_low_again(client, auth_header, doctor_setup, patient_id):
    med = _medicine(client, auth_header, reorder=10, stock=12)
    h_doc, h_pharm, h_admin = auth_header(client, "doctor"), auth_header(client, "pharmacist"), auth_header(client, "admin")

    def issue(qty):
        presc = client.post("/api/prescriptions", headers=h_doc, json={
            "patient_id": patient_id, "items": [{"medicine_id": med["id"], "dosage": "x", "quantity": qty}]}).get_json()["data"]
        client.post(f"/api/prescriptions/{presc['id']}/issue", headers=h_pharm)

    assert "low_stock" not in _types(_notes(client, auth_header, "pharmacist"))
    issue(5)                                                    # 12 -> 7, below reorder level 10
    note = next(n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "low_stock")
    client.post(f"/api/notifications/{note['id']}/read", headers=h_pharm)
    assert _notes(client, auth_header, "pharmacist", unread="true")["total"] == 0

    client.post(f"/api/pharmacy/medicines/{med['id']}/batches", headers=h_admin,
                json={"batch_number": "B2", "expiry_date": "2028-12-31", "purchase_quantity": 100})
    assert "low_stock" not in _types(_notes(client, auth_header, "pharmacist"))   # condition gone -> resolved

    issue(100)                                                  # 107 -> 7 again
    again = [n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "low_stock"]
    assert len(again) == 1 and again[0]["id"] == note["id"] and again[0]["is_read"] is False   # re-notified


# ------------------------------------------------------------------ medicine expiry --

def test_batch_expiring_soon_is_flagged(client, auth_header):
    soon = (local_today() + timedelta(days=20)).isoformat()
    _medicine(client, auth_header, stock=100, expiry=soon)
    note = next(n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "medicine_expiry")
    assert note["severity"] == "warning" and "expire in" in note["message"] and soon in note["message"]


def test_batch_within_a_week_is_critical(client, auth_header):
    _medicine(client, auth_header, stock=100, expiry=(local_today() + timedelta(days=3)).isoformat())
    note = next(n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "medicine_expiry")
    assert note["severity"] == "critical"


def test_batch_far_from_expiry_is_not_flagged(client, auth_header):
    _medicine(client, auth_header, stock=100, expiry=(local_today() + timedelta(days=90)).isoformat())
    assert "medicine_expiry" not in _types(_notes(client, auth_header, "pharmacist"))


def test_expired_stock_is_critical_and_not_counted_as_available(client, auth_header):
    from app.extensions import db
    from app.models.pharmacy import MedicineBatch
    med = _medicine(client, auth_header, reorder=10, stock=100)
    batch = MedicineBatch.query.filter_by(medicine_id=med["id"]).first()
    batch.expiry_date = local_today() - timedelta(days=2)
    db.session.commit()
    notes = _notes(client, auth_header, "pharmacist")["items"]
    expired = next(n for n in notes if n["type"] == "medicine_expiry")
    assert expired["severity"] == "critical" and "EXPIRED" in expired["title"]
    # expired units are not usable stock, so the medicine is also out of stock
    assert any(n["type"] == "low_stock" and "OUT OF STOCK" in n["message"] for n in notes)


def test_empty_expired_batch_is_ignored(client, auth_header, doctor_setup, patient_id):
    """A batch with 0 units left needs no expiry warning."""
    med = _medicine(client, auth_header, reorder=0, stock=5, expiry=(local_today() + timedelta(days=5)).isoformat())
    presc = client.post("/api/prescriptions", headers=auth_header(client, "doctor"), json={
        "patient_id": patient_id, "items": [{"medicine_id": med["id"], "dosage": "x", "quantity": 5}]}).get_json()["data"]
    client.post(f"/api/prescriptions/{presc['id']}/issue", headers=auth_header(client, "pharmacist"))
    assert "medicine_expiry" not in _types(_notes(client, auth_header, "pharmacist"))


# ----------------------------------------------------------------- payment pending --

def test_unpaid_bill_notifies_billing_and_clears_when_paid(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = client.post("/api/bills", headers=h, json={"patient_id": patient_id}).get_json()["data"]
    note = next(n for n in _notes(client, auth_header, "billing_staff")["items"] if n["type"] == "payment_pending")
    assert bill["bill_number"] in note["message"] and "2400.00 outstanding" in note["message"]
    assert "payment_pending" not in _types(_notes(client, auth_header, "pharmacist"))

    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 1000, "method": "cash"})
    updated = next(n for n in _notes(client, auth_header, "billing_staff")["items"] if n["type"] == "payment_pending")
    assert "1400.00 outstanding" in updated["message"] and updated["id"] == note["id"]   # same alert, text updated

    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 1400, "method": "card"})
    assert "payment_pending" not in _types(_notes(client, auth_header, "billing_staff"))


def test_payment_pending_respects_the_age_setting(app, client, auth_header, scenario, patient_id):
    scenario()
    client.post("/api/bills", headers=auth_header(client, "billing_staff"), json={"patient_id": patient_id})
    app.config["PAYMENT_PENDING_AFTER_DAYS"] = 7          # a brand-new bill is not "pending" yet
    assert "payment_pending" not in _types(_notes(client, auth_header, "billing_staff"))


# ------------------------------------------------------------------ no duplicates --

def test_refreshing_many_times_creates_no_duplicates(client, auth_header, scenario, patient_id):
    scenario()
    client.post("/api/bills", headers=auth_header(client, "billing_staff"), json={"patient_id": patient_id})
    _medicine(client, auth_header, reorder=50, stock=5)
    admin = auth_header(client, "admin")
    first = client.post("/api/notifications/refresh", headers=admin).get_json()["data"]
    second = client.post("/api/notifications/refresh", headers=admin).get_json()["data"]
    assert first["created"] == 2                                       # payment pending + low stock
    assert second == {"created": 0, "updated": 0, "resolved": 0}       # same conditions -> nothing new
    all_keys = [n["id"] for n in _notes(client, auth_header, "admin")["items"]]
    assert len(all_keys) == len(set(all_keys))


# ----------------------------------------------------------------- read / unread --

def test_mark_read_and_unread_count(client, auth_header, scenario):
    scenario(discharge=True)
    h = auth_header(client, "billing_staff")
    data = _notes(client, auth_header, "billing_staff")
    total = data["unread_count"]
    assert total >= 1
    r = client.post(f"/api/notifications/{data['items'][0]['id']}/read", headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["is_read"] is True
    assert client.get("/api/notifications/unread-count", headers=h).get_json()["data"]["unread_count"] == total - 1
    client.post(f"/api/notifications/{data['items'][0]['id']}/read", headers=h)     # double click is harmless
    assert client.get("/api/notifications/unread-count", headers=h).get_json()["data"]["unread_count"] == total - 1


def test_read_state_is_per_user_not_shared(client, auth_header):
    admin = auth_header(client, "admin")
    client.post("/api/users", headers=admin, json={"username": "pharma2", "email": "p2@test.com", "password": "Secret123",
                                                    "full_name": "Second Pharmacist", "role": "pharmacist"})
    token2 = client.post("/api/auth/login", json={"username": "pharma2", "password": "Secret123"}).get_json()["data"]["access_token"]
    h2 = {"Authorization": f"Bearer {token2}"}
    _medicine(client, auth_header, reorder=50, stock=5)
    h1 = auth_header(client, "pharmacist")
    note = next(n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "low_stock")
    client.post(f"/api/notifications/{note['id']}/read", headers=h1)
    assert client.get("/api/notifications/unread-count", headers=h1).get_json()["data"]["unread_count"] == 0
    assert client.get("/api/notifications/unread-count", headers=h2).get_json()["data"]["unread_count"] == 1   # pharma2 has not read it


def test_cannot_read_someone_elses_notification(client, auth_header):
    _medicine(client, auth_header, reorder=50, stock=5)
    note = next(n for n in _notes(client, auth_header, "pharmacist")["items"] if n["type"] == "low_stock")
    assert client.post(f"/api/notifications/{note['id']}/read", headers=auth_header(client, "doctor")).status_code == 404
    assert client.post("/api/notifications/9999/read", headers=auth_header(client, "doctor")).status_code == 404


def test_read_all(client, auth_header, scenario):
    scenario(discharge=True)
    h = auth_header(client, "billing_staff")
    n = _notes(client, auth_header, "billing_staff")["unread_count"]
    assert client.post("/api/notifications/read-all", headers=h).get_json()["data"]["marked"] == n
    assert _notes(client, auth_header, "billing_staff", unread="true")["total"] == 0
    assert client.post("/api/notifications/read-all", headers=h).get_json()["data"]["marked"] == 0


def test_admin_sees_everyones_notifications(client, auth_header, scenario):
    scenario(discharge=True)
    _medicine(client, auth_header, reorder=50, stock=5)
    types = set(_types(_notes(client, auth_header, "admin")))
    assert {"lab_result", "patient_discharge", "low_stock"} <= types


def test_filters_and_pagination(client, auth_header, scenario):
    scenario(discharge=True)
    _medicine(client, auth_header, reorder=50, stock=5)
    h = auth_header(client, "admin")
    assert all(n["type"] == "low_stock" for n in _notes(client, auth_header, "admin", type="low_stock")["items"])
    page = client.get("/api/notifications?per_page=1&page=1", headers=h).get_json()["data"]
    assert len(page["items"]) == 1 and page["pages"] == page["total"]
    assert client.get("/api/notifications?type=bogus", headers=h).status_code == 400
    assert client.get("/api/notifications?page=0", headers=h).status_code == 400


def test_newest_first(client, auth_header, scenario):
    scenario(discharge=True)
    dates = [n["created_at"] for n in _notes(client, auth_header, "admin")["items"]]
    assert dates == sorted(dates, reverse=True)


def test_notifications_need_a_token(client):
    for path in ("/api/notifications", "/api/notifications/unread-count"):
        assert client.get(path).status_code == 401
    assert client.post("/api/notifications/read-all").status_code == 401


@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse", "lab_technician", "pharmacist", "billing_staff"])
def test_only_admin_can_force_refresh(client, auth_header, role):
    assert client.post("/api/notifications/refresh", headers=auth_header(client, role)).status_code == 403


def test_notification_failure_never_breaks_the_real_action(client, auth_header, scenario, monkeypatch):
    """A broken notification must not stop a patient being discharged."""
    ids = scenario(discharge=False)
    def boom(*a, **k):
        raise RuntimeError("notification table unavailable")
    monkeypatch.setattr("app.services.notification_service.Notification", boom)
    r = client.post(f"/api/admissions/{ids['admission_id']}/discharge", headers=auth_header(client, "nurse"))
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "discharged"
