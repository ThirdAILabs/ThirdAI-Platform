import pytest
from fastapi.testclient import TestClient

from .utils import (
    add_user_to_team,
    assign_team_admin,
    auth_header,
    create_team,
    create_user,
    login,
    upload_model,
)

pytestmark = [pytest.mark.unit]

### Helper Functions ###


def create_workflow(client, jwt_token, workflow_name, type_name):
    """
    Helper function to create a workflow.
    """
    res = client.post(
        "/api/workflow/create",
        params={"name": workflow_name, "type_name": type_name},
        headers=auth_header(jwt_token),
    )
    assert res.status_code == 200
    return res.json()["data"]["workflow_id"]


def delete_workflow(client, jwt_token, workflow_id, expected_status_code):
    """
    Helper function to delete a workflow.
    """
    res = client.post(
        "/api/workflow/delete",
        params={"workflow_id": workflow_id},
        headers=auth_header(jwt_token),
    )
    assert res.status_code == expected_status_code


def check_model_presence(client, jwt_token, model_name, should_exist=True):
    """
    Helper function to check if a model is present.
    """
    res = client.get(
        "/api/model/name-check",
        params={"name": model_name},
        headers=auth_header(jwt_token),
    )
    assert res.status_code == 200
    model_present = res.json()["data"]["model_present"]
    assert model_present == should_exist


def setup_model(
    client, jwt_token, model_name, access_level="public", team_id=None, username=None
):
    """
    Helper function to upload a model and update its access level if needed.
    """
    upload_model(client, jwt_token, model_name, access_level)

    if team_id:
        res = client.post(
            "/api/model/update-access-level",
            params={
                "model_identifier": f"{username}/{model_name}",
                "access_level": "protected",
                "team_id": team_id,
            },
            headers=auth_header(jwt_token),
        )
        assert res.status_code == 200

    res = client.get(
        "/api/model/list", params={"name": model_name}, headers=auth_header(jwt_token)
    )
    assert res.status_code == 200
    return res.json()["data"][0]["model_id"]


### Setup: Create Users ###


@pytest.fixture(scope="module", autouse=True)
def setup_users():
    """
    Setup fixture to create necessary users for the tests.
    Runs once before all tests in the module.
    """
    from main import app

    client = TestClient(app)
    # Create workflow owner
    res = create_user(
        client, "workflow-owner", "workflow-owner@mail.com", "owner-password"
    )
    assert res.status_code == 200

    # Create normal user
    res = create_user(client, "normal-user", "normal-user@mail.com", "normal-password")
    assert res.status_code == 200

    # Team Admin User
    res = create_user(client, "team-admin", "team-admin@mail.com", "admin-password")
    assert res.status_code == 200

    res = create_user(
        client, "user_1", email="user_1@mail.com", password="user_1_password"
    )
    assert res.status_code == 200

    res = create_user(
        client, "user_2", email="user_2@mail.com", password="user_2_password"
    )
    assert res.status_code == 200


### 1. Workflow Type Tests ###


def test_create_and_delete_workflow_type():
    from main import app

    client = TestClient(app)

    # Log in as global admin
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    # Create a complex workflow type
    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "complex_workflow_type",
            "description": "A complex workflow type",
            "model_requirements": [
                [{"component": "search", "type": "ndb"}],
                [
                    {"component": "filter", "type": "udf", "subtype": "regex"},
                    {"component": "guardrail", "type": "udt", "subtype": "token"},
                ],
            ],
        },
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 200

    # Create a sample workflow type
    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "sample_workflow_type",
            "description": "A sample workflow type",
            "model_requirements": [[{"component": "search", "type": "ndb"}]],
        },
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 200

    # Access control check: Normal user trying to create workflow type
    res = login(client, username="normal-user@mail.com", password="normal-password")
    assert res.status_code == 200
    normal_user_jwt = res.json()["data"]["access_token"]

    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "unauthorized_workflow_type",
            "description": "Should not be created",
            "model_requirements": [[{"component": "search", "type": "ndb"}]],
        },
        headers=auth_header(normal_user_jwt),
    )
    assert res.status_code == 403  # Forbidden

    # Attempt to create a duplicate workflow type
    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "complex_workflow_type",
            "description": "Duplicate workflow type",
            "model_requirements": [[{"component": "search", "type": "ndb"}]],
        },
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 400  # Expect failure due to duplicate name

    # Attempt to create workflow type with missing fields
    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "empty type",
            "description": "empty type",
            "model_requirements": [],
        },
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 422  # Cannot have empty model requirements.

    # Attempt to create workflow type with wrong parameters
    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "empty type",
            "description": "empty type",
            "model_requireme": {},
        },
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 422  # Cannot have empty model requiremnts.

    # List workflow types to verify addition
    res = client.get("/api/workflow/types", headers=auth_header(admin_jwt))
    assert res.status_code == 200
    workflow_types = res.json()["data"]["types"]
    assert any(wt["name"] == "complex_workflow_type" for wt in workflow_types)

    # Attempt to delete the sample workflow type
    sample_workflow_type_id = next(
        wt["id"] for wt in workflow_types if wt["name"] == "sample_workflow_type"
    )
    # Access control check: Normal user trying to delete workflow type
    res = client.post(
        "/api/workflow/delete-type",
        json={"type_id": sample_workflow_type_id},
        headers=auth_header(normal_user_jwt),
    )
    assert res.status_code == 403  # Forbidden

    # Global admin can delete the workflow
    res = client.post(
        "/api/workflow/delete-type",
        params={"type_id": sample_workflow_type_id},
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 200

    # Verify deletion of sample workflow type
    res = client.get("/api/workflow/types", headers=auth_header(admin_jwt))
    workflow_types_after_delete = res.json()["data"]["types"]
    assert not any(
        wt["name"] == "sample_workflow_type" for wt in workflow_types_after_delete
    )


### 2. Workflow Tests ###


def test_create_and_delete_workflow():
    from main import app

    client = TestClient(app)

    # Log in as workflow owner
    res = login(client, username="workflow-owner@mail.com", password="owner-password")
    assert res.status_code == 200
    owner_jwt = res.json()["data"]["access_token"]

    # Create a new workflow
    # This assumes that `complex_worklfow_type` has already been added in the previous
    # test and all the subsequent tests uses that.
    workflow_id = create_workflow(
        client, owner_jwt, "Test Workflow", "complex_workflow_type"
    )

    # Verify that the workflow has been created
    res = client.get("/api/workflow/list", headers=auth_header(owner_jwt))
    assert res.status_code == 200
    workflows = res.json()["data"]
    assert any(wf["id"] == workflow_id for wf in workflows)

    # Access control check: Normal user trying to delete a workflow they do not own
    res = login(client, username="normal-user@mail.com", password="normal-password")
    assert res.status_code == 200
    normal_user_jwt = res.json()["data"]["access_token"]

    delete_workflow(
        client, normal_user_jwt, workflow_id, expected_status_code=403
    )  # Expect failure

    # Global admin attempting to delete the workflow
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    delete_workflow(
        client, admin_jwt, workflow_id, expected_status_code=200
    )  # Should succeed

    # Verify deletion by global admin
    res = client.get("/api/workflow/list", headers=auth_header(owner_jwt))
    assert res.status_code == 200
    workflows_after_delete = res.json()["data"]
    assert not any(wf["id"] == workflow_id for wf in workflows_after_delete)


### 3. Model Management in Workflows ###


def test_add_and_validate_models_to_workflow():
    from main import app

    client = TestClient(app)

    # Log in as workflow owner
    res = login(client, username="workflow-owner@mail.com", password="owner-password")
    assert res.status_code == 200
    owner_jwt = res.json()["data"]["access_token"]

    # Login as normal user
    res = login(client, username="normal-user@mail.com", password="normal-password")
    assert res.status_code == 200
    normal_user_jwt = res.json()["data"]["access_token"]

    # Create a workflow for adding models
    workflow_id = create_workflow(
        client, owner_jwt, "Model Test Workflow", "complex_workflow_type"
    )

    model1_id = setup_model(client, owner_jwt, "model_1", "public")

    # Add models to the workflow
    res = client.post(
        "/api/workflow/add-models",
        json={
            "workflow_id": workflow_id,
            "model_ids": [model1_id],
            "components": ["search"],
        },
        headers=auth_header(owner_jwt),
    )
    assert res.status_code == 200

    # Validate the workflow
    res = client.post(
        "/api/workflow/validate",
        params={"workflow_id": workflow_id},
        headers=auth_header(owner_jwt),
    )
    assert res.status_code == 200
    assert "Validation successful" in res.json()["message"]

    # Access control check: Attempt to delete a model from workflow by non-owner
    res = client.post(
        "/api/workflow/delete-models",
        json={
            "workflow_id": workflow_id,
            "model_ids": [model1_id],
            "components": ["search"],
        },
        headers=auth_header(normal_user_jwt),
    )
    assert res.status_code == 403  # Forbidden

    # Delete model from workflow by owner
    res = client.post(
        "/api/workflow/delete-models",
        json={
            "workflow_id": workflow_id,
            "model_ids": [model1_id],
            "components": ["search"],
        },
        headers=auth_header(owner_jwt),
    )
    assert res.status_code == 200

    # Validate the workflow after deletion of a model
    res = client.post(
        "/api/workflow/validate",
        params={"workflow_id": workflow_id},
        headers=auth_header(owner_jwt),
    )
    assert res.status_code == 404  # Validation should fail due to missing models

    delete_workflow(client, owner_jwt, workflow_id, expected_status_code=200)


def test_delete_workflow_delete_models():
    from main import app

    client = TestClient(app)

    # Log in as workflow owner
    res = login(client, username="workflow-owner@mail.com", password="owner-password")
    assert res.status_code == 200
    owner_jwt = res.json()["data"]["access_token"]

    # Create two workflows
    workflow_id_1 = create_workflow(
        client, owner_jwt, "Model Test Workflow 1", "complex_workflow_type"
    )
    workflow_id_2 = create_workflow(
        client, owner_jwt, "Model Test Workflow 2", "complex_workflow_type"
    )

    model_id = setup_model(client, owner_jwt, "model_a", "public")

    # Add model to both workflows
    for workflow_id in [workflow_id_1, workflow_id_2]:
        res = client.post(
            "/api/workflow/add-models",
            json={
                "workflow_id": workflow_id,
                "model_ids": [model_id],
                "components": ["search"],
            },
            headers=auth_header(owner_jwt),
        )
        assert res.status_code == 200

    # Delete workflow 2 and check model presence
    delete_workflow(client, owner_jwt, workflow_id_2, expected_status_code=200)
    check_model_presence(client, owner_jwt, "model_a", should_exist=True)

    # Delete workflow 1 and check model presence
    delete_workflow(client, owner_jwt, workflow_id_1, expected_status_code=200)
    check_model_presence(client, owner_jwt, "model_a", should_exist=True)


def test_workflow_access_based_on_model_access():
    from main import app

    client = TestClient(app)

    # Login as Global admin
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    global_admin_jwt = res.json()["data"]["access_token"]

    # Login as team admin
    res = login(client, username="team-admin@mail.com", password="admin-password")
    assert res.status_code == 200
    team_admin_jwt = res.json()["data"]["access_token"]

    # Login as team member
    res = login(client, username="workflow-owner@mail.com", password="owner-password")
    assert res.status_code == 200
    team_member_jwt = res.json()["data"]["access_token"]

    # Login as normal user
    res = login(client, username="normal-user@mail.com", password="normal-password")
    assert res.status_code == 200
    normal_user_jwt = res.json()["data"]["access_token"]

    res = create_team(client, "Team A", global_admin_jwt)
    assert res.status_code == 201
    team_id = res.json()["data"]["team_id"]

    res = assign_team_admin(client, team_id, "team-admin@mail.com", global_admin_jwt)
    assert res.status_code == 200

    res = add_user_to_team(client, team_id, "workflow-owner@mail.com", team_admin_jwt)
    assert res.status_code == 200

    public_model_id = setup_model(client, global_admin_jwt, "public_model", "public")

    protected_model_id = setup_model(
        client,
        team_admin_jwt,
        "protected_model",
        team_id=team_id,
        username="team-admin",
    )

    private_model_id = setup_model(client, team_member_jwt, "private_model", "private")

    workflow_public_id = create_workflow(
        client, global_admin_jwt, "Public Workflow", "complex_workflow_type"
    )
    workflow_protected_id = create_workflow(
        client, team_admin_jwt, "Protected Workflow", "complex_workflow_type"
    )
    workflow_private_id = create_workflow(
        client, team_member_jwt, "Private Workflow", "complex_workflow_type"
    )

    # Add models to workflows
    for model_id, jwt, workflow_id in [
        (public_model_id, global_admin_jwt, workflow_public_id),
        (protected_model_id, team_admin_jwt, workflow_protected_id),
        (private_model_id, team_member_jwt, workflow_private_id),
    ]:
        res = client.post(
            "/api/workflow/add-models",
            json={
                "workflow_id": workflow_id,
                "model_ids": [model_id],
                "components": ["search"],
            },
            headers=auth_header(jwt),
        )
        assert res.status_code == 200

    for user_jwt, expected_workflows in [
        (
            global_admin_jwt,
            ["Public Workflow", "Protected Workflow", "Private Workflow"],
        ),
        (team_admin_jwt, ["Protected Workflow", "Public Workflow"]),
        (
            team_member_jwt,
            ["Public Workflow", "Private Workflow", "Protected Workflow"],
        ),
        (normal_user_jwt, ["Public Workflow"]),
    ]:
        res = client.get("/api/workflow/list", headers=auth_header(user_jwt))
        assert res.status_code == 200
        accessible_workflows = [wf["name"] for wf in res.json()["data"]]

        # Assert that only the expected workflows are listed
        assert set(accessible_workflows) == set(
            expected_workflows
        ), f"Failed for user {user_jwt}"


def test_workflow_access_control_with_model_visibility():
    from main import app

    client = TestClient(app)

    # Create a workflow type with two NDB models
    res = login(client, username="admin@mail.com", password="password")
    assert res.status_code == 200
    admin_jwt = res.json()["data"]["access_token"]

    res = client.post(
        "/api/workflow/add-type",
        json={
            "name": "ndb_workflow_type",
            "description": "A workflow type requiring two NDB models",
            "model_requirements": [
                [{"component": "search_1", "type": "ndb"}],
                [{"component": "search_2", "type": "ndb"}],
            ],
        },
        headers=auth_header(admin_jwt),
    )
    assert res.status_code == 200

    # User 1 creates two private models
    res = login(client, username="user_1@mail.com", password="user_1_password")
    assert res.status_code == 200
    user_1_jwt = res.json()["data"]["access_token"]

    model_1_id = setup_model(client, user_1_jwt, "user_1_model_1", "private")
    model_2_id = setup_model(client, user_1_jwt, "user_1_model_2", "private")

    # User 1 creates a workflow with the two private models
    workflow_id = create_workflow(
        client, user_1_jwt, "User 1 Workflow", "ndb_workflow_type"
    )

    # Add models to the workflow
    res = client.post(
        "/api/workflow/add-models",
        json={
            "workflow_id": workflow_id,
            "model_ids": [model_1_id, model_2_id],
            "components": ["search_1", "search_2"],
        },
        headers=auth_header(user_1_jwt),
    )
    assert res.status_code == 200

    # User 2 creates a third NDB model and tries to create a workflow using User 1's second model
    res = login(client, username="user_2@mail.com", password="user_2_password")
    assert res.status_code == 200
    user_2_jwt = res.json()["data"]["access_token"]

    model_3_id = setup_model(client, user_2_jwt, "user_2_model_3", "private")

    worfklow_id_2 = create_workflow(
        client, user_2_jwt, "User 2 Workflow", "ndb_workflow_type"
    )

    # Attempt to add models to workflow by User 2 using User 1's second model
    res = client.post(
        "/api/workflow/add-models",
        json={
            "workflow_id": worfklow_id_2,
            "model_ids": [model_3_id, model_2_id],
            "components": ["search_1", "search_2"],
        },
        headers=auth_header(user_2_jwt),
    )

    assert res.status_code == 403  # Should fail because model_2 is private

    # User 1 changes model_2 access to public
    res = client.post(
        "/api/model/update-access-level",
        params={
            "model_identifier": "user_1/user_1_model_2",
            "access_level": "public",
        },
        headers=auth_header(user_1_jwt),
    )
    assert res.status_code == 200

    # User 2 tries again to create a workflow using User 1's second model
    res = client.post(
        "/api/workflow/add-models",
        json={
            "workflow_id": worfklow_id_2,
            "model_ids": [model_3_id, model_2_id],
            "components": ["search_1", "search_2"],
        },
        headers=auth_header(user_2_jwt),
    )
    assert res.status_code == 200  # Should succeed now

    # Verify that the workflow created by User 2 is visible in their list
    res = client.get("/api/workflow/list", headers=auth_header(user_2_jwt))
    assert res.status_code == 200
    workflows = [wf["name"] for wf in res.json()["data"]]
    assert "User 2 Workflow" in workflows


def test_workflow_access_explicit_permission():
    from main import app

    client = TestClient(app)

    private_model_workflow = "Private Model Workflow"

    # User 1 logs in and creates a private model
    res = login(client, username="user_1@mail.com", password="user_1_password")
    assert res.status_code == 200
    user_1_jwt = res.json()["data"]["access_token"]

    private_model_id = setup_model(
        client, user_1_jwt, "private_model_user_1", "private"
    )

    # User 1 creates a workflow using the private model
    workflow_id = create_workflow(
        client, user_1_jwt, private_model_workflow, "complex_workflow_type"
    )

    # Add the private model to the workflow
    res = client.post(
        "/api/workflow/add-models",
        json={
            "workflow_id": workflow_id,
            "model_ids": [private_model_id],
            "components": ["search"],
        },
        headers=auth_header(user_1_jwt),
    )
    assert res.status_code == 200

    res = login(client, username="user_2@mail.com", password="user_2_password")
    assert res.status_code == 200
    user_2_jwt = res.json()["data"]["access_token"]

    res = client.get("/api/workflow/list", headers=auth_header(user_2_jwt))
    assert res.status_code == 200
    workflows = [wf["name"] for wf in res.json()["data"]]
    assert private_model_workflow not in workflows  # User 2 shouldn't see the workflow

    res = client.post(
        "/api/model/update-model-permission",
        params={
            "model_identifier": "user_1/private_model_user_1",
            "email": "user_2@mail.com",
            "permission": "read",
        },
        headers=auth_header(user_1_jwt),
    )
    assert res.status_code == 200

    # User 2 tries again to list workflows (should now see the workflow)
    res = client.get("/api/workflow/list", headers=auth_header(user_2_jwt))
    assert res.status_code == 200
    workflows = [wf["name"] for wf in res.json()["data"]]
    assert private_model_workflow in workflows  # Now User 2 should see the workflow
