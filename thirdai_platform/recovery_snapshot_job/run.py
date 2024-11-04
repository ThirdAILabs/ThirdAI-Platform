import datetime
import logging
import os
import subprocess
import zipfile
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from platform_common.file_handler import (
    AzureStorageHandler,
    CloudStorageHandler,
    GCPStorageHandler,
    S3StorageHandler,
)
from platform_common.logging import setup_logger
from platform_common.pydantic_models.recovery_snapshot import (
    AzureConfig,
    BackupConfig,
    GCPConfig,
    S3Config,
)

# Global scheduler instance
scheduler = BlockingScheduler()

model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")

log_dir: Path = Path(model_bazaar_dir) / "logs"

setup_logger(log_dir=log_dir, log_prefix="recovery_snapshot")

logger = logging.getLogger("recovery_snapshot")


def get_cloud_storage_handler(config: BackupConfig):
    """Get the appropriate cloud storage handler based on the provider."""
    provider_config = config.provider

    if isinstance(provider_config, S3Config):
        logger.info("Using S3 storage handler for backup.")
        return S3StorageHandler(
            aws_access_key=provider_config.aws_access_key,
            aws_secret_access_key=provider_config.aws_secret_access_key,
        )
    elif isinstance(provider_config, AzureConfig):
        logger.info("Using Azure storage handler for backup.")
        return AzureStorageHandler(
            account_name=provider_config.azure_account_name,
            account_key=provider_config.azure_account_key,
        )
    elif isinstance(provider_config, GCPConfig):
        logger.info("Using GCP storage handler for backup.")
        return GCPStorageHandler(provider_config.gcp_credentials_file_path)
    else:
        logger.info("No cloud storage handler configured; using local storage.")
        return None  # Local backup, no cloud handler


def extract_timestamp(backup_name: str) -> datetime:
    """
    Extract the timestamp from the backup filename and convert it to a datetime object.
    Assumes the backup format is 'backup_YYYYMMDD_HHMMSS.zip'.
    """
    try:
        # Extract the timestamp part (e.g., '20241010_203418') from the backup filename
        timestamp_str = (
            backup_name.split("_")[1] + "_" + backup_name.split("_")[2].split(".")[0]
        )
        # Convert the timestamp string to a datetime object
        return datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
    except (IndexError, ValueError):
        # If the timestamp format is invalid, return a minimum date to avoid deletion
        logger.warning(f"Invalid timestamp format in backup name: {backup_name}")
        return datetime.datetime.min


def delete_local_backup(zip_file_path: str, dump_file_path: str):
    """Delete local backup files after successful backup."""
    try:
        os.remove(f"{zip_file_path}")
        logger.info(f"Deleted local zip file: {zip_file_path}")
        os.remove(dump_file_path)
        logger.info(f"Deleted local DB dump file: {dump_file_path}")
    except Exception as e:
        logger.error(f"Error while deleting local files: {str(e)}")


def create_backup_files(
    db_uri: str, model_bazaar_dir: str, backup_dir: str, timestamp: str
):
    # Create database dump file
    dump_file_path = os.path.join(model_bazaar_dir, f"db_backup.sql")
    logger.info(f"Creating database dump at {dump_file_path}")
    # TODO(YASH): Only backup completed models.
    subprocess.run(["pg_dump", db_uri, "-f", dump_file_path], check=True)

    # Path for the zip file in the backups folder
    zip_file_path = os.path.join(backup_dir, f"backup_{timestamp}.zip")

    # Create a zip file excluding the 'backups' folder
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(model_bazaar_dir):
            # Skip the 'backups' directory
            if "backups" in root:
                continue

            # Add files to the zip archive
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, model_bazaar_dir)
                zipf.write(file_path, relative_path)

    logger.info(f"Backup zip file created at {zip_file_path}")
    return zip_file_path, dump_file_path


def manage_backup_limit_local(backup_dir: str, backup_limit: int):
    """Ensure that the number of local backups does not exceed the limit."""
    all_backups = [f for f in os.listdir(backup_dir) if f.startswith("backup_")]
    sorted_backups = sorted(all_backups, key=extract_timestamp, reverse=True)
    if len(sorted_backups) > backup_limit:
        for backup in sorted_backups[backup_limit:]:
            backup_path = os.path.join(backup_dir, backup)
            os.remove(backup_path)
            logger.info(f"Deleted old local backup: {backup_path}")


def manage_backup_limit(
    cloud_handler: CloudStorageHandler, bucket_name: str, backup_limit: int
):
    """Ensure that the number of backups in the cloud does not exceed the limit."""
    all_backups = cloud_handler.list_files(bucket_name, "backup_")
    sorted_backups = sorted(all_backups, key=extract_timestamp, reverse=True)
    if len(sorted_backups) > backup_limit:
        for backup in sorted_backups[backup_limit:]:
            cloud_handler.delete_path(bucket_name, backup)
            logger.info(f"Deleted old cloud backup: {backup}")


def perform_backup(config_file):
    """Perform the backup operation based on the provided config."""
    config = BackupConfig.parse_file(config_file)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")

    try:
        backup_dir = os.path.join(model_bazaar_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        db_uri = os.getenv("DATABASE_URI")
        backup_limit = config.backup_limit

        zip_file_path, dump_file_path = create_backup_files(
            db_uri, model_bazaar_dir, backup_dir, timestamp
        )

        # If a cloud provider is configured, upload the backup to the cloud
        cloud_handler = get_cloud_storage_handler(config)
        if cloud_handler:
            cloud_handler.create_bucket_if_not_exists(config.provider.bucket_name)
            cloud_handler.upload_file(
                f"{zip_file_path}",
                config.provider.bucket_name,
                f"backup_{timestamp}.zip",
            )
            manage_backup_limit(
                cloud_handler, config.provider.bucket_name, backup_limit
            )
            delete_local_backup(zip_file_path, dump_file_path)
        else:
            # No cloud provider, manage local backups
            manage_backup_limit_local(backup_dir, backup_limit)
            os.remove(dump_file_path)
            logger.info(f"Deleted local DB dump file: {dump_file_path}")

    except Exception as e:
        logger.error(f"Backup failed: {e}")


def schedule_backup(config_file):
    """Schedule backup based on interval in config or run once."""
    config = BackupConfig.parse_file(config_file)
    interval_minutes = config.interval_minutes

    if interval_minutes:
        # Schedule recurring backups
        scheduler.add_job(
            perform_backup,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[config_file],
            id="backup_job",
            replace_existing=True,
        )
        logger.info(f"Scheduled periodic backup every {interval_minutes} minutes.")

        # Start the scheduler for periodic backups
        try:
            scheduler.start()
        except Exception as e:
            logger.error(f"Scheduler encountered an error: {e}")
            scheduler.shutdown()
    else:
        # Run one-time backup directly, no scheduler needed
        logger.info("Starting one-time backup.")
        perform_backup(config_file)


if __name__ == "__main__":
    config_file = os.getenv("CONFIG_PATH")
    if not config_file or not os.path.exists(config_file):
        logger.error("Config file not found.")
        raise ValueError("Config file not found.")

    try:
        schedule_backup(config_file)
    except Exception as err:
        # TODO(YASH): Figure out a way to propagate this error messages to user.
        logger.error(f"Error during backup: {err}")
