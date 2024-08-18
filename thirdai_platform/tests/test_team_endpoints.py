import pytest
from fastapi.testclient import TestClient

from .utils import (
    auth_header,
    create_user,
    global_admin_token,
    login,
    create_team,
    add_user_to_team,
)

pytestmark = [pytest.mark.unit]


def create_new_users(client):
    users = ["user_a", "user_b", "user_c", "user_d"]
    for user in users:
        res = create_user(
            client, user, email=user + "@mail.com", password=user + "_pwd"
        )
        assert res.status_code == 200

    return users


def assign_team_admin(client, team, user, access_token):
    return client.post(
        "/api/team/assign-team-admin",
        headers=auth_header(access_token),
        params={"email": user, "team_id": team},
    )


def check_create_teams(client, global_admin, user):
    # User cannot create team
    res = create_team(client, "green_team", user)
    assert res.status_code == 403

    # Global admin can create teams
    res = create_team(client, "green_team", global_admin)
    assert res.status_code == 201
    green_team = res.json()["data"]["team_id"]

    res = create_team(client, "purple_team", global_admin)
    assert res.status_code == 201
    purple_team = res.json()["data"]["team_id"]

    return green_team, purple_team


def test_team_management():
    from main import app

    client = TestClient(app)

    create_new_users(client)

    global_admin = global_admin_token(client)

    res = login(client, username="user_a@mail.com", password="user_a_pwd")
    assert res.status_code == 200
    user = res.json()["data"]["access_token"]

    green_team, purple_team = check_create_teams(client, global_admin, user)

    # Regular user cannot add another user to a team
    res = add_user_to_team(client, green_team, "user_b@mail.com", user)
    assert res.status_code == 403

    # Global admin can add user to a team
    res = add_user_to_team(client, green_team, "user_a@mail.com", global_admin)
    assert res.status_code == 200

    # Team member cannot add user to team
    res = add_user_to_team(client, green_team, "user_b@mail.com", user)
    assert res.status_code == 403

    # Users cannot make themselves team admin
    res = assign_team_admin(client, green_team, "user_a@mail.com", user)
    assert res.status_code == 403

    # Global admin can assign team admin
    res = assign_team_admin(client, green_team, "user_a@mail.com", global_admin)
    assert res.status_code == 200

    # Can add admin who's not already in the team
    res = assign_team_admin(client, purple_team, "user_c@mail.com", global_admin)
    assert res.status_code == 200

    # Team admin can add user to team
    res = add_user_to_team(client, green_team, "user_b@mail.com", user)
    assert res.status_code == 200

    # Users cannot list teams
    res = client.get("/api/team/list", headers=auth_header(user))
    assert res.status_code == 403

    # Global admin can list teams
    res = client.get("/api/team/list", headers=auth_header(global_admin))
    assert res.status_code == 200
    all_teams = set([t["id"] for t in res.json()["data"]])
    assert len(set([green_team, purple_team]).intersection(all_teams)) == 2

    # Must be admin of team to list members
    res = client.get(
        "/api/team/team-users",
        params={"team_id": purple_team},
        headers=auth_header(user),
    )
    assert res.status_code == 403

    # Admins can list members of team
    res = client.get(
        "/api/team/team-users",
        params={"team_id": green_team},
        headers=auth_header(user),
    )
    assert res.status_code == 200

    members = res.json()["data"]
    assert len(members) == 2
    roles = {m["email"]: m["role"] for m in members}
    assert roles["user_a@mail.com"] == "team_admin"
    assert roles["user_b@mail.com"] == "user"

    # Remove user from team
    res = client.post(
        "/api/team/remove-user-from-team",
        headers=auth_header(user),
        params={"team_id": green_team, "email": "user_b@mail.com"},
    )
    assert res.status_code == 200

    # Remove admin from team
    res = client.post(
        "/api/team/remove-team-admin",
        headers=auth_header(global_admin),
        params={"team_id": green_team, "email": "user_a@mail.com"},
    )
    assert res.status_code == 200

    # Check team contents
    res = client.get(
        "/api/team/team-users",
        params={"team_id": green_team},
        headers=auth_header(global_admin),
    )
    assert res.status_code == 200
    assert [m["username"] for m in res.json()["data"]] == ["user_a"]

    # Global admin can delete teams
    res = client.delete(
        "/api/team/delete-team",
        headers=auth_header(global_admin),
        params={"team_id": green_team},
    )
    assert res.status_code == 200

    # Check list of teams
    res = client.get("/api/team/list", headers=auth_header(global_admin))
    assert res.status_code == 200
    all_teams = set([t["id"] for t in res.json()["data"]])
    assert len(set([purple_team]).intersection(all_teams)) == 1
