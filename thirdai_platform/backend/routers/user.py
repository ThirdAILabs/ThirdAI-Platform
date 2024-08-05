import os
import pathlib
from urllib.parse import urlencode, urljoin

import bcrypt
from auth.jwt import AuthenticatedUser, create_access_token, verify_access_token
from backend.mailer import Mailer
from thirdai_platform.backend.routers.utils import hash_password, response
from database import schema
from database.session import get_session
from backend.auth_dependencies import get_current_user, verify_admin_access
from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

user_router = APIRouter()
basic_security = HTTPBasic()

root_folder = pathlib.Path(__file__).parent
template_directory = root_folder.joinpath("../templates/").resolve()
templates = Jinja2Templates(directory=template_directory)


class AccountSignupBody(BaseModel):
    username: str
    email: str
    password: str


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
    user = session.query(schema.User).filter(schema.User.email == body.email).first()
    if user:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="There is already an account associated with this email.",
        )

    name = (
        session.query(schema.User).filter(schema.User.username == body.username).first()
    )
    if name:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="There is already a user associated with this name.",
        )

    domain = body.email.split("@")[1]
    organization = (
        session.query(schema.Organization)
        .filter(schema.Organization.domain == domain)
        .first()
    )
    if not organization:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Organization does not exist for the provided email domain.",
        )

    try:
        user = schema.User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
            verified=False,
            organization_id=organization.id,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        send_verification_mail(
            user.email,
            str(user.verification_token),
            user.username,
        )
    except Exception as err:
        return response(status_code=status.HTTP_400_BAD_REQUEST, message=str(err))

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully signed up via email.",
        data={
            "user": {
                "username": user.username,
                "email": user.email,
                "user_id": str(user.id),
            },
        },
    )


@user_router.post("/add-admin", dependencies=[Depends(verify_admin_access)])
def add_admin(
    email: str,
    session: Session = Depends(get_session),
):
    user: schema.User = (
        session.query(schema.User).filter(schema.User.email == email).first()
    )

    if not user:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="User is not registered yet.",
        )

    user.role = schema.Role.admin
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User {email} has been successfully added as an admin.",
    )


@user_router.delete("/delete-user", dependencies=[Depends(verify_admin_access)])
def delete_user(
    user_id: str,
    session: Session = Depends(get_session),
):
    user = session.query(schema.User).filter(schema.User.id == user_id).first()

    if not user:
        return response(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"User with id {user_id} not found.",
        )

    session.delete(user)
    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message=f"User with id {user_id} has been successfully deleted.",
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
    user: schema.User = (
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
    user: schema.User = (
        session.query(schema.User)
        .filter(schema.User.email == credentials.username)
        .first()
    )
    if not user:
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="User is not yet registered.",
        )
    byte_password = credentials.password.encode("utf-8")
    if not bcrypt.checkpw(byte_password, user.password_hash.encode("utf-8")):
        return response(
            status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid password."
        )

    # if not user.verified:
    #     return response(
    #         status_code=status.HTTP_400_BAD_REQUEST, message="User is not verified yet."
    #     )

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
    The password change process involves verification of the reset password code sent to the
    user's email, ensuring security. Once verified, the system allows the user to update their
    password seamlessly.
    """
    user: schema.User = (
        session.query(schema.User).filter(schema.User.email == body.email).first()
    )

    if not user:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="This email is not registered with any account.",
        )

    if not user.reset_password_code:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Click on forgot password to get verification code.",
        )

    if user.reset_password_code != body.reset_password_code:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="entered wrong reset password code.",
        )

    user.reset_password_code = None

    user.password_hash = hash_password(body.new_password)

    session.commit()

    return response(
        status_code=status.HTTP_200_OK,
        message="Successfully changed the password.",
    )
