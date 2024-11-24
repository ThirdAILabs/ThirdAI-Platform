import pytest
from fastapi.testclient import TestClient

from .utils import (
    add_user_to_team,
    assign_team_admin,
    auth_header,
    create_team,
    create_user,
    login,
)

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

    # Promote the user to global admin
    res = client.post(
        "/api/user/add-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "future-admin@mail.com"},
    )
    assert res.status_code == 200

    res = client.get("/api/user/list", headers=auth_header(user_jwt))
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

    # Attempt to remove the last global admin and expect failure
    res = client.post(
        "/api/user/delete-global-admin",
        headers=auth_header(admin_jwt),
        json={"email": "admin@mail.com"},
    )
    assert (
        res.status_code == 400
    )  # Should fail as there must be at least one global admin


# Add test for list_accessible_users
def test_list_accessible_users():
    from main import app

    client = TestClient(app)

    # Global Admin login to get access token
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    # Create team1 and team2
    res = create_team(client, "team1", admin_jwt)
    assert res.status_code == 201
    team1_id = res.json()["data"]["team_id"]

    res = create_team(client, "team2", admin_jwt)
    assert res.status_code == 201
    team2_id = res.json()["data"]["team_id"]

    # Create users
    res = create_user(
        client, username="user2", email="user2@mail.com", password="password2"
    )
    assert res.status_code == 200

    res = create_user(
        client, username="user3", email="user3@mail.com", password="password3"
    )
    assert res.status_code == 200

    res = create_user(
        client, username="team_admin", email="team_admin@mail.com", password="password4"
    )
    assert res.status_code == 200

    # Add user1 to team1
    res = add_user_to_team(client, team1_id, "user1@mail.com", admin_jwt)
    assert res.status_code == 200

    # Add user2 to team2
    res = add_user_to_team(client, team2_id, "user2@mail.com", admin_jwt)
    assert res.status_code == 200

    # Assign team_admin as the admin of both team1 and team2
    res = assign_team_admin(client, team1_id, "team_admin@mail.com", admin_jwt)
    assert res.status_code == 200
    res = assign_team_admin(client, team2_id, "team_admin@mail.com", admin_jwt)
    assert res.status_code == 200

    # User1 logs in and should only see users from team1
    res = login(client, username="user1@mail.com", password="firstpassword")
    assert res.status_code == 200
    user1_jwt = res.json()["data"]["access_token"]

    res = client.get("/api/user/list", headers=auth_header(user1_jwt))
    assert res.status_code == 200
    accessible_users = [user["email"] for user in res.json()["data"]]
    assert "user1@mail.com" in accessible_users  # User1 should see themself
    assert (
        "team_admin@mail.com" in accessible_users
    )  # Admin of their team should be accessible
    assert (
        "user2@mail.com" not in accessible_users
    )  # User1 should not see users from team2

    # User3 logs in and should only see User3 as it is not associated with any team
    res = login(client, username="user3@mail.com", password="password3")
    assert res.status_code == 200
    user3_jwt = res.json()["data"]["access_token"]

    res = client.get("/api/user/list", headers=auth_header(user3_jwt))
    assert res.status_code == 200
    accessible_users = [user["email"] for user in res.json()["data"]]
    assert "user3@mail.com" in accessible_users  # User3 should see themself
    assert len(accessible_users) == 1  # Ensure that it is not accessing other users.

    # team_admin logs in and should see users from both team1 and team2
    res = login(client, username="team_admin@mail.com", password="password4")
    assert res.status_code == 200
    team_admin_jwt = res.json()["data"]["access_token"]

    res = client.get("/api/user/list", headers=auth_header(team_admin_jwt))
    assert res.status_code == 200
    accessible_users = [user["email"] for user in res.json()["data"]]
    assert "user1@mail.com" in accessible_users  # Admin should see user1 (team1)
    assert "user2@mail.com" in accessible_users  # Admin should see user2 (team2)
    assert "team_admin@mail.com" in accessible_users  # Admin should see themself

    # Test for global admin: should retrieve all users
    res = client.get("/api/user/list", headers=auth_header(admin_jwt))
    assert (
        res.status_code == 200
    ), f"Unexpected status code: {res.status_code}. Response: {res.json()}"

    data = res.json()
    accessible_users = [user["email"] for user in res.json()["data"]]
    assert "user1@mail.com" in accessible_users
    assert "user2@mail.com" in accessible_users
    assert "team_admin@mail.com" in accessible_users
    assert "admin@mail.com" in accessible_users
    assert data["message"] == "Successfully got the list of all users"


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


def test_add_user_by_global_admin():
    from main import app

    client = TestClient(app)

    # Admin login to get access token
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    # Add a new user by global admin (should be automatically verified)
    user_payload = {
        "username": "new_user",
        "email": "new_user@mail.com",
        "password": "securepassword",
    }
    res = client.post(
        "/api/user/add-user", headers=auth_header(admin_jwt), json=user_payload
    )
    assert res.status_code == 200, f"Failed to add user: {res.json()}"

    # Ensure the new user can log in immediately after being added
    res = login(client, username="new_user@mail.com", password="securepassword")
    assert (
        res.status_code == 200
    ), "User should be able to log in immediately after being added"
