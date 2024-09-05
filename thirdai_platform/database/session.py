import os
from contextlib import contextmanager

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


# Adding a global_admin by default initially
class AdminAddition:
    @classmethod
    def add_admin(cls):
        with contextmanager(get_session)() as session:
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


AdminAddition.add_admin()
