import asyncio
from functools import wraps
from threading import Thread
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from reporter import Reporter
from routers.ndb.read import ndb_read_router
from routers.ndb.write import ndb_write_router, process_tasks
from routers.telemetry.write import telemetry_write_router
from routers.udt.read import udt_read_router
from utils import delete_deployment_job
from variables import GeneralVariables, TypeEnum

# Load environment variables
general_variables = GeneralVariables.load_from_env()
reporter = Reporter(general_variables.model_bazaar_endpoint)

docs_prefix = "write" if general_variables.write else "read"

# Initialize FastAPI application
app = FastAPI(
    docs_url=f"/{general_variables.model_id}/{docs_prefix}/docs",
    openapi_url=f"/{general_variables.model_id}/{docs_prefix}/openapi.json",
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
            # Wait for the reset event for 15 minutes (900 seconds)
            await asyncio.wait_for(reset_event.wait(), timeout=900)
            reset_event.clear()  # Clear the event if the endpoint was hit within the timeout period
        except asyncio.TimeoutError:
            # Timer expired, initiate shutdown
            active_workflows_count = reporter.active_workflow_count(
                model_id=general_variables.model_id
            )
            if active_workflows_count == 0:
                response, job_id = delete_deployment_job(
                    general_variables.get_nomad_endpoint(),
                    general_variables.model_id,
                    general_variables.task_runner_token,
                )
                if response.status_code == 200:
                    print(f"Job {job_id} stopped successfully")
                else:
                    print(
                        f"Failed to stop job {job_id}. Status code: {response.status_code}, Response: {response.text}"
                    )
                reporter.update_deploy_status(general_variables.model_id, "stopped")
            reset_event.clear()  # Clear event after handling timeout


# Include routers based on conditions
if general_variables.write:
    app.include_router(
        telemetry_write_router, prefix=f"/{general_variables.model_id}/write/telemetry"
    )

if general_variables.type == TypeEnum.NDB:
    router = ndb_write_router if general_variables.write else ndb_read_router
    app.include_router(router, prefix=f"/{general_variables.model_id}/{docs_prefix}")
elif general_variables.type == TypeEnum.UDT:
    app.include_router(udt_read_router, prefix=f"/{general_variables.model_id}/read")


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
        await asyncio.sleep(10)  # Asynchronous sleep to avoid blocking the event loop
        reporter.update_deploy_status(general_variables.model_id, "complete")
        if general_variables.type == TypeEnum.NDB and general_variables.write:
            # This thread will only run in write job.
            thread = Thread(target=process_tasks, daemon=True)
            thread.start()
        # Start the shutdown timer coroutine
        asyncio.create_task(async_timer())
    except Exception as e:
        reporter.update_deploy_status(general_variables.model_id, "failed")
        raise e  # Re-raise the exception to propagate it to the main block


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="localhost", port=8000)
    except Exception as e:
        print(f"Uvicorn failed to start: {str(e)}")
        reporter.update_deploy_status(general_variables.model_id, "failed")
