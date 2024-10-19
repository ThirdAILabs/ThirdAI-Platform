from typing import List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.auth_dependencies import (
    global_admin_only,
    is_model_owner,
    team_admin_or_global_admin,
)
from backend.utils import get_model_from_identifier
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from platform_common.utils import response
from sqlalchemy.orm import Session, selectinload

team_router = APIRouter()


@team_router.post("/create-team", dependencies=[Depends(global_admin_only)])
def add_team(name: str, session: Session = Depends(get_session)):
    """
    Create a new team.

    Parameters:
    - name: The name of the team to be created.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the team ID and name upon successful creation.
    """
    # `exists()` for existence check
    if session.query(session.query(schema.Team).filter_by(name=name).exists()).scalar():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team with this name already exists",
        )
    new_team = schema.Team(name=name)
    session.add(new_team)
    session.commit()
    session.refresh(new_team)
    return response(
        status_code=status.HTTP_201_CREATED,
        message="Team created successfully",
        data={"team_id": str(new_team.id), "team_name": new_team.name},
    )


@team_router.post(
    "/add-user-to-team", dependencies=[Depends(team_admin_or_global_admin)]
)
def add_user_to_team(
    email: str,
    team_id: str,
    role: schema.Role = schema.Role.user,
    session: Session = Depends(get_session),
):
    """
    Add a user to a team.
    Parameters:
    - email: The email of the user to add to the team.
    - team_id: The ID of the team to add the user to.
    - role: The role of the user in the team (default: user).
    - session: The database session (dependency).

    Returns:
    - A JSON response with the user ID and team ID upon successful addition.
    """
    user: Optional[schema.User] = (
        session.query(schema.User).filter_by(email=email).first()
    )
    team: Optional[schema.Team] = session.query(schema.Team).get(team_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    # Use `exists()` instead of fetching whole object
    if session.query(
        session.query(schema.UserTeam)
        .filter_by(user_id=user.id, team_id=team.id)
        .exists()
    ).scalar():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already a member of this team",
        )

    new_user_team = schema.UserTeam(user_id=user.id, team_id=team.id, role=role)
    session.add(new_user_team)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="User added to the team successfully",
        data={"user_id": str(user.id), "team_id": str(team.id)},
    )


@team_router.post(
    "/assign-team-admin", dependencies=[Depends(team_admin_or_global_admin)]
)
def assign_team_admin(
    email: str,
    team_id: str,
    session: Session = Depends(get_session),
):
    """
    Assign a user as a team admin.

    Parameters:
    - email: The email of the user to be assigned as team admin.
    - team_id: The ID of the team where the user will be assigned as admin.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the user ID and team ID upon successful assignment.
    """
    # Fetch both user and the corresponding user-team relation in one query
    user_team = (
        session.query(schema.UserTeam)
        .join(schema.User)
        .join(schema.Team)
        .filter(schema.User.email == email, schema.Team.id == team_id)
        .options(selectinload(schema.UserTeam.user), selectinload(schema.UserTeam.team))
        .first()
    )

    if user_team:
        # If user-team relationship exists, just update the role
        user_team.role = schema.Role.team_admin
    else:
        # Fetch user and team in one go if the user-team relationship doesn't exist
        user, team = (
            session.query(schema.User, schema.Team)
            .filter(schema.User.email == email, schema.Team.id == team_id)
            .first()
        )

        if not user or not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User or Team not found",
            )

        # Create new user-team relationship and assign the role
        user_team = schema.UserTeam(
            user_id=user.id, team_id=team.id, role=schema.Role.team_admin
        )
        session.add(user_team)

    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User {email} has been successfully assigned as team admin for team ID {team_id}.",
        data={"user_id": str(user_team.user_id), "team_id": str(user_team.team_id)},
    )


@team_router.delete("/delete-team", dependencies=[Depends(global_admin_only)])
def delete_team(team_id: str, session: Session = Depends(get_session)):
    """
    Delete a team.

    Parameters:
    - team_id: The ID of the team to delete.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the deleted team ID.
    """
    team: Optional[schema.Team] = (
        session.query(schema.Team)
        .options(selectinload(schema.Team.users), selectinload(schema.Team.models))
        .get(team_id)
    )

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    # Delete all user-team relationships and update model access levels
    # Bulk delete and update operations
    session.query(schema.UserTeam).filter_by(team_id=team.id).delete(
        synchronize_session=False
    )
    session.query(schema.Model).filter_by(team_id=team.id).update(
        {"access_level": schema.Access.private, "team_id": None},
        synchronize_session=False,
    )

    session.delete(team)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Team deleted successfully",
        data={"team_id": str(team.id)},
    )


@team_router.post("/add-model-to-team", dependencies=[Depends(is_model_owner)])
def add_model_to_team(
    model_identifier: str,
    team_id: str,
    session: Session = Depends(get_session),
):
    """
    Add a model to a team.

    Parameters:
    - model_identifier: The identifier of the model to add to the team.
    - team_id: The ID of the team to add the model to.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the model ID and team ID upon successful addition.
    """
    model: Optional[schema.Model] = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
        )
    if model.team_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model already belongs to a team",
        )

    team: Optional[schema.Team] = session.query(schema.Team).get(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    model.team_id = team.id
    model.access_level = schema.Access.protected

    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Model added to team successfully",
        data={"model_id": str(model.id), "team_id": str(team.id)},
    )


@team_router.post("/remove-model-from-team", dependencies=[Depends(is_model_owner)])
def remove_model_from_team(
    model_identifier: str,
    session: Session = Depends(get_session),
):
    """
    Remove a model from a team.

    Parameters:
    - model_identifier: The identifier of the model to remove from the team.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the model ID upon successful removal.
    """
    model: Optional[schema.Model] = get_model_from_identifier(model_identifier, session)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
        )

    model.team_id = None
    model.access_level = schema.Access.private

    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Model removed from team successfully",
        data={"model_id": str(model.id)},
    )


@team_router.post(
    "/remove-user-from-team", dependencies=[Depends(team_admin_or_global_admin)]
)
def remove_user_from_team(
    email: str,
    team_id: str,
    session: Session = Depends(get_session),
):
    """
    Remove a user from a team.

    Parameters:
    - email: The email of the user to remove from the team.
    - team_id: The ID of the team to remove the user from.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the user ID and team ID upon successful removal.
    """
    user_team: Optional[schema.UserTeam] = (
        session.query(schema.UserTeam)
        .join(schema.User)
        .filter(schema.User.email == email, schema.UserTeam.team_id == team_id)
        .first()
    )

    if not user_team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or Team not found",
        )

    # Bulk update models
    session.query(schema.Model).filter_by(
        user_id=user_team.user_id, team_id=team_id
    ).update(
        {"access_level": schema.Access.private, "team_id": None},
        synchronize_session=False,
    )

    session.delete(user_team)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="User removed from the team successfully",
        data={"user_id": str(user_team.user_id), "team_id": str(team_id)},
    )


@team_router.post(
    "/remove-team-admin", dependencies=[Depends(team_admin_or_global_admin)]
)
def remove_team_admin(
    email: str,
    team_id: str,
    session: Session = Depends(get_session),
):
    """
    Remove a user's team admin role.

    Parameters:
    - email: The email of the user to remove as team admin.
    - team_id: The ID of the team from which the user's admin role will be removed.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the user ID and team ID upon successful removal of the admin role.
    """
    user_team: Optional[schema.UserTeam] = (
        session.query(schema.UserTeam)
        .join(schema.User)
        .filter(schema.User.email == email, schema.UserTeam.team_id == team_id)
        .first()
    )

    if not user_team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of this team",
        )

    if user_team.role != schema.Role.team_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a team admin of this team",
        )

    user_team.role = schema.Role.user
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Team admin role removed successfully",
        data={"user_id": str(user_team.user_id), "team_id": str(user_team.team_id)},
    )


@team_router.get("/list")
def list_accessible_teams(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    List all teams related to that user.

    Parameters:
    - session: Session - The database session (dependency).
    - authenticated_user: AuthenticatedUser - The authenticated user (dependency).

    Returns:
    Global Admin:-
        - A JSON response with the list of all teams.
    Non Global Admin:-
        - A JSON response with the list of accessible teams.
    """

    user: schema.User = authenticated_user.user

    # Query to filter teams based on team_id present in user_teams
    query = session.query(schema.Team)
    if not user.global_admin:
        user_teams = [ut.team_id for ut in user.teams]
        query = query.filter(
            schema.Team.id.in_(user_teams)
        )  # Filter teams where team_id is in user_teams

    teams_info = [
        {
            "id": team.id,
            "name": team.name,
        }
        for team in query.all()
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the list of all teams",
        data=jsonable_encoder(teams_info),
    )


@team_router.get("/team-users", dependencies=[Depends(team_admin_or_global_admin)])
def list_team_users(
    team_id: str,
    session: Session = Depends(get_session),
):
    """
    List all users in a specific team.

    Parameters:
    - team_id: The ID of the team to retrieve users for.
    - session: The database session (dependency).

    Returns:
    - A JSON response with the list of users in the team.
    """
    user_teams: List[schema.UserTeam] = (
        session.query(schema.UserTeam)
        .options(selectinload(schema.UserTeam.user))
        .filter(schema.UserTeam.team_id == team_id)
        .all()
    )

    users_info = [
        {
            "user_id": user_team.user_id,
            "username": user_team.user.username,
            "email": user_team.user.email,
            "role": user_team.role,
        }
        for user_team in user_teams
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved users in the team",
        data=jsonable_encoder(users_info),
    )
