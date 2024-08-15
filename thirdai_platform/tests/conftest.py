from sqlalchemy import create_engine, text, NullPool
import os
import random
import pytest


@pytest.fixture(autouse=True, scope="session")
def initialize_database():
    db_uri = "postgresql://postgres@localhost:5432"
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
