import sys

from dotenv import load_dotenv

load_dotenv()

import fastapi
import uvicorn
from backend.routers.deploy import deploy_router as deploy
from backend.routers.models import model_router as model
from backend.routers.recovery import recovery_router as recovery
from backend.routers.team import team_router as team
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
from database.utils import initialize_default_workflow_types
from fastapi.middleware.cors import CORSMiddleware

app = fastapi.FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user, prefix="/api/user", tags=["user"])
app.include_router(train, prefix="/api/train", tags=["train"])
app.include_router(model, prefix="/api/model", tags=["model"])
app.include_router(deploy, prefix="/api/deploy", tags=["deploy"])
app.include_router(workflow, prefix="/api/workflow", tags=["workflow"])
app.include_router(vault, prefix="/api/vault", tags=["vault"])
app.include_router(team, prefix="/api/team", tags=["team"])
app.include_router(recovery, prefix="/api/recovery", tags=["recovery"])


@app.on_event("startup")
async def startup_event():
    try:
        print("Starting Generation Job...")
        await restart_generate_job()
        print("Successfully started Generation Job!")
    except Exception as error:
        print(f"Failed to start the Generation Job : {error}", file=sys.stderr)

    platform = get_platform()
    if platform == "docker":
        try:
            print("Starting telemetry Job...")
            await restart_telemetry_jobs()
            print("Successfully started telemetry Job!")
        except Exception as error:
            print(f"Failed to start the telemetry Job : {error}", file=sys.stderr)

        try:
            print("Launching frontend...")
            await restart_thirdai_platform_frontend()
            print("Successfully launched the frontend!")
        except Exception as error:
            print(f"Failed to start the frontend : {error}", file=sys.stderr)

    try:
        print("Starting LLM Cache Job...")
        await restart_llm_cache_job()
        print("Successfully started LLM Cache Job!")
    except Exception as error:
        print(f"Failed to start the LLM Cache Job : {error}", file=sys.stderr)

    try:
        print("Adding default workflow types")
        with next(get_session()) as session:
            initialize_default_workflow_types(session)
        print("Added workflow types")
    except Exception as error:
        print(f"Initializing default workflow types failed: {error}", file=sys.stderr)
        raise

    await sync_job_statuses()


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
