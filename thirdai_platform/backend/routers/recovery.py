import os
import subprocess

from auth.jwt import verify_access_token
from backend.utils import response
from fastapi import APIRouter, Depends, HTTPException, status

from thirdai_platform.platform_common.file_handler import S3StorageHandler

recovery_router = APIRouter()


def dump_postgres_db_to_file(db_uri, dump_file_path):
    try:
        subprocess.run(["pg_dump", db_uri, "-f", dump_file_path], check=True)
        print(f"Database successfully dumped to {dump_file_path}")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dump the database: {str(e)}",
        )


@recovery_router.post("/backup-to-s3", dependencies=[Depends(verify_access_token)])
def backup_to_s3():
    local_dir = os.getenv("SHARE_DIR")
    if not local_dir:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SHARE_DIR environment variable is not set.",
        )

    bucket_name = os.getenv("RECOVERY_BUCKET_NAME", "thirdai-enterprise-recovery")
    s3_client_handler = S3StorageHandler()

    s3_client_handler.create_bucket_if_not_exists(bucket_name)

    db_uri = os.getenv("DATABASE_URI")
    dump_file_path = os.path.join(local_dir, "db_backup.sql")
    dump_postgres_db_to_file(db_uri, dump_file_path)

    s3_client_handler.upload_file(dump_file_path, bucket_name, "db_backup.sql")

    s3_client_handler.upload_folder(bucket_name, local_dir)

    return response(
        status_code=status.HTTP_200_OK,
        message=f"Backup to S3 completed successfully, including the database.",
    )
