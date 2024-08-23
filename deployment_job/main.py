import asyncio
import time
from functools import wraps
from queue import Queue
from threading import Lock, Thread
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from reporter import Reporter
from routers.ndb import create_ndb_router, process_tasks
from routers.telemetry import telemetry_router  # Import the telemetry router
from routers.udt import udt_router
from utils import delete_deployment_job
from variables import GeneralVariables, TypeEnum

general_variables = GeneralVariables.load_from_env()
reporter = Reporter(general_variables.model_bazaar_endpoint)

app = FastAPI(
    docs_url=f"/{general_variables.model_id}/docs",
    openapi_url=f"/{general_variables.model_id}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The following logic will start a timer at this Fast API application's start up.
# after n minutes, this service will shut down, unless a function that is decorated
# with @reset_timer is called, in which case the timer restarts.
reset_event = asyncio.Event()


def reset_timer(endpoint_func):
    """
    Decorator to reset the shutdown timer on endpoint access.
    """

    @wraps(endpoint_func)
    def wrapper(*args, **kwargs):
        response = endpoint_func(*args, **kwargs)
        reset_event.set()
        return response

    return wrapper


async def async_timer() -> None:
    """
    Async function to start a shutdown timer and reset it upon endpoint access.
    """
    while True:
        try:
            await asyncio.wait_for(
                reset_event.wait(), timeout=900  # 15 minutes = 900 seconds
            )
            reset_event.clear()  # clear the event if the endpoint was hit within the timeout period
        except asyncio.TimeoutError:
            response, job_id = delete_deployment_job(
                general_variables.model_id, general_variables.task_runner_token
            )
            if response.status_code == 200:
                print(f"Job {job_id} stopped successfully")
            else:
                print(
                    f"Failed to stop job {job_id}. Status code: {response.status_code}, Response: {response.text}"
                )
            reset_event.clear()


task_queue = Queue()
tasks = {}
task_lock = Lock()

# Include the telemetry router for all deployments
app.include_router(telemetry_router, prefix=f"/{general_variables.model_id}/telemetry")

if general_variables.type == TypeEnum.NDB:
    ndb_router = create_ndb_router(task_queue, task_lock, tasks)
    app.include_router(ndb_router, prefix=f"/{general_variables.model_id}")
elif general_variables.type == TypeEnum.UDT:
    app.include_router(udt_router, prefix=f"/{general_variables.model_id}")


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"message": f"Request path '{request.url.path}' doesn't exist"},
    )


@app.get("/")
async def homepage(request: Request) -> dict:
    return {"Deployment"}


@app.on_event("startup")
async def startup_event() -> None:
    """
    Event handler for application startup.
    """
    try:
        time.sleep(10)
        reporter.update_deploy_status(general_variables.model_id, "complete")
        if general_variables.type == TypeEnum.NDB:
            # TODO(Yash/Kartik): Separate Job for write modifications for NDB.
            # As we are going with on-disk index we could only have one instance of model with write mode.
            thread = Thread(
                target=process_tasks, args=(task_queue, task_lock, tasks), daemon=True
            )
            thread.start()
    except Exception as e:
        reporter.update_deploy_status(general_variables.model_id, "failed")
        raise e  # Re-raise the exception to propagate it to the main block


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="localhost", port=8000)
    except Exception as e:
        print(f"Uvicorn failed to start: {str(e)}")
        reporter.update_deploy_status(general_variables.model_id, "failed")
