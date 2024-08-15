import pytest
from fastapi.testclient import TestClient

from .utils import auth_header, create_user, login

pytestmark = [pytest.mark.unit]


def test_admin_login():
    from main import app

    client = TestClient(app)

    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    assert res.json()["data"]["access_token"] is not None

    res = login(client, username="admin", password="Password")
    assert res.status_code == 401


def test_email_signup():
    from main import app

    client = TestClient(app)

    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 401

    res = create_user(
        client, username="user1", email="user1@mail.com", password="firstpassword"
    )
    assert res.status_code == 200

    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 200


def test_user_auth():
    from main import app

    client = TestClient(app)

    res = client.get("/api/user/info", headers=auth_header("not a jwt"))
    assert res.status_code == 401

    res = login(client, username="user1@mail.com", password="bad-password")
    assert res.status_code == 401

    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 200
    access_token = res.json()["data"]["access_token"]

    res = client.get("/api/user/info", headers=auth_header(access_token))
    assert res.status_code == 200

    res = client.get("/api/user/info", headers=auth_header(access_token[:-1]))
    assert res.status_code == 401


def test_add_remove_global_admin():
    from main import app

    client = TestClient(app)

    res = create_user(
        client,
        username="future-admin",
        email="future-admin@mail.com",
        password="future-admin",
    )
    assert res.status_code == 200

    res = login(client, username="future-admin@mail.com", password="future-admin")
    assert res.status_code == 200
    user_jwt = res.json()["data"]["access_token"]

    res = login(client, "admin@mail.com", "password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    res = client.get("/api/user/all-users", headers=auth_header(user_jwt))
    assert res.status_code == 403

    res = client.post(
        "/api/user/add-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "future-admin@mail.com"},
    )
    assert res.status_code == 200

    res = client.get("/api/user/all-users", headers=auth_header(user_jwt))
    assert res.status_code == 200

    users_found = set(user["username"] for user in res.json()["data"])
    assert len(users_found.intersection(["future-admin", "user1", "admin"])) == 3

    res = client.post(
        "/api/user/delete-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "future-admin@mail.com"},
    )
    assert res.status_code == 200

    res = client.get("/api/user/all-users", headers=auth_header(user_jwt))
    assert res.status_code == 403


def test_delete_user():
    from main import app

    client = TestClient(app)

    res = login(client, username="future-admin@mail.com", password="future-admin")
    assert res.status_code == 200
    user_jwt = res.json()["data"]["access_token"]

    res = login(client, "admin@mail.com", "password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    res = client.get("/api/user/info", headers=auth_header(user_jwt))
    assert res.status_code == 200

    res = client.request(
        "DELETE",
        "/api/user/delete-user",
        headers=auth_header(admin_jwt),
        json={"email": "future-admin@mail.com"},
    )
    assert res.status_code == 200

    res = client.get("/api/user/info", headers=auth_header(user_jwt))
    assert res.status_code == 401
