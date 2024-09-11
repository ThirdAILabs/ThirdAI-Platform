import os

from sqlalchemy import MetaData, create_engine


def check_tables_existence(db_uri, table_name):
    engine = create_engine(db_uri)
    metadata = MetaData()

    # Reflect the tables from the database
    metadata.reflect(bind=engine)

    # Check if the specified table exists
    return table_name in metadata.tables


if __name__ == "__main__":
    # Replace this with your actual database URI
    db_uri = os.getenv("DATABASE_URI", None)
    table_name = "models"

    if check_tables_existence(db_uri, table_name):
        print("Table exists.")
    else:
        print("Table does not exist.")
        exit(1)
