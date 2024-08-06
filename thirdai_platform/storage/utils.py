import datetime
import os

import jwt


def create_token(expiration_min=15, **kwargs):
    access_token_expires = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=expiration_min
    )
    payload = {"exp": access_token_expires, **kwargs}

    access_token = jwt.encode(
        payload=payload,
        key=os.getenv("JWT_SECRET"),
        algorithm="HS256",
    )
    return access_token


def verify_token(token):
    try:
        # This function automatically checks for token expiration:
        # https://pyjwt.readthedocs.io/en/stable/usage.html#expiration-time-claim-exp
        payload = jwt.decode(
            jwt=token,
            key=os.getenv("JWT_SECRET"),
            algorithms=["HS256"],
        )
        return payload
    except jwt.PyJWTError:
        raise ValueError("Token is not valid")
