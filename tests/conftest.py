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
