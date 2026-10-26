"""Tests for: login lockout, logout, safe defaults, bed gender info, and the starter-data commands."""
from datetime import date, timedelta

from app.config import Config
from app.extensions import db
from app.models.bed import Bed, Ward
from app.models.doctor import Department, Doctor
from app.models.lab import LabTest
from app.models.pharmacy import Medicine
from app.services import demo_data
from tests.conftest import PASSWORD


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ---------------- login lockout ----------------
def test_login_is_blocked_after_too_many_wrong_passwords(client, app):
    limit = app.config["LOGIN_MAX_ATTEMPTS"]
    for _ in range(limit):
        assert _login(client, "t_nurse", "wrong-password").status_code == 401
    blocked = _login(client, "t_nurse", PASSWORD)           # even the RIGHT password is refused while locked
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert blocked.get_json()["success"] is False


def test_lockout_only_affects_that_username(client, app):
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        _login(client, "t_nurse", "wrong-password")
    assert _login(client, "t_doctor", PASSWORD).status_code == 200


def test_successful_login_resets_the_failure_counter(client, app):
    limit = app.config["LOGIN_MAX_ATTEMPTS"]
    for _ in range(limit - 1):
        _login(client, "t_nurse", "wrong-password")
    assert _login(client, "t_nurse", PASSWORD).status_code == 200
    for _ in range(limit - 1):                               # counter started again from zero
        assert _login(client, "t_nurse", "wrong-password").status_code == 401
    assert _login(client, "t_nurse", PASSWORD).status_code == 200


def test_lockout_can_be_switched_off(client, app):
    app.extensions["login_guard"].max_attempts = 0
    for _ in range(10):
        assert _login(client, "t_nurse", "wrong-password").status_code == 401


# ---------------- logout ----------------
def test_logout_makes_the_token_useless(client, auth_header):
    headers = auth_header(client, "nurse")
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    again = client.get("/api/auth/me", headers=headers)
    assert again.status_code == 401 and again.get_json()["success"] is False


def test_logout_needs_a_token(client):
    assert client.post("/api/auth/logout").status_code == 401


def test_logout_is_written_to_the_audit_log(client, auth_header):
    nurse = auth_header(client, "nurse")
    client.post("/api/auth/logout", headers=nurse)
    rows = client.get("/api/audit-logs?action=auth.logout", headers=auth_header(client, "admin")).get_json()["data"]
    assert any(r["action"] == "auth.logout" for r in rows["items"])


# ---------------- safe defaults ----------------
def test_cors_default_is_not_open_to_everyone():
    assert "*" not in Config.CORS_ORIGINS


# ---------------- beds show the ward's gender rule ----------------
def test_bed_list_includes_gender_restriction(client, auth_header):
    admin = auth_header(client, "admin")
    ward = client.post("/api/wards", headers=admin, json={
        "name": "Ladies Ward", "ward_type": "general", "gender_restriction": "female"}).get_json()["data"]
    client.post(f"/api/wards/{ward['id']}/beds", headers=admin, json={"bed_number": "L-1", "bed_type": "general"})
    beds = client.get("/api/beds", headers=admin).get_json()["data"]
    beds = beds["items"] if isinstance(beds, dict) else beds
    assert beds[0]["gender_restriction"] == "female"


# ---------------- starter data ----------------
def test_master_data_fills_an_empty_hospital(app):
    added = demo_data.seed_master_data()
    assert added["departments"] == len(demo_data.DEPARTMENTS)
    assert Ward.query.count() == len(demo_data.WARDS)
    assert Bed.query.count() == sum(w[6] for w in demo_data.WARDS)
    assert LabTest.query.count() == len(demo_data.LAB_TESTS)
    assert Medicine.query.count() == len(demo_data.MEDICINES)


def test_master_data_can_run_twice_without_duplicates(app):
    demo_data.seed_master_data()
    second = demo_data.seed_master_data()
    assert all(count == 0 for count in second.values())
    assert Department.query.count() == len(demo_data.DEPARTMENTS)


def test_demo_doctors_have_profiles_and_bookable_slots(client, auth_header):
    created = demo_data.seed_demo_doctors("Demo12345")
    assert created >= len(demo_data.DOCTORS)
    assert demo_data.seed_demo_doctors("Demo12345") == 0          # nothing new the second time
    doctor = Doctor.query.first()
    monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    r = client.get(f"/api/doctors/{doctor.id}/availability?date={monday.isoformat()}",
                   headers=auth_header(client, "receptionist"))
    assert r.status_code == 200 and len(r.get_json()["data"]["slots"]) > 0


def test_cli_commands_work(app):
    runner = app.test_cli_runner()
    assert "Added:" in runner.invoke(args=["seed-demo-data"]).output
    result = runner.invoke(args=["seed-demo-doctors"], input="Demo12345\nDemo12345\n")
    assert result.exit_code == 0 and "Doctor profiles added" in result.output
    weak = runner.invoke(args=["seed-demo-doctors"], input="abc\nabc\n")
    assert weak.exit_code != 0


# ---------------- a doctor can look up medicines (needed to write a prescription) ----------------
def test_doctor_can_list_medicines_but_not_manage_stock(client, auth_header):
    doctor = auth_header(client, "doctor")
    assert client.get("/api/pharmacy/medicines", headers=doctor).status_code == 200
    assert client.post("/api/pharmacy/medicines", headers=doctor,
                       json={"name": "X", "unit": "tablet"}).status_code == 403
    assert client.get("/api/pharmacy/medicines", headers=auth_header(client, "receptionist")).status_code == 403
