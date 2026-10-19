from io import BytesIO

import pytest
from pypdf import PdfReader

SUMMARY = {"diagnosis": "Community-acquired pneumonia", "treatment_summary": "IV antibiotics for 3 days, oxygen support, rapid recovery.",
           "doctor_instructions": "Complete the antibiotic course. Avoid cold drinks.", "follow_up_date": "2030-01-15"}


def _pdf_text(resp):
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(resp.data)).pages)


def test_doctor_discharges_patient_with_full_summary(client, auth_header, scenario, patient_id):
    ids = scenario(discharge=False)
    r = client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=SUMMARY)
    d = r.get_json()["data"]
    assert r.status_code == 201

    assert d["patient"]["full_name"] == "Ramesh Kulkarni" and d["patient"]["patient_code"].startswith("P")
    assert d["doctor"]["full_name"] == "Test doctor" and d["doctor"]["specialization"] == "Cardiologist"
    assert d["admission"]["discharge_date"] is not None
    assert d["diagnosis"] == SUMMARY["diagnosis"] and d["follow_up_date"] == "2030-01-15"
    assert d["doctor_instructions"].startswith("Complete the antibiotic")

    assert len(d["lab_reports"]) == 1
    assert d["lab_reports"][0]["code"] == "CBC" and d["lab_reports"][0]["is_abnormal"] is True
    assert d["medicines"][0]["medicine"] == "Paracetamol" and d["medicines"][0]["quantity_issued"] == 4

    bill = d["final_bill"]
    assert bill["total_amount"] == 2400.0 and bill["status"] == "unpaid"
    assert sorted(i["category"] for i in bill["items"]) == ["bed", "consultation", "laboratory", "medicine"]


def test_discharge_frees_the_bed(client, auth_header, scenario):
    ids = scenario(discharge=False)
    admin = auth_header(client, "admin")
    assert client.get(f"/api/beds?ward_id={ids['ward_id']}", headers=admin).get_json()["data"][0]["status"] == "occupied"
    client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=SUMMARY)
    assert client.get(f"/api/beds?ward_id={ids['ward_id']}", headers=admin).get_json()["data"][0]["status"] == "available"
    adm = client.get(f"/api/admissions/{ids['admission_id']}", headers=admin).get_json()["data"]
    assert adm["status"] == "discharged"


def test_discharge_creates_exactly_one_final_bill(client, auth_header, scenario, patient_id):
    ids = scenario(discharge=False)
    client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=SUMMARY)
    bills = client.get(f"/api/bills?patient_id={patient_id}", headers=auth_header(client, "billing_staff")).get_json()["data"]
    assert bills["total"] == 1


def test_summary_works_after_nurse_already_discharged(client, auth_header, scenario):
    ids = scenario(discharge=True)  # nurse used the Phase 3 discharge endpoint
    r = client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=SUMMARY)
    assert r.status_code == 201 and r.get_json()["data"]["final_bill"]["total_amount"] == 2400.0


def test_cannot_discharge_twice(client, auth_header, scenario):
    ids = scenario(discharge=False)
    h = auth_header(client, "doctor")
    assert client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=SUMMARY).status_code == 201
    r = client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=SUMMARY)
    assert r.status_code == 409


def test_discharge_validation(client, auth_header, scenario):
    ids = scenario(discharge=False)
    h = auth_header(client, "doctor")
    r = client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json={})
    assert r.status_code == 400 and {"diagnosis", "treatment_summary"} <= set(r.get_json()["errors"])
    bad_date = {**SUMMARY, "follow_up_date": "2020-01-01"}
    assert "follow_up_date" in client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=bad_date).get_json()["errors"]
    bad_fmt = {**SUMMARY, "follow_up_date": "15/01/2030"}
    assert client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=bad_fmt).status_code == 400
    # nothing was saved by the failed attempts, so a correct one still works
    assert client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=SUMMARY).status_code == 201


def test_discharge_unknown_admission_404(client, auth_header, doctor_setup):
    assert client.post("/api/discharge/9999", headers=auth_header(client, "doctor"), json=SUMMARY).status_code == 404


def test_follow_up_date_is_optional(client, auth_header, scenario):
    ids = scenario(discharge=False)
    body = {k: v for k, v in SUMMARY.items() if k not in ("follow_up_date", "doctor_instructions")}
    r = client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=body)
    assert r.status_code == 201 and r.get_json()["data"]["follow_up_date"] is None


@pytest.mark.parametrize("role", ["receptionist", "nurse", "lab_technician", "pharmacist", "billing_staff"])
def test_only_doctor_and_admin_can_write_summary(client, auth_header, scenario, role):
    ids = scenario(discharge=False)
    r = client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, role), json=SUMMARY)
    assert r.status_code == 403


def test_admin_can_write_summary(client, auth_header, scenario):
    ids = scenario(discharge=False)
    assert client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "admin"), json=SUMMARY).status_code == 201


@pytest.mark.parametrize("role,expected", [("doctor", 200), ("nurse", 200), ("receptionist", 200), ("billing_staff", 200),
                                           ("admin", 200), ("lab_technician", 403), ("pharmacist", 403)])
def test_read_permissions(client, auth_header, scenario, role, expected):
    ids = scenario(discharge=False)
    client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=SUMMARY)
    h = auth_header(client, role)
    assert client.get(f"/api/discharge/{ids['admission_id']}", headers=h).status_code == expected
    assert client.get(f"/api/discharge/{ids['admission_id']}/pdf", headers=h).status_code == expected


def test_no_token_is_401(client):
    assert client.get("/api/discharge/1").status_code == 401
    assert client.post("/api/discharge/1", json=SUMMARY).status_code == 401


def test_get_summary_before_it_exists_is_404(client, auth_header, scenario):
    ids = scenario(discharge=False)
    h = auth_header(client, "doctor")
    assert client.get(f"/api/discharge/{ids['admission_id']}", headers=h).status_code == 404
    assert client.get(f"/api/discharge/{ids['admission_id']}/pdf", headers=h).status_code == 404


def test_summary_shows_live_payment_status(client, auth_header, scenario):
    ids = scenario(discharge=False)
    client.post(f"/api/discharge/{ids['admission_id']}", headers=auth_header(client, "doctor"), json=SUMMARY)
    h = auth_header(client, "billing_staff")
    bill_id = client.get("/api/bills", headers=h).get_json()["data"]["items"][0]["id"]
    client.post(f"/api/bills/{bill_id}/payments", headers=h, json={"amount": 400, "method": "cash"})
    final = client.get(f"/api/discharge/{ids['admission_id']}", headers=h).get_json()["data"]["final_bill"]
    assert final["status"] == "partially_paid" and final["outstanding_amount"] == 2000.0


def test_discharge_summary_pdf_contains_everything(client, auth_header, scenario):
    ids = scenario(discharge=False)
    h = auth_header(client, "doctor")
    client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=SUMMARY)
    r = client.get(f"/api/discharge/{ids['admission_id']}/pdf", headers=h)
    assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data.startswith(b"%PDF")
    text = _pdf_text(r)
    for expected in ("DISCHARGE SUMMARY", "Ramesh Kulkarni", "Dr. Test doctor", "Community-acquired pneumonia",
                     "Complete Blood Count", "ABNORMAL", "Paracetamol", "Complete the antibiotic course",
                     "2030-01-15", "2,400.00", "UNPAID"):
        assert expected in text, f"missing in PDF: {expected}"


def test_discharge_pdf_survives_special_characters(client, auth_header, scenario):
    ids = scenario(discharge=False)
    h = auth_header(client, "doctor")
    body = {**SUMMARY, "diagnosis": "Fever <b>& chills</b> (temp > 101 < 104)", "treatment_summary": "Line one\nLine two & <i>three</i>"}
    assert client.post(f"/api/discharge/{ids['admission_id']}", headers=h, json=body).status_code == 201
    r = client.get(f"/api/discharge/{ids['admission_id']}/pdf", headers=h)
    assert r.status_code == 200 and "Fever" in _pdf_text(r)
