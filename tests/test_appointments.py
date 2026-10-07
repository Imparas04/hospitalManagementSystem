import pytest


def _give_doctor_monday_schedule(client, auth_header, doctor_id):
    client.post(f"/api/doctors/{doctor_id}/schedule", headers=auth_header(client, "admin"),
                json={"day_of_week": 0, "start_time": "09:00", "end_time": "09:30", "slot_minutes": 15})


MONDAY = "2026-10-05"  # confirmed Monday


def test_book_appointment_in_open_slot(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    r = client.post("/api/appointments", headers=auth_header(client, "receptionist"), json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Chest pain"})
    body = r.get_json()
    assert r.status_code == 201 and body["data"]["status"] == "scheduled"
    assert body["data"]["patient_name"] == "Ramesh Kulkarni"
    assert body["data"]["doctor_name"] == "Test doctor"


def test_double_booking_same_slot_waitlists(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    payload = {"patient_id": patient_id, "doctor_id": doctor_id,
               "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}
    r1 = client.post("/api/appointments", headers=h, json=payload)
    r2 = client.post("/api/appointments", headers=h, json=payload)
    assert r1.get_json()["data"]["status"] == "scheduled"
    assert r2.status_code == 201 and r2.get_json()["data"]["status"] == "waitlisted"
    assert "waiting list" in r2.get_json()["message"].lower()


def test_double_booking_without_waitlist_returns_409(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    payload = {"patient_id": patient_id, "doctor_id": doctor_id,
               "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}
    client.post("/api/appointments", headers=h, json=payload)
    r = client.post("/api/appointments", headers=h, json={**payload, "allow_waitlist": False})
    assert r.status_code == 409


def test_booking_outside_schedule_waitlists(client, auth_header, doctor_setup, patient_id):
    """No schedule at all for the doctor -> every requested slot is 'unavailable' -> waitlisted."""
    doctor_id = doctor_setup["doctor"]["id"]
    r = client.post("/api/appointments", headers=auth_header(client, "receptionist"), json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"})
    assert r.status_code == 201 and r.get_json()["data"]["status"] == "waitlisted"


def test_book_appointment_validation(client, auth_header):
    r = client.post("/api/appointments", headers=auth_header(client, "receptionist"), json={})
    errors = r.get_json()["errors"]
    assert r.status_code == 400
    for field in ("patient_id", "doctor_id", "appointment_date", "appointment_time", "reason"):
        assert field in errors


def test_book_appointment_unknown_patient_or_doctor(client, auth_header):
    r = client.post("/api/appointments", headers=auth_header(client, "receptionist"), json={
        "patient_id": 9999, "doctor_id": 9999, "appointment_date": MONDAY,
        "appointment_time": "09:00", "reason": "Checkup"})
    errors = r.get_json()["errors"]
    assert r.status_code == 400 and "patient_id" in errors and "doctor_id" in errors


@pytest.mark.parametrize("role", ["doctor", "nurse", "lab_technician", "pharmacist", "billing_staff"])
def test_only_receptionist_and_admin_book(client, auth_header, doctor_setup, patient_id, role):
    r = client.post("/api/appointments", headers=auth_header(client, role), json={
        "patient_id": patient_id, "doctor_id": doctor_setup["doctor"]["id"],
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"})
    assert r.status_code == 403


def test_list_and_filter_appointments(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"})
    r = client.get(f"/api/appointments?doctor_id={doctor_id}&status=scheduled", headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["total"] == 1
    r = client.get(f"/api/appointments?date={MONDAY}", headers=h)
    assert r.get_json()["data"]["total"] == 1


def test_reschedule_appointment_to_free_slot(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    appt = client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}).get_json()["data"]
    r = client.put(f"/api/appointments/{appt['id']}", headers=h, json={"appointment_time": "09:15"})
    assert r.status_code == 200 and r.get_json()["data"]["appointment_time"] == "09:15"


def test_reschedule_to_taken_slot_rejected(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "first"})
    appt2 = client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:15", "reason": "second"}).get_json()["data"]
    r = client.put(f"/api/appointments/{appt2['id']}", headers=h, json={"appointment_time": "09:00"})
    assert r.status_code == 409


def test_cancel_and_complete_appointment(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    appt = client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}).get_json()["data"]

    r = client.post(f"/api/appointments/{appt['id']}/complete", headers=auth_header(client, "doctor"))
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "completed"

    r = client.post(f"/api/appointments/{appt['id']}/cancel", headers=h)
    assert r.status_code == 400  # already completed


def test_cancel_frees_slot_for_rebooking(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    appt = client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}).get_json()["data"]
    client.post(f"/api/appointments/{appt['id']}/cancel", headers=h)
    r = client.post("/api/appointments", headers=h, json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "rebooked", "allow_waitlist": False})
    assert r.status_code == 201 and r.get_json()["data"]["status"] == "scheduled"


def test_waiting_list_and_promote(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    payload = {"patient_id": patient_id, "doctor_id": doctor_id,
               "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}
    first = client.post("/api/appointments", headers=h, json=payload).get_json()["data"]
    waitlisted = client.post("/api/appointments", headers=h, json=payload).get_json()["data"]

    r = client.get(f"/api/appointments/waiting-list?doctor_id={doctor_id}", headers=h)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1

    client.post(f"/api/appointments/{first['id']}/cancel", headers=h)
    r = client.post(f"/api/appointments/{waitlisted['id']}/promote", headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "scheduled"


def test_promote_fails_when_still_taken(client, auth_header, doctor_setup, patient_id):
    doctor_id = doctor_setup["doctor"]["id"]
    _give_doctor_monday_schedule(client, auth_header, doctor_id)
    h = auth_header(client, "receptionist")
    payload = {"patient_id": patient_id, "doctor_id": doctor_id,
               "appointment_date": MONDAY, "appointment_time": "09:00", "reason": "Checkup"}
    client.post("/api/appointments", headers=h, json=payload)
    waitlisted = client.post("/api/appointments", headers=h, json=payload).get_json()["data"]
    r = client.post(f"/api/appointments/{waitlisted['id']}/promote", headers=h)
    assert r.status_code == 409


def test_get_unknown_appointment_404(client, auth_header):
    assert client.get("/api/appointments/9999", headers=auth_header(client, "receptionist")).status_code == 404
