import logging
import os
from contextlib import contextmanager

from auth.utils import identity_provider, keycloak_admin
from backend.utils import hash_password
from database import schema
from database.schema import SQLDeclarativeBase as Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_uri = os.getenv("DATABASE_URI")
if db_uri is None:
    raise ValueError("No DATABASE_URI environment variable set")

admin_username = os.getenv("ADMIN_USERNAME")
admin_mail = os.getenv("ADMIN_MAIL")
admin_password = os.getenv("ADMIN_PASSWORD")

env_variable_names = [
    "ADMIN_USERNAME",
    "ADMIN_MAIL",
    "ADMIN_PASSWORD",
]

# Check if any of the environment variables are missing
missing_variables = [var for var in env_variable_names if os.getenv(var) is None]

if missing_variables:
    raise FileNotFoundError(
        f"The following environment variables are missing: {', '.join(missing_variables)}"
    )

# Determine the environment
app_env = os.getenv("APP_ENV", "Production")

# Set the echo parameter based on the environment
echo = True if app_env == "development" else False

# Create the SQLAlchemy engine
engine = create_engine(
    db_uri,
    echo=echo,  # Controls whether SQL statements are logged. Useful for debugging in development.
    pool_size=20,  # Number of connections to maintain in the pool for efficient connection reuse.
    max_overflow=30,  # Additional connections allowed beyond the pool size for handling spikes in load.
    pool_timeout=30,  # Maximum time (in seconds) to wait for a connection before timing out.
)

Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


"""Create all tables defined in the Base metadata."""
Base.metadata.create_all(engine, checkfirst=True)


def get_session():
    session = Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class AdminAddition:
    @classmethod
    def add_admin(
        cls,
        admin_mail: str,
        admin_username: str,
        admin_password: str,
    ):
        """
        Add or update a global admin based on the current identity provider (Keycloak or Postgres).
        If Keycloak is used, Google as an identity provider can also be added or updated.
        """
        with contextmanager(get_session)() as session:

            if identity_provider == "keycloak":
                # Keycloak logic
                keycloak_user_id = keycloak_admin.get_user_id(admin_username)
                if keycloak_user_id:
                    try:
                        keycloak_admin.update_user(
                            keycloak_user_id,
                            {
                                "email": admin_mail,
                                "emailVerified": True,
                                "firstName": admin_username,
                                "lastName": "User",
                            },
                        )
                    except Exception as e:
                        # Check if the update was applied anyway
                        updated_user = keycloak_admin.get_user(keycloak_user_id)
                        if (
                            updated_user.get("email") == admin_mail
                            and updated_user.get("emailVerified") == True
                            and updated_user.get("firstName") == admin_username
                            and updated_user.get("lastName") == "User"
                        ):
                            logging.warning(
                                f"Caught an exception after attempting to update user '{admin_username}', "
                                f"but the user now appears to have the updated fields. Skipping error."
                            )
                        else:
                            # Update truly failed
                            logging.error(
                                f"Error updating user '{admin_username}': {str(e)}"
                            )
                            raise e
                else:
                    user_payload = {
                        "username": admin_username,
                        "email": admin_mail,
                        "enabled": True,
                        "emailVerified": True,
                        "credentials": [
                            {
                                "type": "password",
                                "value": admin_password,
                                "temporary": False,
                            }
                        ],
                        "realmRoles": ["admin"],
                        "firstName": admin_username,
                        "lastName": "User",
                    }
                    try:
                        keycloak_user_id = keycloak_admin.create_user(
                            user_payload,
                            exist_ok=True,
                        )
                    except Exception as e:
                        # Check if the user now exists
                        check_user_id = keycloak_admin.get_user_id(admin_username)
                        if check_user_id:
                            logging.warning(
                                f"Caught an exception after attempting to create user '{admin_username}', "
                                f"but the user now appears to exist. Skipping error."
                            )
                            keycloak_user_id = check_user_id
                        else:
                            # User truly failed to create
                            logging.error(
                                f"Error creating user '{admin_username}': {str(e)}"
                            )
                            raise e

            try:
                user: schema.User = (
                    session.query(schema.User)
                    .filter(schema.User.email == admin_mail)
                    .first()
                )

                if not user:
                    user = schema.User(
                        username=admin_username,
                        email=admin_mail,
                        password_hash=hash_password(admin_password),
                        verified=True,
                        global_admin=True,
                    )
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                else:
                    user.global_admin = True
                    session.commit()
            except Exception as e:
                # Attempt to check if the user was already added
                existing_user = (
                    session.query(schema.User)
                    .filter(schema.User.email == admin_mail)
                    .first()
                )
                if existing_user and existing_user.global_admin:
                    logging.warning(
                        f"Attempted to add admin user '{admin_username}', but the user already exists as a global admin. Skipping error."
                    )
                else:
                    # If the user doesn't exist or isn't a global admin, re-raise the exception
                    logging.error(
                        f"Error adding/updating admin user '{admin_username}': {str(e)}"
                    )
                    raise e


AdminAddition.add_admin(
    admin_mail=admin_mail,
    admin_username=admin_username,
    admin_password=admin_password,
)
