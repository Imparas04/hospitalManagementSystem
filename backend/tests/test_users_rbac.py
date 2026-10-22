import pytest

from app.models.role import ALL_ROLES

NEW_USER = {"username": "new.nurse", "email": "new.nurse@test.com", "password": "Secret123",
            "full_name": "New Nurse", "role": "nurse", "phone": "+919876543210"}


def test_admin_can_create_user(client, auth_header):
    r = client.post("/api/users", headers=auth_header(client, "admin"), json=NEW_USER)
    body = r.get_json()
    assert r.status_code == 201
    assert body["data"]["role"] == "nurse" and "password" not in body["data"]
    # the new user can log in
    assert client.post("/api/auth/login", json={"username": "new.nurse", "password": "Secret123"}).status_code == 200


def test_create_user_validation_errors(client, auth_header):
    bad = {"username": "a", "email": "not-email", "password": "123", "full_name": "", "role": "wizard"}
    r = client.post("/api/users", headers=auth_header(client, "admin"), json=bad)
    assert r.status_code == 400
    assert set(r.get_json()["errors"]) == {"username", "email", "password", "full_name", "role"}


def test_create_user_duplicate(client, auth_header):
    h = auth_header(client, "admin")
    client.post("/api/users", headers=h, json=NEW_USER)
    r = client.post("/api/users", headers=h, json=NEW_USER)
    assert r.status_code == 409
    assert "username" in r.get_json()["errors"] and "email" in r.get_json()["errors"]


@pytest.mark.parametrize("role", [r for r in ALL_ROLES if r != "admin"])
def test_non_admin_roles_are_forbidden(client, auth_header, role):
    """Wrong-role access: every non-admin role gets 403 on admin-only APIs."""
    h = auth_header(client, role)
    assert client.get("/api/users", headers=h).status_code == 403
    assert client.post("/api/users", headers=h, json=NEW_USER).status_code == 403
    assert client.get("/api/roles", headers=h).status_code == 403
    assert client.delete("/api/users/1", headers=h).status_code == 403


def test_no_token_is_401_not_403(client):
    assert client.get("/api/users").status_code == 401


def test_list_users_filters_and_pagination(client, auth_header):
    h = auth_header(client, "admin")
    r = client.get("/api/users?role=doctor", headers=h)
    assert r.get_json()["data"]["total"] == 1
    r = client.get("/api/users?per_page=3&page=1", headers=h)
    d = r.get_json()["data"]
    assert len(d["items"]) == 3 and d["total"] == len(ALL_ROLES) and d["pages"] == 3
    r = client.get("/api/users?q=nurse", headers=h)
    assert r.get_json()["data"]["total"] == 1
    assert client.get("/api/users?page=0", headers=h).status_code == 400


def test_get_update_user(client, auth_header):
    h = auth_header(client, "admin")
    uid = client.get("/api/users?role=nurse", headers=h).get_json()["data"]["items"][0]["id"]
    assert client.get(f"/api/users/{uid}", headers=h).status_code == 200
    r = client.put(f"/api/users/{uid}", headers=h, json={"full_name": "Renamed Nurse", "role": "receptionist"})
    assert r.status_code == 200 and r.get_json()["data"]["role"] == "receptionist"
    assert client.get("/api/users/9999", headers=h).status_code == 404
    assert client.put(f"/api/users/{uid}", headers=h, json={}).status_code == 400
    assert client.put(f"/api/users/{uid}", headers=h, json={"role": "bad"}).status_code == 400


def test_update_to_duplicate_email_conflicts(client, auth_header):
    h = auth_header(client, "admin")
    uid = client.get("/api/users?role=nurse", headers=h).get_json()["data"]["items"][0]["id"]
    r = client.put(f"/api/users/{uid}", headers=h, json={"email": "t_doctor@test.com"})
    assert r.status_code == 409


def test_admin_cannot_lock_self_out(client, auth_header):
    h = auth_header(client, "admin")
    me = client.get("/api/auth/me", headers=h).get_json()["data"]["id"]
    assert client.delete(f"/api/users/{me}", headers=h).status_code == 400
    assert client.put(f"/api/users/{me}", headers=h, json={"role": "doctor"}).status_code == 400


def test_reset_password(client, auth_header):
    h = auth_header(client, "admin")
    uid = client.get("/api/users?role=nurse", headers=h).get_json()["data"]["items"][0]["id"]
    assert client.post(f"/api/users/{uid}/reset-password", headers=h, json={"new_password": "x"}).status_code == 400
    assert client.post(f"/api/users/{uid}/reset-password", headers=h, json={"new_password": "Fresh1234"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "t_nurse", "password": "Fresh1234"}).status_code == 200


def test_sql_injection_attempt_is_harmless(client):
    r = client.post("/api/auth/login", json={"username": "' OR '1'='1' --", "password": "' OR '1'='1"})
    assert r.status_code == 401


def test_permission_map():
    from app.utils.permissions import has_permission
    assert has_permission("admin", "anything:at_all")
    assert has_permission("receptionist", "patients:create")
    assert not has_permission("nurse", "billing:create")
    assert not has_permission("unknown_role", "patients:read")


def test_404_is_json(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.get_json()["success"] is False
