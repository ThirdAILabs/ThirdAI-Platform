import os
import uuid
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from auth.jwt import AuthenticatedUser, verify_access_token
from backend.utils import (
    get_platform,
    get_python_path,
    get_root_absolute_path,
    response,
    submit_nomad_job,
)
from database.session import get_session
from fastapi import APIRouter, Depends, Form, status
from licensing.verify.verify_license import valid_job_allocation, verify_license
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

data_router = APIRouter()


@data_router.post("/test-connection/sql")
def test_sql_connection(
    uri: str, authenticated_user: AuthenticatedUser = Depends(verify_access_token)
):
    from sqlalchemy import create_engine

    try:
        engine = create_engine(uri)
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Connection refused",
            data={"error": str(e)},
        )

    return response(
        status_code=status.HTTP_200_OK,
        message="connection sucessfull",
    )


@data_router.post("/test-connection/azure-blob")
def test_azure_blob_connection(
    account_name: str,
    account_key: str,
    container_name: str,
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    from azure.storage.blob import BlobServiceClient, ResourceExistsError

    try:
        blob_service_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key,
        )
        container_client = blob_service_client.get_container_client(container_name)

        container_client.get_container_properties()

    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Connection refused",
            data={"error": str(e)},
        )

    return response(status_code=status.HTTP_200_OK, message="connection sucessfull")


@data_router.post("/test-connection/s3")
def test_s3_connection(
    aws_access_key: str,
    aws_secret_access_key: str,
    bucket_name: str,
    authenticated_user: AuthenticatedUser = Depends(verify_access_token),
):
    import boto3

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_access_key,
    )

    try:
        s3_client.head_bucket(Bucket=bucket_name)

    except Exception as e:
        return response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Connection refused",
            data={"error": str(e)},
        )

    return response(status_code=status.HTTP_200_OK, message="connection sucessfull")
