import os
import pathlib
from typing import List, Optional
from urllib.parse import urlencode, urljoin

import bcrypt
from auth.jwt import AuthenticatedUser, create_access_token, verify_access_token
from backend.auth_dependencies import global_admin_only
from backend.mailer import Mailer
from backend.utils import hash_password, response
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from auth.jwt import identity_provider_type
from auth.utils import keycloak_admin

user_router = APIRouter()
basic_security = HTTPBasic()

root_folder = pathlib.Path(__file__).parent
template_directory = root_folder.joinpath("../templates/").resolve()
templates = Jinja2Templates(directory=template_directory)


class AccessToken(BaseModel):
    access_token: str


class AccountSignupBody(BaseModel):
    username: str
    email: str
    password: str


class AdminRequest(BaseModel):
    email: str


def delete_all_models_for_user(user_to_delete, session):
    team_admins: List[schema.UserTeam] = (
        session.query(schema.UserTeam).filter_by(role=schema.Role.team_admin).all()
    )
    team_admin_map = {
        team_admin.team_id: team_admin.user_id for team_admin in team_admins
    }

    models: List[schema.Model] = user_to_delete.models

    for model in models:
        if model.access_level == schema.Access.protected:
            new_owner_id = team_admin_map.get(model.team_id, user_to_delete.id)
        else:
            # current user is the global_admin.
            new_owner_id = user_to_delete.id

        model.user_id = new_owner_id

    session.bulk_save_objects(models)


def send_verification_mail(email: str, verification_token: str, username: str):
    """
    Send a verification email to the user.

    Parameters:
    - email: The email address of the user.
    - verification_token: The verification token for the user.
    - username: The username of the user.

    Sends an email with a verification link to the provided email address.
    """
    subject = "Verify Your Email Address"
    base_url = os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT")
    args = {"verification_token": verification_token}
    verify_link = urljoin(base_url, f"api/user/redirect-verify?{urlencode(args)}")
    body = "<p>Please click the following link to verify your email address: <a href={}>verify</a></p>".format(
        verify_link
    )

    Mailer(
        to=f"{username} <{email}>",
        subject=subject,
        body=body,
    )


@user_router.post("/email-signup-basic")
def email_signup(
    body: AccountSignupBody,
    session: Session = Depends(get_session),
):
    """
    Sign up a new user with email and password.

    Parameters:
    - body: The body of the request containing username, email, and password.
        - Example:
        ```json
        {
            "username": "johndoe",
            "email": "johndoe@example.com",
            "password": "securepassword"
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the signup status.
    """
    user: Optional[schema.User] = (
        session.query(schema.User)
        .filter(
            (schema.User.email == body.email) | (schema.User.username == body.username)
        )
        .first()
    )

    if user:
        if user.email == body.email:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="There is already an account associated with this email.",
            )
        else:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="There is already a user associated with this name.",
            )

    hashed_password = hash_password(body.password)
    is_test_environment = os.getenv("TEST_ENVIRONMENT", "False") == "True"

    new_user_identity = schema.UserPostgresIdentityProvider(
        username=body.username,
        email=body.email,
        password_hash=hashed_password,
        verified=is_test_environment,
    )

    try:
        session.add(new_user_identity)
        session.commit()
        session.refresh(new_user_identity)

        new_user = schema.User(
            id=new_user_identity.id,
            username=body.username,
            email=body.email,
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        if not is_test_environment:
            send_verification_mail(
                new_user.email,
                new_user_identity.verification_token,
                new_user.username,
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully signed up via email.",
            data={
                "user": {
                    "username": new_user.username,
                    "email": new_user.email,
                    "user_id": str(new_user.id),
                },
            },
        )

    except IntegrityError:
        session.rollback()
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="User with this email or username already exists.",
        )


@user_router.post("/add-global-admin", dependencies=[Depends(global_admin_only)])
def add_global_admin(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
):
    """
    Promote a user to global admin.

    Parameters:
    - admin_request: The request body containing the user's email.
        - Example:
        ```json
        {
            "email": "user@example.com"
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the success of the operation.
    """
    email = admin_request.email
    user: Optional[schema.User] = (
        session.query(schema.User).filter(schema.User.email == email).first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not registered yet.",
        )

    # Update the user's role to global admin
    user.global_admin = True
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User {email} has been successfully added as a global admin",
    )


@user_router.post("/delete-global-admin", dependencies=[Depends(global_admin_only)])
def demote_global_admin(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
):
    """
    Demote a global admin to a regular user.

    Parameters:
    - admin_request: The request body containing the user's email.
        - Example:
        ```json
        {
            "email": "user@example.com"
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the success of the operation.
    """
    email = admin_request.email
    user: Optional[schema.User] = (
        session.query(schema.User).filter(schema.User.email == email).first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not registered yet.",
        )

    if not user.global_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a global admin.",
        )

    # Check if there is more than one global admin
    another_admin_exists = (
        session.query(schema.User)
        .filter(schema.User.global_admin == True, schema.User.id != user.id)
        .first()
    )

    if not another_admin_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There must be at least one global admin.",
        )

    # Update the user's role to normal user
    user.global_admin = False
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User {email} has been successfully removed as a global admin and is now a normal user.",
    )


@user_router.delete("/delete-user")
def delete_user(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
    current_user: schema.User = Depends(global_admin_only),
):
    """
    Delete a user from the system and reassign their models.

    Parameters:
    - admin_request: The request body containing the user's email.
        - Example:
        ```json
        {
            "email": "user@example.com"
        }
        ```
    - session: The database session (dependency).
    - current_user: The current authenticated global admin (dependency).

    Returns:
    - A JSON response indicating the success of the operation.
    """
    email = admin_request.email

    user: Optional[schema.User] = (
        session.query(schema.User)
        .options(joinedload(schema.User.models))
        .filter(schema.User.email == email)
        .first()
    )

    if not user:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"User with email {email} not found.",
        )

    delete_all_models_for_user(user, session)

    if user:
        session.delete(user)

    if identity_provider_type == "postgres":
        user_identity = (
            session.query(schema.UserPostgresIdentityProvider)
            .filter(schema.UserPostgresIdentityProvider.email == email)
            .first()
        )
        if user_identity:
            session.delete(user_identity)
    elif identity_provider_type == "keycloak":
        try:
            keycloak_admin.delete_user(user.id)
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Failed to delete user in Keycloak: {str(e)}",
            )

    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User with email {email} has been successfully deleted.",
    )


@user_router.get("/redirect-verify")
def redirect_email_verify(verification_token: str, request: Request):
    """
    Redirect to email verification endpoint.

    Parameters:
    - verification_token: The verification token for the user.
    - request: The HTTP request object (dependency).

    Returns:
    - A HTML response with the redirection page.
    """
    base_url = os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT")
    args = {"verification_token": verification_token}
    verify_url = urljoin(base_url, f"api/user/email-verify?{urlencode(args)}")

    context = {"request": request, "verify_url": verify_url}
    return templates.TemplateResponse("verify_email_sent.html", context=context)


@user_router.post("/email-verify")
def email_verify(verification_token: str, session: Session = Depends(get_session)):
    """
    Verify the user's email with the provided token.

    Parameters:
    - verification_token: The verification token for the user.
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the verification status.
    """
    user_identity = (
        session.query(schema.UserPostgresIdentityProvider)
        .filter(
            schema.UserPostgresIdentityProvider.verification_token == verification_token
        )
        .first()
    )

    if not user_identity:
        return {
            "message": "Token not found: this could be due to user already being verified or invalid token."
        }

    user_identity.verified = True
    user_identity.verification_token = None
    session.commit()

    return {"message": "Email verification successful."}


@user_router.get("/email-login")
def email_login(
    credentials: HTTPBasicCredentials = Depends(basic_security),
    session: Session = Depends(get_session),
):
    """
    Log in a user with email and password.

    Parameters:
    - credentials: The HTTP basic credentials (dependency).
        - Example:
        ```json
        {
            "username": "johndoe@example.com",
            "password": "securepassword"
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the login status and user details along with an access token.
    """
    user_identity = (
        session.query(schema.UserPostgresIdentityProvider)
        .filter(
            (schema.UserPostgresIdentityProvider.username == credentials.username)
            | (schema.UserPostgresIdentityProvider.email == credentials.email)
        )
        .first()
    )
    if not user_identity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if not user_identity.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password authentication not available for this user.",
        )

    if not bcrypt.checkpw(
        credentials.password.encode("utf-8"),
        user_identity.password_hash.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password."
        )

    if not user_identity.verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not verified yet.",
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully logged in via email",
        data={
            "user": {
                "username": user_identity.username,
                "email": user_identity.email,
                "user_id": str(user_identity.id),
            },
            "access_token": create_access_token(user_identity.id, expiration_min=120),
            "verified": user_identity.verified,
        },
    )


@user_router.post("/email-login-with-keycloak")
def email_login_with_keycloak(
    access_token: AccessToken,
    session: Session = Depends(get_session),
):
    """
    This endpoint handles the login process using a Keycloak access token.
    It verifies the token directly in this function and returns user info.
    """
    try:
        verified_user = verify_access_token(access_token.access_token, session)

        user = verified_user.user

        if not user:
            return response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="User not found in local database.",
            )

        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully logged in using Keycloak token.",
            data={
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "user_id": str(user.id),
                },
                "access_token": access_token.access_token,
            },
        )
    except HTTPException as e:
        return response(status_code=e.status_code, message=e.detail)
    except Exception as e:
        return response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"An unexpected error occurred: {str(e)}",
        )


class VerifyResetPassword(BaseModel):
    email: str
    reset_password_code: int
    new_password: str


@user_router.post("/new-password", include_in_schema=False)
def reset_password_verify(
    body: VerifyResetPassword,
    session: Session = Depends(get_session),
):
    """
    Reset the user's password after verifying the reset code.

    Parameters:
    - body: The request body containing the email, reset password code, and new password.
        - Example:
        ```json
        {
            "email": "johndoe@example.com",
            "reset_password_code": 123456,
            "new_password": "newsecurepassword"
        }
        ```
    - session: The database session (dependency).

    Returns:
    - A JSON response indicating the password reset status.
    """
    user_identity = (
        session.query(schema.UserPostgresIdentityProvider)
        .filter(schema.UserPostgresIdentityProvider.email == body.email)
        .first()
    )

    if not user_identity:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="This email is not registered with any account.",
        )

    if not user_identity.reset_password_code:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Click on forgot password to get verification code.",
        )

    if user_identity.reset_password_code != body.reset_password_code:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Entered wrong reset password code.",
        )

    user_identity.reset_password_code = None
    user_identity.password_hash = hash_password(body.new_password)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully changed the password.",
    )


@user_router.get("/all-users", dependencies=[Depends(global_admin_only)])
def list_all_users(session: Session = Depends(get_session)):
    """
    List all users in the system along with their team memberships and roles.

    Parameters:
    - session: The database session (dependency).

    Returns:
    - A JSON response with the list of all users and their team details.
    """
    users: List[schema.User] = (
        session.query(schema.User)
        .options(joinedload(schema.User.teams).joinedload(schema.UserTeam.team))
        .all()
    )

    users_info = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "global_admin": user.global_admin,
            "teams": [
                {
                    "team_id": user_team.team_id,
                    "team_name": user_team.team.name,
                    "role": user_team.role,
                }
                for user_team in user.teams
            ],
        }
        for user in users
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the list of all users",
        data=jsonable_encoder(users_info),
    )


@user_router.get("/info")
def get_user_info(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    """
    Get detailed information about the authenticated user.

    Parameters:
    - session: The database session (dependency).
    - authenticated_user: The authenticated user (dependency).

    Returns:
    - A JSON response with the user's information.
    """
    user: Optional[schema.User] = (
        session.query(schema.User)
        .options(joinedload(schema.User.teams).joinedload(schema.UserTeam.team))
        .filter(schema.User.id == authenticated_user.user.id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user_info = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "global_admin": user.global_admin,
        "teams": [
            {
                "team_id": user_team.team_id,
                "team_name": user_team.team.name,
                "role": user_team.role,
            }
            for user_team in user.teams
        ],
    }

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully retrieved user information",
        data=jsonable_encoder(user_info),
    )
