## Alembic Configuration and Usage Guide

This guide provides step-by-step instructions to set up Alembic,
generate and apply new migration scripts, and ensure your migrations are
working correctly.

### Step 1: Install Alembic

To install Alembic and its required dependencies, run:

```bash
pip install alembic alembic-enums
```

### Step 2: Initialize Alembic

- Open your terminal and navigate to your project\'s root directory.

- Initialize Alembic by running:

    ```bash
    alembic init alembic
    ```

This command creates an `alembic` directory with the following
structure:

    - alembic/ 
        - env.py 
        - README 
        - script.py.mako 
        - versions/ # Directory for storing migration scripts 
        - alembic.ini # Alembic configuration file

### Step 3: Configure Alembic

- Edit `alembic.ini`

    - Open the `alembic.ini` file in your project\'s root directory.
    - Find the line starting with `sqlalchemy.url` and update it with your
database URL:
        ```bash
        sqlalchemy.url = postgresql://user:password@localhost/dbname
        ```

        Replace `postgresql`, `user`, `password`, `localhost`, and
`dbname` with your actual database credentials.

- Edit `env.py`

    - Open the `alembic/env.py` file. 
    - Import your SQLAlchemy `Base` model where your models are defined, and set the `target_metadata` to `Base.metadata`:
    
    ```python
    from your_application.models import Base # Update with your actual models file
    target_metadata = Base.metadata
    ```

    Make sure to replace `your_application.models` with the correct import
path to your SQLAlchemy models.

### Important Note

- Step 2,3 has to done once per project, once we setup for any future change we should only have to do from step 4. Also for our current project we directly get the database_uri from env variable and set it up in the `env.py`

### Step 4: Generate New Migration Scripts
- Its always a good pratice to upgrade your database to latest version of alembic before you creating latest migration script.
    ```bash
    cd thirdai_platform
    export DATABASE_URI="your_database_uri"
    alembic upgrade head
    ```

- After making changes to your SQLAlchemy models, generate a new
migration script using:

    ```bash
    alembic revision --autogenerate -m "Describe your changes"
    ```

    This will create a new migration script in the `alembic/versions/`
    directory.

- Open the generated script and review it to ensure it accurately
reflects the changes you made to your models. we need to makesure following things carefully in those scripts.
    
    - alembic doesn't take care of data migrations, so we need to take care of that in those scripts by writing the scripts by ourselves.

### Step 5: Apply Migrations

- To apply the migration scripts to your database, run:

    ```bash
    alembic upgrade head
    ```

    This command will execute all migration scripts sequentially to bring
    your database schema up to date.

- To test downgrades, run:

    ```bash
    alembic downgrade -1
    ```

    This will revert the most recent migration. Run `alembic upgrade head`
    again to reapply the migration.

- We have to make sure the following before we merge a new alembic migration script to main

    -  we can upgrade and downgrade that version without any failures
    -  we can migrate the data without it being lost.

### Step 7: Running Alembic Commands

Here are some common Alembic commands you will use:

- Check Current Migration Status:

    ```bash
    alembic current
    ```

    This command shows the current migration version applied to the
    database.

- Stamp the Database with a Specific Version:

    If you need to manually mark the database as being at a specific
    revision:

    ```bash
    alembic stamp head
    ```

    This is useful when initializing Alembic with an existing database
    schema.

- Downgrade to a Specific Version:

    To revert the database schema to a previous version:

    ```bash
    alembic downgrade revision
    ```

    Replace `revision` with the target revision ID.

### Conclusion

By following these steps, you can successfully apply alembic DB migrations. Remember to always review the generated migration scripts and test both
`upgrade` and `downgrade` commands to ensure smooth transitions
between schema versions.
