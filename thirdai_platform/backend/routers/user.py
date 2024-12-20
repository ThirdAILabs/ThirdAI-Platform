import os
import pathlib
import re
from typing import List, Optional
from urllib.parse import urlencode, urljoin

import bcrypt
from auth.jwt import AuthenticatedUser, create_access_token, verify_access_token
from auth.utils import identity_provider, keycloak_admin, keycloak_openid
from backend.auth_dependencies import global_admin_only
from backend.mailer import mailer
from backend.utils import hash_password
from database import schema
from database.session import get_session
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from platform_common.utils import get_section, response
from pydantic import BaseModel
from sqlalchemy import exists
from sqlalchemy.orm import Session, selectinload

user_router = APIRouter()
basic_security = HTTPBasic()

root_folder = pathlib.Path(__file__).parent
template_directory = root_folder.joinpath("../templates/").resolve()
templates = Jinja2Templates(directory=template_directory)

docs_file = root_folder.joinpath("../../docs/user_endpoints.txt")

with open(docs_file) as f:
    docs = f.read()


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


def slugify_username(preferred_username):
    safe_username = re.sub(r"[^\w]", "", preferred_username)

    return safe_username


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

    mailer(
        to=f"{username} <{email}>",
        subject=subject,
        body=body,
    )


def send_reset_password_code(email: str, reset_password_code: int):
    subject = "Your Reset Password Code"

    body = (
        f"The verification code for resetting your password is {reset_password_code}."
    )

    mailer(
        to=f"<{email}>",
        subject=subject,
        body=body,
    )


@user_router.post(
    "/email-signup-basic",
    summary="Email SignUp",
    description=get_section(docs, "Email Signup"),
)
def email_signup(
    body: AccountSignupBody,
    session: Session = Depends(get_session),
):
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

    try:
        is_test_environment = os.getenv("AIRGAPPED", "False") == "True"

        new_user = schema.User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
            verified=is_test_environment,
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        if not is_test_environment:
            send_verification_mail(
                new_user.email,
                str(new_user.verification_token),
                new_user.username,
            )

    except Exception as err:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(err))

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


@user_router.post(
    "/add-global-admin",
    dependencies=[Depends(global_admin_only)],
    summary="Add Global Admin",
    description=get_section(docs, "Add Global Admin"),
)
def add_global_admin(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
):
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


@user_router.post(
    "/delete-global-admin",
    dependencies=[Depends(global_admin_only)],
    summary="Demote Global Admin",
    description=get_section(docs, "Demote Global Admin"),
)
def demote_global_admin(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
):
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
    # Dont need the data so just fetching whether another admin exists or not.
    another_admin_exists = session.query(
        exists().where(schema.User.global_admin == True, schema.User.id != user.id)
    ).scalar()

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


@user_router.delete(
    "/delete-user", summary="Delete User", description=get_section(docs, "Delete User")
)
def delete_user(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
    current_user: schema.User = Depends(global_admin_only),
):
    email = admin_request.email

    user: Optional[schema.User] = (
        session.query(schema.User)
        .options(selectinload(schema.User.models))
        .filter(schema.User.email == email)
        .first()
    )

    if not user:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"User with email {email} not found.",
        )

    delete_all_models_for_user(user, session)

    session.delete(user)

    if identity_provider == "keycloak":
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


@user_router.get("/redirect-verify", include_in_schema=False)
def redirect_email_verify(verification_token: str, request: Request):
    base_url = os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT")
    args = {"verification_token": verification_token}
    verify_url = urljoin(base_url, f"api/user/email-verify?{urlencode(args)}")

    context = {"request": request, "verify_url": verify_url}
    return templates.TemplateResponse("verify_email_sent.html", context=context)


@user_router.post("/email-verify", include_in_schema=False)
def email_verify(verification_token: str, session: Session = Depends(get_session)):
    user: Optional[schema.User] = (
        session.query(schema.User)
        .filter(schema.User.verification_token == verification_token)
        .first()
    )

    if not user:
        return {
            "message": "Token not found: this could be due to user already being verified or invalid token."
        }

    user.verified = True
    user.verification_token = None
    session.commit()

    return {"message": "Email verification successful."}


@user_router.get(
    "/email-login", summary="Email Login", description=get_section(docs, "Email Login")
)
def email_login(
    credentials: HTTPBasicCredentials = Depends(basic_security),
    session: Session = Depends(get_session),
):
    user: Optional[schema.User] = (
        session.query(schema.User)
        .filter(schema.User.email == credentials.username)
        .first()
    )
    if not user:
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="User is not yet registered.",
        )

    if not user.verified:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST, message="User is not verified yet."
        )

    byte_password = credentials.password.encode("utf-8")
    if not bcrypt.checkpw(byte_password, user.password_hash.encode("utf-8")):
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid password."
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully logged in via email",
        data={
            "user": {
                "username": user.username,
                "email": user.email,
                "user_id": str(user.id),
            },
            "access_token": create_access_token(user.id, expiration_min=120),
            "verified": user.verified,
        },
    )


@user_router.post(
    "/email-login-with-keycloak",
    summary="Email Login with Keycloak",
    description=get_section(docs, "Email Login with Keycloak"),
)
def email_login_with_keycloak(
    access_token: AccessToken,
    session: Session = Depends(get_session),
):
    try:
        user_info = keycloak_openid.userinfo(access_token.access_token)

        keycloak_user_id = user_info.get("sub")

        user = (
            session.query(schema.User)
            .filter(schema.User.email == user_info.get("email"))
            .first()
        )
        if not user:
            user = schema.User(
                id=keycloak_user_id,
                username=slugify_username(user_info.get("preferred_username")),
                email=user_info.get("email"),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

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


@user_router.get(
    "/reset-password",
    summary="Reset Password",
    description=get_section(docs, "Reset Password"),
)
def reset_password(
    email: str,
    session: Session = Depends(get_session),
):
    user: schema.User = (
        session.query(schema.User).filter(schema.User.email == email).first()
    )

    if not user:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="This email is not registered with any account.",
        )

    reset_code = schema.PasswordReset.generate_reset_code(num=6)

    reset_code_hash = bcrypt.hashpw(
        reset_code.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    expiration_time = schema.PasswordReset.generate_expiration_time(minutes=15)
    password_reset = schema.PasswordReset(
        user_id=user.id,
        reset_code_hash=reset_code_hash,
        expiration_time=expiration_time,
    )

    # Delete any existing reset tokens for this user
    session.query(schema.PasswordReset).filter_by(user_id=user.id).delete()

    session.add(password_reset)
    session.commit()

    is_test_environment = os.getenv("AIRGAPPED", "False") == "True"

    if is_test_environment:
        return response(
            status_code=status.HTTP_200_OK,
            message="Successfully created the reset password code.",
            data={"reset_password_code": reset_code},
        )

    send_reset_password_code(email=email, reset_password_code=reset_code)

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully sent the verification code to mail.",
    )


class VerifyResetPassword(BaseModel):
    email: str
    reset_password_code: str
    new_password: str


@user_router.post(
    "/new-password",
    summary="New Password",
    description=get_section(docs, "New Password"),
)
def reset_password_verify(
    body: VerifyResetPassword,
    session: Session = Depends(get_session),
):
    user: Optional[schema.User] = (
        session.query(schema.User).filter(schema.User.email == body.email).first()
    )

    if not user:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="This email is not registered with any account.",
        )

    password_reset: schema.PasswordReset = (
        session.query(schema.PasswordReset)
        .filter(schema.PasswordReset.user_id == user.id)
        .first()
    )

    if not password_reset:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="No password reset request found. Please initiate a new password reset.",
        )

    if not password_reset.is_valid():
        # Delete the expired token
        session.delete(password_reset)
        session.commit()
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="The reset code has expired. Please request a new one.",
        )

    if not bcrypt.checkpw(
        body.reset_password_code.encode("utf-8"),
        password_reset.reset_code_hash.encode("utf-8"),
    ):
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid reset code.",
        )

    user.password_hash = hash_password(body.new_password)

    # Delete the used reset token
    session.delete(password_reset)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully changed the password.",
    )


@user_router.get(
    "/list",
    summary="List Accessible Users",
    description=get_section(docs, "List Accessible Users"),
)
def list_accessible_users(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: schema.User = authenticated_user.user

    # If the user is a Global Admin, return all users
    if user.global_admin:
        users = (
            session.query(schema.User)
            .options(selectinload(schema.User.teams).selectinload(schema.UserTeam.team))
            .all()
        )
    elif len(user.teams) != 0:
        # For non-global admins, return users who are part of the user's teams
        user_teams = [ut.team_id for ut in user.teams]
        users = (
            session.query(schema.User)
            .join(schema.UserTeam)
            .filter(schema.UserTeam.team_id.in_(user_teams))
            .distinct()  # Avoid duplicate users if they're part of multiple teams
            .options(selectinload(schema.User.teams).selectinload(schema.UserTeam.team))
            .all()
        )
    else:
        # If the user is not present in any team
        users = [user]

    # Build the response data with team membership information
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
            "verified": user.verified,
        }
        for user in users
    ]

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully got the list of all users",
        data=jsonable_encoder(users_info),
    )


@user_router.get(
    "/info", summary="Get User Info", description=get_section(docs, "Get User Info")
)
def get_user_info(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    user: Optional[schema.User] = (
        session.query(schema.User)
        .options(selectinload(schema.User.teams).selectinload(schema.UserTeam.team))
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


@user_router.get("/auth")
def get_user_info(
    session: Session = Depends(get_session),
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
    authorization: str = Header(None),
):
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Verified access token."},
        headers={"Authorization": authorization},
    )


@user_router.post(
    "/add-user",
    dependencies=[Depends(global_admin_only)],
    summary="Add User by Global Admin",
    description=get_section(docs, "Add User by Global Admin"),
)
def add_user_by_global_admin(
    body: AccountSignupBody,
    session: Session = Depends(get_session),
):
    global identity_provider

    if identity_provider == "keycloak":
        try:
            keycloak_user_id = keycloak_admin.get_user_id(body.username)
            if keycloak_user_id:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="There is already a user associated with this name.",
                )

            existing_users = keycloak_admin.get_users({"email": body.email})
            if existing_users:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="There is already an account associated with this email.",
                )

            keycloak_user_id = keycloak_admin.create_user(
                {
                    "username": body.username,
                    "email": body.email,
                    "enabled": True,
                    "emailVerified": True,
                    "credentials": [
                        {
                            "type": "password",
                            "value": body.password,
                            "temporary": False,
                        }
                    ],
                    "firstName": body.username,
                    "lastName": "User",
                }
            )

            new_user = schema.User(
                username=body.username,
                email=body.email,
                verified=True,
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)

        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"An error occurred while creating the user: {str(e)}",
            )

    else:
        # Check if the user already exists
        existing_user: Optional[schema.User] = (
            session.query(schema.User)
            .filter(
                (schema.User.email == body.email)
                | (schema.User.username == body.username)
            )
            .first()
        )

        if existing_user:
            if existing_user.email == body.email:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="There is already an account associated with this email.",
                )
            else:
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="There is already a user associated with this name.",
                )

        try:
            new_user = schema.User(
                username=body.username,
                email=body.email,
                password_hash=hash_password(body.password),
                verified=True,  # The user is added by Global admin, so he will be verified by default.
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)

        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"An error occurred while creating the user: {str(e)}",
            )

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Successfully added user {body.username}.",
        data={"user_id": str(new_user.id), "email": new_user.email},
    )


@user_router.post(
    "/verify-user",
    dependencies=[Depends(global_admin_only)],
    summary="Verify User by Global Admin",
    description=get_section(docs, "Verify User by Global Admin"),
)
def verify_user_by_global_admin(
    admin_request: AdminRequest,
    session: Session = Depends(get_session),
):
    global identity_provider

    if identity_provider == "keycloak":
        try:
            # Find the user in Keycloak by email
            users = keycloak_admin.get_users({"email": admin_request.email})
            if not users:
                return response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="User not found.",
                )
            user_info = users[0]
            user_id = user_info["id"]

            if user_info.get("emailVerified", False):
                return response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="User is already verified.",
                )

            keycloak_admin.update_user(
                user_id,
                {
                    "emailVerified": True,
                },
            )

            local_user = (
                session.query(schema.User)
                .filter(schema.User.email == admin_request.email)
                .first()
            )
            if local_user:
                local_user.verified = True
                session.commit()

        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"An error occurred while verifying the user: {str(e)}",
            )

    else:
        # Find the user by email
        user: Optional[schema.User] = (
            session.query(schema.User)
            .filter(schema.User.email == admin_request.email)
            .first()
        )

        if not user:
            return response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="User not found.",
            )

        if user.verified:
            return response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="User is already verified.",
            )

        # Verify the user
        try:
            user.verified = True
            user.verification_token = None  # Clear the verification token
            session.commit()
        except Exception as e:
            return response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"An error occurred while verifying the user: {str(e)}",
            )

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User {admin_request.email} has been successfully verified.",
    )
