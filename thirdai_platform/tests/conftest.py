import os
import random
import shutil

import pytest
from dotenv import load_dotenv
from sqlalchemy import NullPool, create_engine, text


@pytest.fixture(autouse=True, scope="session")
def setup_env():
    os.environ["LICENSE_PATH"] = os.path.join(
        os.path.dirname(__file__), "ndb_enterprise_license.json"
    )
    os.environ["JWT_SECRET"] = "SUPER_SECRET"
    os.environ["PLATFORM"] = "local"
    os.environ["PYTHON_PATH"] = "python3"
    os.environ["ADMIN_USERNAME"] = "admin"
    os.environ["ADMIN_MAIL"] = "admin@mail.com"
    os.environ["ADMIN_PASSWORD"] = "password"
    os.environ["TEST_ENVIRONMENT"] = "True"


@pytest.fixture(autouse=True, scope="session")
def initialize_database():
    load_dotenv()

    db_uri = os.environ["DB_BASE_URI"]
    db_name = f"model_bazaar_{random.randint(0, 1e6)}"

    eng = create_engine(db_uri, isolation_level="AUTOCOMMIT", poolclass=NullPool)

    with eng.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))

    os.environ["DATABASE_URI"] = f"{db_uri}/{db_name}"

    yield

    from database import session

    session.engine.dispose()

    with eng.connect() as conn:
        conn.execute(text(f"DROP DATABASE {db_name}"))


@pytest.fixture(autouse=True, scope="session")
def create_test_directory():
    test_dir = ".test_data"
    os.makedirs(test_dir, exist_ok=True)

    os.environ["SHARE_DIR"] = os.path.join(test_dir, "share_dir")

    yield

    shutil.rmtree(test_dir)
