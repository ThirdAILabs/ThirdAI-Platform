#!/bin/bash

# Check if alembic version exists
alembic current | grep -q "[a-f0-9]\{12\}"; 
if [ $? -ne 0 ]; then

    # If alembic version doesn't exist, check if tables exist
    python check_tables.py
    if [ $? -eq 0 ]; then

        # If tables exists, stamp the current alembic version to the first alembic version
        alembic stamp f2b04f674b1e
    fi
fi

alembic upgrade head

# Finally, run the Uvicorn server
uvicorn main:app --reload --host 0.0.0.0 --port 80