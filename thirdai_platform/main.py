import logging
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from platform_common.logging import setup_logger
from platform_common.utils import model_bazaar_path

load_dotenv()
import json

import fastapi
import uvicorn
from auth.jwt import validate_access_token
from backend.routers.data import data_router
from backend.routers.deploy import deploy_router as deploy
from backend.routers.integrations import integrations_router as integrations
from backend.routers.models import model_router as model
from backend.routers.recovery import recovery_router as recovery
from backend.routers.team import team_router as team
from backend.routers.telemetry import telemetry_router as telemetry
from backend.routers.train import train_router as train
from backend.routers.user import user_router as user
from backend.routers.vault import vault_router as vault
from backend.routers.workflow import workflow_router as workflow
from backend.startup_jobs import (
    restart_generate_job,
    restart_llm_cache_job,
    restart_telemetry_jobs,
    restart_thirdai_platform_frontend,
)
from backend.status_sync import sync_job_statuses
from backend.utils import get_platform
from database.session import get_session
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import event

pass
from database import schema
from fastapi import BackgroundTasks, WebSocket, WebSocketDisconnect
from middleware.timeout_middleware import TimeoutMiddleware
from websocket.utils import manager, notify_model_change

app = fastapi.FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TimeoutMiddleware,
    timeout=10.0,
)

log_dir: Path = Path(model_bazaar_path()) / "logs"

setup_logger(log_dir=log_dir, log_prefix="platform_backend")

logger = logging.getLogger("platform-backend")
audit_logger = setup_logger(log_dir=log_dir, log_prefix="audit", configure_root=False)

app.include_router(user, prefix="/api/user", tags=["user"])
app.include_router(train, prefix="/api/train", tags=["train"])
app.include_router(model, prefix="/api/model", tags=["model"])
app.include_router(deploy, prefix="/api/deploy", tags=["deploy"])
app.include_router(vault, prefix="/api/vault", tags=["vault"])
app.include_router(team, prefix="/api/team", tags=["team"])
app.include_router(workflow, prefix="/api/workflow", tags=["workflow"])
app.include_router(recovery, prefix="/api/recovery", tags=["recovery"])
app.include_router(data_router, prefix="/api/data", tags=["data"])
app.include_router(telemetry, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(integrations, prefix="/api/integrations", tags=["integrations"])


@app.get("/api/health")
async def health_check():
    # TODO(pratik): we should add a check whether all the dependency are running fine
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: fastapi.Request, exc: Exception):
    # Log the traceback
    error_trace = traceback.format_exc()
    logger.error(f"Exception occurred: {error_trace}")

    # Return the exact exception message in the response
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.middleware("http")
async def log_requests(request: fastapi.Request, call_next):
    if request.url.path.strip("/") != "metrics":
        # Don't log the prometheus client metric request
        x_forwarded_for = request.headers.get("x-forwarded-for")
        client_ip = (
            x_forwarded_for.split(",")[0].strip()
            if x_forwarded_for
            else (request.client.host if request.client else "Unknown")
        )  # When behind a load balancer or proxy, client IP would be in `x-forwarded-for` header
        audit_log = {
            "ip": client_ip,
            "protocol": request.headers.get("x-forwarded-proto", request.url.scheme),
            "method": request.method,
            "url": str(request.url),
            "query_params": dict(request.query_params),
            "path_params": dict(request.path_params),
        }
        body = None
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                body = await request.json()
            except Exception:
                body = "Could not parse body as JSON"
        audit_log["body"] = body
        try:
            session = next(get_session())
            user = validate_access_token(
                access_token=request.headers.get("Authorization").split()[1],
                session=session,
            )
            audit_log["username"] = user.user.username
        except Exception as e:
            audit_log["username"] = "unknown"
        finally:
            session.close()

        audit_logger.info(json.dumps(audit_log))

    response = await call_next(request)

    logger.info(
        f"Request: {request.method}; URl: {request.url} - {response.status_code}"
    )

    return response


@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Starting Generation Job...")
        await restart_generate_job()
        logger.info("Successfully started Generation Job!")
    except Exception as error:
        logger.error(f"Failed to start the Generation Job: {error}")
        logger.debug(traceback.format_exc())

    try:
        logger.info("Starting telemetry Job...")
        await restart_telemetry_jobs()
        logger.info("Successfully started telemetry Job!")
    except Exception as error:
        logger.error(f"Failed to start the telemetry Job: {error}")
        logger.debug(traceback.format_exc())

    platform = get_platform()
    if platform == "docker":
        try:
            logger.info("Launching frontend...")
            await restart_thirdai_platform_frontend()
            logger.info("Successfully launched the frontend!")
        except Exception as error:
            logger.error(f"Failed to start the frontend: {error}")
            logger.debug(traceback.format_exc())

    try:
        logger.info("Starting LLM Cache Job...")
        await restart_llm_cache_job()
        logger.info("Successfully started LLM Cache Job!")
    except Exception as error:
        logger.error(f"Failed to start the LLM Cache Job: {error}")
        logger.debug(traceback.format_exc())

    await sync_job_statuses()


@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket, background_tasks: BackgroundTasks):
    await manager.connect(websocket)
    try:
        while True:
            data = (
                await websocket.receive_text()
            )  # Handle incoming messages if necessary
            logger.info(f"Received data: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.error("Client disconnected")


@event.listens_for(schema.Model, "after_insert")
def after_insert(mapper, connection, target):
    notify_model_change(target, "insert")


@event.listens_for(schema.Model, "after_update")
def after_update(mapper, connection, target):
    notify_model_change(target, "update")


@event.listens_for(schema.Model, "after_delete")
def after_delete(mapper, connection, target):
    notify_model_change(target, "delete")


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000, log_level="info")
