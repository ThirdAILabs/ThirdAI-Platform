import base64


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
