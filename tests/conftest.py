import pytest

from app import create_app
from app.cli import seed_roles
from app.config import TestingConfig
from app.extensions import db
from app.models.role import ALL_ROLES
from app.services import user_service

PASSWORD = "Test1234"


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        seed_roles()
        # one user per role: admin_user, doctor_user, ...
        for role in ALL_ROLES:
            user_service.create_user({
                "username": f"t_{role}", "email": f"t_{role}@test.com",
                "password": PASSWORD, "full_name": f"Test {role}", "role": role})
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, role):
    resp = client.post("/api/auth/login", json={"username": f"t_{role}", "password": PASSWORD})
    return resp.get_json()["data"]["access_token"]


@pytest.fixture()
def auth_header():
    """auth_header(client, 'doctor') -> {'Authorization': 'Bearer ...'}"""
    def _make(client, role):
        return {"Authorization": f"Bearer {login(client, role)}"}
    return _make


@pytest.fixture()
def doctor_setup(client, auth_header):
    """Creates a department and a Doctor profile for the standard t_doctor user.
    Returns {"department": {...}, "doctor": {...}}."""
    admin = auth_header(client, "admin")
    dept = client.post("/api/departments", headers=admin, json={"name": "Cardiology"}).get_json()["data"]
    doctor_user_id = client.get("/api/auth/me", headers=auth_header(client, "doctor")).get_json()["data"]["id"]
    doc = client.post("/api/doctors", headers=admin, json={
        "user_id": doctor_user_id, "department_id": dept["id"], "specialization": "Cardiologist",
    }).get_json()["data"]
    return {"department": dept, "doctor": doc}


@pytest.fixture()
def patient_id(client, auth_header):
    """Registers one standard patient and returns its id."""
    r = client.post("/api/patients", headers=auth_header(client, "receptionist"), json={
        "full_name": "Ramesh Kulkarni", "date_of_birth": "1990-05-15", "gender": "male",
        "phone": "+919876543210",
    })
    return r.get_json()["data"]["id"]


@pytest.fixture()
def ward_and_bed(client, auth_header):
    """Creates one general ward with one available bed. Returns {"ward": {...}, "bed": {...}}."""
    admin = auth_header(client, "admin")
    ward = client.post("/api/wards", headers=admin, json={"name": "General Ward A", "ward_type": "general"}).get_json()["data"]
    bed = client.post(f"/api/wards/{ward['id']}/beds", headers=admin,
                       json={"bed_number": "A-101", "bed_type": "general"}).get_json()["data"]
    return {"ward": ward, "bed": bed}
