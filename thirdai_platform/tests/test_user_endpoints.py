import pytest
from fastapi.testclient import TestClient

from .utils import auth_header, create_user, login

pytestmark = [pytest.mark.unit]


def test_admin_login():
    from main import app

    client = TestClient(app)

    # Test successful admin login
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    assert res.json()["data"]["access_token"] is not None

    # Test unsuccessful login with incorrect credentials
    res = login(client, username="admin", password="Password")
    assert res.status_code == 401


def check_email_signup(client):
    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 401  # User should not be able to log in before signing up

    # Create a new user
    res = create_user(
        client, username="user1", email="user1@mail.com", password="firstpassword"
    )
    assert res.status_code == 200  # User should be created successfully

    # Check that login is successful after signup
    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 200


def check_basic_auth(client):
    # Attempt to access a protected route with an invalid token
    res = client.get("/api/user/info", headers=auth_header("not a jwt"))
    assert res.status_code == 401

    # Attempt login with incorrect password
    res = login(client, username="user1@mail.com", password="bad-password")
    assert res.status_code == 401

    # Successful login with correct credentials
    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 200
    access_token = res.json()["data"]["access_token"]

    # Accessing protected route with a valid token
    res = client.get("/api/user/info", headers=auth_header(access_token))
    assert res.status_code == 200

    # Accessing protected route with a tampered token
    res = client.get("/api/user/info", headers=auth_header(access_token[:-1]))
    assert res.status_code == 401


def test_email_signup_and_user_auth():
    from main import app

    client = TestClient(app)

    check_email_signup(client)

    check_basic_auth(client)


def test_delete_user():
    from main import app

    client = TestClient(app)

    res = create_user(
        client, username="tmp-user", email="tmp-user@mail.com", password="tmp-pwd"
    )
    assert res.status_code == 200

    # Login as the temporary user
    res = login(client, username="tmp-user@mail.com", password="tmp-pwd")
    assert res.status_code == 200
    user_jwt = res.json()["data"]["access_token"]

    # Login as admin
    res = login(client, "admin@mail.com", "password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    # Admin fetches user information to confirm existence
    res = client.get("/api/user/info", headers=auth_header(user_jwt))
    assert res.status_code == 200

    # Admin deletes the temporary user
    res = client.request(
        "DELETE",
        "/api/user/delete-user",
        headers=auth_header(admin_jwt),
        json={"email": "tmp-user@mail.com"},
    )
    assert res.status_code == 200

    # Ensure deleted user can no longer access their information
    res = client.get("/api/user/info", headers=auth_header(user_jwt))
    assert res.status_code == 401


def test_add_remove_global_admin():
    from main import app

    client = TestClient(app)

    # Create a user to be promoted to global admin
    res = create_user(
        client,
        username="future-admin",
        email="future-admin@mail.com",
        password="future-admin",
    )
    assert res.status_code == 200

    # Login as the newly created user
    res = login(client, username="future-admin@mail.com", password="future-admin")
    assert res.status_code == 200
    user_jwt = res.json()["data"]["access_token"]

    # Login as admin
    res = login(client, "admin@mail.com", "password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    # Verify the user does not have admin access initially
    res = client.get("/api/user/all-users", headers=auth_header(user_jwt))
    assert res.status_code == 403  # Access forbidden for non-admin

    # Promote the user to global admin
    res = client.post(
        "/api/user/add-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "future-admin@mail.com"},
    )
    assert res.status_code == 200

    # Verify the user can access admin routes after promotion
    res = client.get("/api/user/all-users", headers=auth_header(user_jwt))
    assert res.status_code == 200

    # Check that all expected users are listed
    users_found = set(user["username"] for user in res.json()["data"])
    assert len(users_found.intersection(["future-admin", "user1", "admin"])) == 3

    # Demote the user from global admin
    res = client.post(
        "/api/user/delete-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "future-admin@mail.com"},
    )
    assert res.status_code == 200

    # Verify the user no longer has admin access after demotion
    res = client.get("/api/user/all-users", headers=auth_header(user_jwt))
    assert res.status_code == 403

    # Attempt to remove the last global admin and expect failure
    res = client.post(
        "/api/user/delete-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "admin@mail.com"},
    )
    assert (
        res.status_code == 400
    )  # Should fail as there must be at least one global admin


def test_reset_password():
    from main import app

    client = TestClient(app)

    # Create a new user
    res = create_user(
        client,
        username="reset-user",
        email="reset-user@mail.com",
        password="oldpassword",
    )
    assert res.status_code == 200  # User should be created successfully

    # Request password reset code
    res = client.get(
        "/api/user/reset-password", params={"email": "reset-user@mail.com"}
    )
    assert res.status_code == 200  # Reset request should be successful

    # If running in a test environment, extract the reset code from the response
    reset_password_code = res.json()["data"]["reset_password_code"]
    assert reset_password_code is not None

    # Use the reset code to change the password
    new_password_payload = {
        "email": "reset-user@mail.com",
        "reset_password_code": reset_password_code,
        "new_password": "newsecurepassword",
    }
    res = client.post("/api/user/new-password", json=new_password_payload)
    assert res.status_code == 200  # Password should be reset successfully

    # Ensure the user cannot log in with the old password
    res = login(client, username="reset-user@mail.com", password="oldpassword")
    assert res.status_code == 401  # Old password should be rejected

    # Ensure the user can log in with the new password
    res = login(client, username="reset-user@mail.com", password="newsecurepassword")
    assert res.status_code == 200  # New password should work
