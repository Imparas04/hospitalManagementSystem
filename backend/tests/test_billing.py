from datetime import datetime, timedelta
from io import BytesIO

import pytest
from pypdf import PdfReader


def _bill(client, auth_header, patient_id, **extra):
    return client.post("/api/bills", headers=auth_header(client, "billing_staff"),
                       json={"patient_id": patient_id, **extra})


def _pdf_text(resp):
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(resp.data)).pages)


# ------------------------------------------------------------ automatic billing --

def test_preview_lists_everything_billable(client, auth_header, scenario, patient_id):
    scenario()
    r = client.get(f"/api/bills/preview?patient_id={patient_id}", headers=auth_header(client, "billing_staff"))
    data = r.get_json()["data"]
    assert r.status_code == 200
    assert sorted(i["category"] for i in data["items"]) == ["bed", "consultation", "laboratory", "medicine"]
    assert data["subtotal"] == 2400.0


def test_preview_does_not_save_anything(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    client.get(f"/api/bills/preview?patient_id={patient_id}", headers=h)
    assert client.get("/api/bills", headers=h).get_json()["data"]["total"] == 0


def test_generate_bill_adds_up_all_charges(client, auth_header, scenario, patient_id):
    scenario()
    r = _bill(client, auth_header, patient_id)
    d = r.get_json()["data"]
    assert r.status_code == 201
    assert d["bill_number"].startswith("B") and d["status"] == "unpaid"
    assert d["subtotal"] == 2400.0 and d["total_amount"] == 2400.0 and d["outstanding_amount"] == 2400.0
    by_cat = {i["category"]: i for i in d["items"]}
    assert by_cat["consultation"]["amount"] == 600.0
    assert by_cat["bed"]["amount"] == 1500.0 and by_cat["bed"]["quantity"] == 1
    assert by_cat["laboratory"]["amount"] == 250.0
    assert by_cat["medicine"]["quantity"] == 4 and by_cat["medicine"]["amount"] == 50.0


def test_discount_then_tax_order_of_calculation(client, auth_header, scenario, patient_id):
    """2400 - 10% (240) = 2160 ; tax 5% of 2160 = 108 ; total 2268."""
    scenario()
    d = _bill(client, auth_header, patient_id, discount_percent=10, tax_percent=5).get_json()["data"]
    assert d["discount_amount"] == 240.0 and d["tax_amount"] == 108.0 and d["total_amount"] == 2268.0


def test_money_is_rounded_to_two_places(client, auth_header, patient_id):
    """33.33 x 3 = 99.99 ; 12.5% discount = 12.49875 -> 12.50 ; taxable 87.49 ; 5% tax = 4.3745 -> 4.37 ; total 91.86"""
    d = _bill(client, auth_header, patient_id, discount_percent=12.5, tax_percent=5,
              other_services=[{"description": "Ambulance charge", "quantity": 3, "unit_price": 33.33}]).get_json()["data"]
    assert d["subtotal"] == 99.99 and d["discount_amount"] == 12.5
    assert d["tax_amount"] == 4.37 and d["total_amount"] == 91.86


def test_nothing_is_billed_twice(client, auth_header, scenario, patient_id):
    scenario()
    assert _bill(client, auth_header, patient_id).status_code == 201
    r = _bill(client, auth_header, patient_id)
    assert r.status_code == 409 and "Nothing to bill" in r.get_json()["message"]


def test_bill_by_patient_code(client, auth_header, scenario, patient_id):
    scenario()
    code = client.get(f"/api/patients/{patient_id}", headers=auth_header(client, "receptionist")).get_json()["data"]["patient_code"]
    r = client.post("/api/bills", headers=auth_header(client, "billing_staff"), json={"patient_code": code})
    assert r.status_code == 201 and r.get_json()["data"]["patient_code"] == code


def test_bed_charge_waits_until_discharge(client, auth_header, scenario, patient_id):
    scenario(discharge=False)
    items = client.get(f"/api/bills/preview?patient_id={patient_id}",
                       headers=auth_header(client, "billing_staff")).get_json()["data"]["items"]
    assert "bed" not in [i["category"] for i in items]


def test_bed_charge_counts_every_started_day(client, app, auth_header, scenario, patient_id):
    """A 2.5 day stay is billed as 3 days."""
    from app.extensions import db
    from app.models.bed import Admission
    ids = scenario()
    adm = db.session.get(Admission, ids["admission_id"])
    adm.admission_date = adm.discharge_date - timedelta(days=2, hours=12)
    db.session.commit()
    d = _bill(client, auth_header, patient_id).get_json()["data"]
    bed = next(i for i in d["items"] if i["category"] == "bed")
    assert bed["quantity"] == 3 and bed["amount"] == 4500.0


def test_medicine_is_billed_in_rounds_only_for_new_quantity(client, auth_header, scenario, patient_id):
    ids = scenario(qty=30)  # only 20 in stock -> pharmacy issues 20
    h_admin, h_pharm = auth_header(client, "admin"), auth_header(client, "pharmacist")
    first = _bill(client, auth_header, patient_id).get_json()["data"]
    assert next(i for i in first["items"] if i["category"] == "medicine")["quantity"] == 20

    client.post(f"/api/pharmacy/medicines/{ids['medicine_id']}/batches", headers=h_admin,
                json={"batch_number": "B2", "expiry_date": "2027-12-31", "purchase_quantity": 50})
    client.post(f"/api/prescriptions/{ids['prescription_id']}/issue", headers=h_pharm)  # issues the remaining 10

    second = _bill(client, auth_header, patient_id).get_json()["data"]
    assert [i["category"] for i in second["items"]] == ["medicine"]
    assert second["items"][0]["quantity"] == 10 and second["items"][0]["amount"] == 125.0


def test_unissued_medicine_and_unfinished_lab_are_not_billed(client, auth_header, doctor_setup, patient_id):
    admin, doc = auth_header(client, "admin"), auth_header(client, "doctor")
    test = client.post("/api/lab/tests", headers=admin, json={"name": "LFT", "code": "LFT", "price": 400}).get_json()["data"]
    client.post("/api/lab/orders", headers=doc, json={"patient_id": patient_id, "lab_test_id": test["id"]})  # no result yet
    med = client.post("/api/pharmacy/medicines", headers=admin, json={"name": "M1", "unit": "tablet"}).get_json()["data"]
    client.post("/api/prescriptions", headers=doc, json={
        "patient_id": patient_id, "items": [{"medicine_id": med["id"], "dosage": "x", "quantity": 5}]})  # never issued
    assert _bill(client, auth_header, patient_id).status_code == 409


def test_generate_bill_validation(client, auth_header):
    h = auth_header(client, "billing_staff")
    assert client.post("/api/bills", headers=h, json={}).status_code == 400
    r = client.post("/api/bills", headers=h, json={"patient_id": 1, "discount_percent": 150, "tax_percent": -1,
                                                   "other_services": [{"description": "", "quantity": 0}]})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and {"discount_percent", "tax_percent", "other_services"} <= set(errors)
    assert client.post("/api/bills", headers=h, json={"patient_id": 9999}).status_code == 404
    assert client.post("/api/bills", headers=h, json={"patient_code": "P0000"}).status_code == 404


# ------------------------------------------------------------ items / adjust --

def test_add_other_service_to_existing_bill(client, auth_header, scenario, patient_id):
    scenario()
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    r = client.post(f"/api/bills/{bill['id']}/items", headers=auth_header(client, "billing_staff"),
                    json={"description": "Dressing kit", "quantity": 2, "unit_price": 75})
    assert r.status_code == 201 and r.get_json()["data"]["total_amount"] == 2550.0


def test_adjust_discount_and_tax_before_payment(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    r = client.put(f"/api/bills/{bill['id']}/adjust", headers=h, json={"discount_percent": 10, "tax_percent": 5})
    assert r.status_code == 200 and r.get_json()["data"]["total_amount"] == 2268.0
    assert client.put(f"/api/bills/{bill['id']}/adjust", headers=h, json={}).status_code == 400
    assert client.put(f"/api/bills/{bill['id']}/adjust", headers=h, json={"discount_percent": 101}).status_code == 400


def test_adjust_blocked_after_a_payment(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 100, "method": "cash"})
    r = client.put(f"/api/bills/{bill['id']}/adjust", headers=h, json={"discount_percent": 50})
    assert r.status_code == 400


def test_cannot_add_items_to_fully_paid_bill(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 2400, "method": "cash"})
    r = client.post(f"/api/bills/{bill['id']}/items", headers=h, json={"description": "Late charge", "unit_price": 10})
    assert r.status_code == 400


# ------------------------------------------------------------------ payments --

def test_partial_payments_with_multiple_methods(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]

    r1 = client.post(f"/api/bills/{bill['id']}/payments", headers=h,
                     json={"amount": 1000, "method": "cash"})
    d1 = r1.get_json()["data"]
    assert r1.status_code == 201 and d1["bill"]["status"] == "partially_paid"
    assert d1["bill"]["outstanding_amount"] == 1400.0 and d1["payment"]["receipt_number"].startswith("R")

    r2 = client.post(f"/api/bills/{bill['id']}/payments", headers=h,
                     json={"amount": 1400, "method": "upi", "reference": "UPI-98765"})
    d2 = r2.get_json()["data"]
    assert d2["bill"]["status"] == "paid" and d2["bill"]["outstanding_amount"] == 0.0
    assert d1["payment"]["receipt_number"] != d2["payment"]["receipt_number"]

    full = client.get(f"/api/bills/{bill['id']}", headers=h).get_json()["data"]
    assert [p["method"] for p in full["payments"]] == ["cash", "upi"]


def test_overpayment_and_payment_on_paid_bill_rejected(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    r = client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 5000, "method": "cash"})
    assert r.status_code == 400 and "outstanding" in r.get_json()["message"]
    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 2400, "method": "card"})
    r = client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 1, "method": "cash"})
    assert r.status_code == 400 and "fully paid" in r.get_json()["message"]


def test_payment_validation(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    for bad in ({}, {"amount": 0, "method": "cash"}, {"amount": -5, "method": "cash"},
                {"amount": 10.555, "method": "cash"}, {"amount": 10, "method": "bitcoin"}):
        assert client.post(f"/api/bills/{bill['id']}/payments", headers=h, json=bad).status_code == 400
    assert client.post("/api/bills/9999/payments", headers=h, json={"amount": 1, "method": "cash"}).status_code == 404


def test_receipt_json_shows_balance_after_that_payment(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    p1 = client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 1000, "method": "cash"}).get_json()["data"]["payment"]
    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 500, "method": "card"})
    r = client.get(f"/api/payments/{p1['id']}/receipt", headers=h).get_json()["data"]
    assert r["balance_after_payment"] == 1400.0  # balance right after the FIRST payment, not today's balance
    assert client.get("/api/payments/9999/receipt", headers=h).status_code == 404


def test_outstanding_bills_and_list_filters(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    out = client.get("/api/bills/outstanding", headers=h).get_json()["data"]
    assert out["count"] == 1 and out["total_outstanding"] == 2400.0
    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 2400, "method": "cash"})
    assert client.get("/api/bills/outstanding", headers=h).get_json()["data"]["count"] == 0
    assert client.get("/api/bills?status=paid", headers=h).get_json()["data"]["total"] == 1
    assert client.get("/api/bills?status=unpaid", headers=h).get_json()["data"]["total"] == 0
    assert client.get(f"/api/bills?patient_id={patient_id}", headers=h).get_json()["data"]["total"] == 1
    assert client.get("/api/bills?page=0", headers=h).status_code == 400


def test_bill_numbers_are_unique_and_increasing(client, auth_header, patient_id):
    h = auth_header(client, "billing_staff")
    nums = [_bill(client, auth_header, patient_id, other_services=[{"description": f"Service {i}", "unit_price": 10}])
            .get_json()["data"]["bill_number"] for i in range(3)]
    assert len(set(nums)) == 3 and nums == sorted(nums)


# ----------------------------------------------------------------------- RBAC --

@pytest.mark.parametrize("role", ["receptionist", "doctor", "nurse", "lab_technician", "pharmacist"])
def test_other_roles_cannot_use_billing(client, auth_header, patient_id, role):
    h = auth_header(client, role)
    assert client.get("/api/bills", headers=h).status_code == 403
    assert client.post("/api/bills", headers=h, json={"patient_id": patient_id}).status_code == 403
    assert client.get("/api/bills/outstanding", headers=h).status_code == 403
    assert client.post("/api/bills/1/payments", headers=h, json={"amount": 1, "method": "cash"}).status_code == 403


def test_billing_without_token_is_401(client):
    assert client.get("/api/bills").status_code == 401
    assert client.get("/api/bills/1/pdf").status_code == 401


def test_admin_can_use_billing(client, auth_header, scenario, patient_id):
    scenario()
    assert client.post("/api/bills", headers=auth_header(client, "admin"), json={"patient_id": patient_id}).status_code == 201


# ------------------------------------------------------------------------ PDFs --

def test_invoice_pdf(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    client.post(f"/api/bills/{bill['id']}/payments", headers=h, json={"amount": 1000, "method": "cash"})
    r = client.get(f"/api/bills/{bill['id']}/pdf", headers=h)
    assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data.startswith(b"%PDF")
    text = _pdf_text(r)
    for expected in (bill["bill_number"], "INVOICE", "Consultation", "2,400.00", "1,400.00"):
        assert expected in text


def test_receipt_pdf(client, auth_header, scenario, patient_id):
    scenario()
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id).get_json()["data"]
    pay = client.post(f"/api/bills/{bill['id']}/payments", headers=h,
                      json={"amount": 1000, "method": "upi", "reference": "TXN-1"}).get_json()["data"]["payment"]
    r = client.get(f"/api/payments/{pay['id']}/receipt/pdf", headers=h)
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
    text = _pdf_text(r)
    assert pay["receipt_number"] in text and "PAYMENT RECEIPT" in text and "TXN-1" in text


def test_pdf_404s(client, auth_header):
    h = auth_header(client, "billing_staff")
    assert client.get("/api/bills/9999/pdf", headers=h).status_code == 404
    assert client.get("/api/payments/9999/receipt/pdf", headers=h).status_code == 404


def test_pdf_survives_special_characters(client, auth_header, patient_id):
    """<b> & < > typed by a user must not break PDF layout."""
    h = auth_header(client, "billing_staff")
    bill = _bill(client, auth_header, patient_id, other_services=[
        {"description": "Oxygen <b>& more</b> > 5 < 6", "unit_price": 100}]).get_json()["data"]
    r = client.get(f"/api/bills/{bill['id']}/pdf", headers=h)
    assert r.status_code == 200 and "Oxygen" in _pdf_text(r)
