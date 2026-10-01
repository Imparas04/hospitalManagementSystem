from tests.conftest import PASSWORD


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.get_json()["success"] is True


def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "t_doctor", "password": PASSWORD})
    body = r.get_json()
    assert r.status_code == 200
    assert body["data"]["access_token"]
    assert body["data"]["user"]["role"] == "doctor"
    assert "password_hash" not in body["data"]["user"]


def test_login_with_email(client):
    r = client.post("/api/auth/login", json={"username": "T_Doctor@test.com", "password": PASSWORD})
    assert r.status_code == 200


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "t_doctor", "password": "wrong"})
    assert r.status_code == 401 and r.get_json()["success"] is False


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": PASSWORD})
    assert r.status_code == 401


def test_login_missing_fields(client):
    r = client.post("/api/auth/login", json={})
    body = r.get_json()
    assert r.status_code == 400
    assert "username" in body["errors"] and "password" in body["errors"]


def test_login_no_json_body(client):
    assert client.post("/api/auth/login").status_code == 400


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["success"] is False


def test_me_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_me_with_token(client, auth_header):
    r = client.get("/api/auth/me", headers=auth_header(client, "nurse"))
    assert r.status_code == 200 and r.get_json()["data"]["username"] == "t_nurse"


def test_change_password(client, auth_header):
    h = auth_header(client, "nurse")
    r = client.post("/api/auth/change-password", headers=h,
                    json={"old_password": PASSWORD, "new_password": "NewPass123"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"username": "t_nurse", "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "t_nurse", "password": "NewPass123"}).status_code == 200


def test_change_password_wrong_old_and_weak_new(client, auth_header):
    h = auth_header(client, "nurse")
    r = client.post("/api/auth/change-password", headers=h, json={"old_password": "bad", "new_password": "abc"})
    assert r.status_code == 400
    assert set(r.get_json()["errors"]) == {"old_password", "new_password"}


def test_deactivated_user_cannot_login_or_use_old_token(client, auth_header):
    admin_h = auth_header(client, "admin")
    doctor_h = auth_header(client, "doctor")
    doctor_id = client.get("/api/auth/me", headers=doctor_h).get_json()["data"]["id"]
    assert client.delete(f"/api/users/{doctor_id}", headers=admin_h).status_code == 200
    # old token no longer works
    assert client.get("/api/auth/me", headers=doctor_h).status_code == 401
    # cannot log in again
    assert client.post("/api/auth/login", json={"username": "t_doctor", "password": PASSWORD}).status_code == 401
