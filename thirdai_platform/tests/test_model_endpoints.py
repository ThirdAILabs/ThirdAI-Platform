import os
import shutil

import pytest
from fastapi.testclient import TestClient
import thirdai
import thirdai.neural_db

from .utils import (
    add_user_to_team,
    auth_header,
    create_team,
    create_user,
    global_admin_token,
    login,
)

pytestmark = [pytest.mark.unit]


def upload_model(client, access_token, name, access):
    model = thirdai.neural_db.NeuralDB()

    filename = f"./tmp_{name}.db"
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
    print(res.json())
    assert res.status_code == 200


def create_and_login(client, user):
    res = create_user(
        client, username=user, email=f"{user}@mail.com", password=f"{user}-pwd"
    )
    assert res.status_code == 200

    res = login(client, username=f"{user}@mail.com", password=f"{user}-pwd")
    assert res.status_code == 200

    return res.json()["data"]["access_token"]


@pytest.fixture(scope="session")
def create_models_and_users():
    from main import app
    from licensing.verify import verify_license

    client = TestClient(app)

    # So we can initialize NDBs vs upload
    license_info = verify_license.verify_license(os.environ["LICENSE_PATH"])
    thirdai.licensing.activate(license_info["boltLicenseKey"])

    tokens = [create_and_login(client, user) for user in ["user_x", "user_y", "user_z"]]

    upload_model(client, tokens[0], "test_model_a", "public")
    upload_model(client, tokens[1], "test_model_b", "private")

    return client, tokens


def test_list_public_models(create_models_and_users):
    client, _ = create_models_and_users

    res = client.get("/api/model/public-list", params={"name": "test_model"})
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["model_name"] == "test_model_a"
    assert data[0]["username"] == "user_x"


def test_list_models(create_models_and_users):
    client, user_tokens = create_models_and_users

    for token, expected_models in [
        (user_tokens[0], ["user_x/test_model_a"]),
        (user_tokens[1], ["user_x/test_model_a", "user_y/test_model_b"]),
        (user_tokens[2], ["user_x/test_model_a"]),
    ]:
        res = client.get(
            "/api/model/list",
            params={"name": "test_model"},
            headers=auth_header(token),
        )
        assert res.status_code == 200

        data = res.json()["data"]
        assert len(data) == len(expected_models)
        model_names = set(f"{m['username']}/{m['model_name']}" for m in data)
        assert model_names == set(expected_models)


def test_check_models(create_models_and_users):
    client, user_tokens = create_models_and_users

    res = client.get(
        "/api/model/name-check",
        params={"name": "test_model_a"},
        headers=auth_header(user_tokens[0]),
    )
    assert res.status_code == 200
    assert res.json()["data"]["model_present"]

    res = client.get(
        "/api/model/name-check",
        params={"name": "test_model_a"},
        headers=auth_header(user_tokens[1]),
    )
    assert res.status_code == 200
    assert not res.json()["data"]["model_present"]


def test_download_public_model(create_models_and_users):
    client, _ = create_models_and_users

    res = client.get(
        "/api/model/public-download", params={"model_identifier": "user_y/test_model_b"}
    )
    assert res.status_code == 403

    res = client.get(
        "/api/model/public-download", params={"model_identifier": "user_x/test_model_a"}
    )
    assert res.status_code == 200
    res.close()


def test_download_model(create_models_and_users):
    client, user_tokens = create_models_and_users

    res = client.get(
        "/api/model/download",
        params={"model_identifier": "user_y/test_model_b"},
        headers=auth_header(user_tokens[0]),
    )
    assert res.status_code == 403

    res = client.get(
        "/api/model/download",
        params={"model_identifier": "user_y/test_model_b"},
        headers=auth_header(user_tokens[1]),
    )
    assert res.status_code == 200
    res.close()


def test_list_all_models(create_models_and_users):
    client, _ = create_models_and_users

    global_admin = global_admin_token(client)

    res = client.get("/api/model/all-models", headers=auth_header(global_admin))
    assert res.status_code == 200

    assert len(res.json()["data"]) == 2


def test_update_access_level(create_models_and_users):
    client, user_tokens = create_models_and_users

    res = client.get("/api/model/public-list", params={"name": "test_model"})
    assert res.status_code == 200
    assert ["test_model_a"] == [m["model_name"] for m in res.json()["data"]]

    res = client.post(
        "/api/model/update-access-level",
        params={"model_identifier": "user_x/test_model_a", "access_level": "private"},
        headers=auth_header(user_tokens[0]),
    )
    assert res.status_code == 200

    res = client.get("/api/model/public-list", params={"name": "test_model"})
    assert res.status_code == 200
    assert [] == [m["model_name"] for m in res.json()["data"]]


def test_model_team_permissions(create_models_and_users):
    client, user_tokens = create_models_and_users

    global_admin = global_admin_token(client)
    res = create_team(client, "tmp_team", access_token=global_admin)
    assert res.status_code == 201
    team_id = res.json()["data"]["team_id"]

    for user in ["user_y@mail.com", "user_z@mail.com"]:
        res = add_user_to_team(
            client, team=team_id, user=user, access_token=global_admin
        )
        assert res.status_code == 200

    res = client.get(
        "/api/model/team-models",
        params={"team_id": team_id},
        headers=auth_header(global_admin),
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 0

    # Only owner can add to team
    res = client.post(
        "/api/team/add-model-to-team",
        params={"model_identifier": "user_y/test_model_b", "team_id": team_id},
        headers=auth_header(user_tokens[2]),
    )
    assert res.status_code == 403

    # Owner can add model to team
    res = client.post(
        "/api/team/add-model-to-team",
        params={"model_identifier": "user_y/test_model_b", "team_id": team_id},
        headers=auth_header(user_tokens[1]),
    )
    assert res.status_code == 200

    res = client.get(
        "/api/model/team-models",
        params={"team_id": team_id},
        headers=auth_header(global_admin),
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    def check_model_permissions(owner, read, write):
        res = client.get(
            "/api/model/permissions",
            params={"model_identifier": "user_y/test_model_b"},
            headers=auth_header(user_tokens[1]),
        )
        assert res.status_code == 200
        permissions = res.json()["data"]

        assert set(owner) == set(p["username"] for p in permissions["owner"])
        assert set(read) == set(p["username"] for p in permissions["read"])
        assert set(write) == set(p["username"] for p in permissions["write"])

    check_model_permissions(
        owner=["admin", "user_y"],
        read=["user_z"],
        write=["user_y"],
    )

    res = client.post(
        "/api/model/update-default-permission",
        params={"model_identifier": "user_y/test_model_b", "new_permission": "write"},
        headers=auth_header(user_tokens[1]),
    )
    assert res.status_code == 200

    check_model_permissions(
        owner=["admin", "user_y"],
        read=[],
        write=["user_y", "user_z"],
    )

    res = client.post(
        "/api/model/update-default-permission",
        params={"model_identifier": "user_y/test_model_b", "new_permission": "read"},
        headers=auth_header(user_tokens[1]),
    )
    assert res.status_code == 200

    check_model_permissions(
        owner=["admin", "user_y"],
        read=["user_z"],
        write=["user_y"],
    )

    res = client.post(
        "/api/model/update-model-permission",
        params={
            "model_identifier": "user_y/test_model_b",
            "email": "user_z@mail.com",
            "permission": "write",
        },
        headers=auth_header(user_tokens[1]),
    )
    assert res.status_code == 200

    check_model_permissions(
        owner=["admin", "user_y"],
        read=[],
        write=["user_y", "user_z"],
    )
