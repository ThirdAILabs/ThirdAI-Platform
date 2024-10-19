import json
import os
import shutil
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest
from platform_common.pydantic_models.recovery_snapshot import (
    BackupConfig,
    LocalBackupConfig,
)
from recovery_snapshot_job.run import perform_backup


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup: create a temporary directory for the model_bazaar_dir
    temp_dir = tempfile.mkdtemp()
    os.environ["MODEL_BAZAAR_DIR"] = temp_dir

    # Create a config.json file with local backup settings
    config_path = os.path.join(temp_dir, "backup_config.json")
    config = BackupConfig(
        provider=LocalBackupConfig(
            provider="local"
        ),  # No cloud provider, so local backup
        interval_minutes=None,  # One-time backup
        backup_limit=2,  # Set backup limit to 2
    )
    with open(config_path, "w") as config_file:
        json.dump(config.dict(), config_file)

    # Set additional environment variables required for the backup
    os.environ["CONFIG_PATH"] = config_path
    os.environ["DATABASE_URI"] = f"random db_uri"

    yield  # This allows the test to run after the setup

    # Teardown: remove the temporary directory after the test completes
    shutil.rmtree(temp_dir)


@patch("subprocess.run")  # Mock subprocess.run for pg_dump
def test_local_backup(mock_subprocess_run):
    config_path = os.getenv("CONFIG_PATH")

    # Simulate a successful pg_dump execution
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    # Manually create the mocked db_backup.sql file as pg_dump would create
    model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")
    db_dump_path = os.path.join(model_bazaar_dir, "db_backup.sql")
    with open(db_dump_path, "w") as f:
        f.write("")  # Create an empty backup file

    # Perform the backup immediately
    perform_backup(config_path)

    # Check if the backups directory is created in the model_bazaar_dir
    backups_dir = os.path.join(os.getenv("MODEL_BAZAAR_DIR"), "backups")
    assert os.path.exists(backups_dir), "Backups directory should be created"

    # Check if a backup zip file was created in the backups directory
    backup_files = [
        f
        for f in os.listdir(backups_dir)
        if f.startswith("backup_") and f.endswith(".zip")
    ]
    assert len(backup_files) > 0, "At least one backup file should be created"

    # Ensure that pg_dump (subprocess.run) was called
    mock_subprocess_run.assert_called_once()


@patch("subprocess.run")  # Mock subprocess.run for pg_dump
def test_backup_limit(mock_subprocess_run):
    """Test to check if the backup limit is respected."""
    config_path = os.getenv("CONFIG_PATH")

    # Simulate a successful pg_dump execution
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    # Manually create the mocked db_backup.sql file as pg_dump would create
    for _ in range(3):
        model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")
        db_dump_path = os.path.join(model_bazaar_dir, "db_backup.sql")
        with open(db_dump_path, "w") as f:
            f.write("")  # Create an empty backup file

        # Perform the backup three times to exceed the backup limit of 2
        time.sleep(3)
        perform_backup(config_path)

    # Check if the backup directory has no more than 2 backups
    backups_dir = os.path.join(os.getenv("MODEL_BAZAAR_DIR"), "backups")
    backup_files = [
        f
        for f in os.listdir(backups_dir)
        if f.startswith("backup_") and f.endswith(".zip")
    ]

    assert (
        len(backup_files) == 2
    ), "Backup limit should enforce only 2 backups to be retained"
