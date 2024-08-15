import os
import random

import pytest
from sqlalchemy import NullPool, create_engine, text


@pytest.fixture(autouse=True, scope="session")
def initialize_database():
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
