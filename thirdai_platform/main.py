import sys
import os

from dotenv import load_dotenv

load_dotenv()

import fastapi
import uvicorn
from backend.routers.data import data_router as data
from backend.routers.deploy import deploy_router as deploy
from backend.routers.models import model_router as model
from backend.routers.recovery import recovery_router as recovery
from backend.routers.team import team_router as team
from backend.routers.train import train_router as train
from backend.routers.user import user_router as user
from backend.routers.vault import vault_router as vault
from backend.routers.workflow import workflow_router as workflow
from backend.startup_jobs import restart_generate_job, restart_on_prem_generate_job
from backend.status_sync import sync_job_statuses
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
app.include_router(data, prefix="/api/data", tags=["data"])
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
    
    if os.getenv("ENABLE_ON_PREM_GENERATION_JOB"):
        try:
            print("Starting On Prem Generation Job...")
            await restart_on_prem_generate_job()
            print("Successfully started On Prem Generation Job!")
        except Exception as error:
            print(f"Failed to start the On Prem Generation Job : {error}", file=sys.stderr)
    else:
        print("ENABLE_ON_PREM_GENERATION_JOB is False, not starting the job.")

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





# curl --request POST     --url http://localhost:80/on-prem-llm/completion     --header "Content-Type: application/json"     --data '{"system_prompt": "You are a helpful assistant. Please be concise in your answers.", "prompt": "What is the reason that the stock market is hard to predict? Please be concise. <|assistant|>", "stream": true}'
# curl --request POST     --url http://localhost:80/on-prem-llm/completion     --header "Content-Type: application/json"     --data '{"system_prompt": "You are a helpful assistant. Please be concise in your answers.", "prompt": "Are these the same institution? MD Anderson, Texas and Texas, MD Anderson. <|assistant|>", "stream": true}'
# curl --request POST     --url http://localhost:80/on-prem-llm/completion     --header "Content-Type: application/json"     --data '{"system_prompt": "You are a helpful assistant. Please be concise in your answers.", "prompt": "Are these the same institution?: \n \"Pathology and Histology core at Baylor College of Medicine, Houston, Texas\" and \"Institute of Radiation and Radiation Medicine or Institute of Electromagnetic and Particle Radiation Medicine\" <|assistant|>", "stream": true}'
# curl --request POST     --url http://localhost:80/on-prem-llm/completion     --header "Content-Type: application/json"     --data '{"system_prompt": "You are a helpful assistant. Please be concise in your answers.", "prompt": "If a city has a population of 450,000 men, how many women do you estimate are in that city? <|assistant|>", "stream": true}'

# Are these the same institution?: \n 'Pathology and Histology core at Baylor College of Medicine, Houston, Texas' and 'Institute of Radiation and Radiation Medicine or Institute of Electromagnetic and Particle Radiation Medicine'

# Are these the same institution? MD Anderson, Texas and Texas, MD Anderson