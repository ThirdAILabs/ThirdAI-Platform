from typing import Optional

from pydantic import BaseModel


class AWSCredentials(BaseModel):
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region_name: Optional[str] = None


class AzureCredentials(BaseModel):
    account_name: Optional[str] = None
    account_key: Optional[str] = None


class GCPCredentials(BaseModel):
    credentials_file: Optional[str] = None


class GenericKeyValue(BaseModel):
    value: str
