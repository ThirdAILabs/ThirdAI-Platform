import base64
import shutil

import thirdai


def login(client, username, password):
    creds = base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")

    return client.get(
        "/api/user/email-login",
        headers={"Authorization": f"Basic {creds}"},
    )


def global_admin_token(client):
    res = login(client, "admin@mail.com", "password")
    assert res.status_code == 200
    return res.json()["data"]["access_token"]


def auth_header(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def create_user(client, username, email, password):
    return client.post(
        "/api/user/email-signup-basic",
        json={"username": username, "email": email, "password": password},
    )


def create_team(client, name, access_token):
    return client.post(
        "/api/team/create-team",
        headers=auth_header(access_token),
        params={"name": name},
    )


def add_user_to_team(client, team, user, access_token):
    return client.post(
        "/api/team/add-user-to-team",
        headers=auth_header(access_token),
        params={"email": user, "team_id": team},
    )


def assign_team_admin(client, team, user, access_token):
    return client.post(
        "/api/team/assign-team-admin",
        headers=auth_header(access_token),
        params={"email": user, "team_id": team},
    )


def upload_model(client, access_token, name, access):
    model = thirdai.neural_db.NeuralDB()
    model.insert([thirdai.neural_db.InMemoryText("test.txt", ["a", "b", "c"])])

    filename = f".test_data/tmp_{name}.db"
    model.save(filename)

    shutil.make_archive(filename, "zip", filename)
    shutil.rmtree(filename)

    with open(filename + ".zip", "rb") as file:
        data = file.read()

    res = client.get(
        "/api/model/upload-token",
        params={"model_name": name, "size": len(data)},
        headers=auth_header(access_token),
    )
    assert res.status_code == 200
    token = res.json()["data"]["token"]

    res = client.post(
        "/api/model/upload-chunk",
        params={"chunk_number": 1, "compressed": True},
        files={"chunk": data[: len(data) // 2]},
        headers=auth_header(token),
    )
    assert res.status_code == 200

    res = client.post(
        "/api/model/upload-chunk",
        params={"chunk_number": 2, "compressed": True},
        files={"chunk": data[len(data) // 2 :]},
        headers=auth_header(token),
    )
    assert res.status_code == 200

    res = client.post(
        "/api/model/upload-commit",
        params={"total_chunks": 2},
        json={
            "type": "ndb",
            "access_level": access,
        },
        headers=auth_header(token),
    )

    assert res.status_code == 200
