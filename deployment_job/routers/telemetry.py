import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from routers.model import get_model


class TelemetryEvent(BaseModel):
    UserAction: str
    UIComponent: str
    UI: str
    data: Any = None


class TelemetryEventPackage(BaseModel):
    UserName: str
    timestamp: str
    UserMachine: str
    event: TelemetryEvent


telemetry_router = APIRouter()


@telemetry_router.post("/record-event")
async def record_event(telemetry_package: TelemetryEventPackage):
    model = get_model()
    log_entry = telemetry_package.dict()

    # Append the log entry to the JSON file
    try:
        with open(model.telemetry_path, "r+") as f:
            logs = json.load(f)
            logs.append(log_entry)
            f.seek(0)
            json.dump(logs, f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write log: {e}")

    return {"message": "Event recorded successfully"}
