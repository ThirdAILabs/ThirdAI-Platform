import asyncio
import time
from functools import wraps
from typing import Any

import uvicorn
from config import DeploymentConfig, ModelType
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from permissions import Permissions
from prometheus_client import make_asgi_app
import os
from reporter import Reporter
from routers.ndb import create_ndb_router
from routers.udt import create_udt_router
from utils import delete_deployment_job


def load_config():
    with open(os.getenv("CONFIG_PATH")) as file:
        return DeploymentConfig.model_validate_json(file.read())


config: DeploymentConfig = load_config()
reporter = Reporter(config.model_bazaar_endpoint)

app = FastAPI(
    docs_url=f"/{config.model_id}/docs", openapi_url=f"/{config.model_id}/openapi.json"
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
            await asyncio.wait_for(reset_event.wait(), timeout=900)
            reset_event.clear()  # Clear the event if the endpoint was hit within the timeout period
        except asyncio.TimeoutError:
            # Timer expired, initiate shutdown
            active_workflows_count = reporter.active_workflow_count(
                model_id=config.model_id
            )
            if active_workflows_count == 0:
                response, job_id = delete_deployment_job(
                    config.get_nomad_endpoint(),
                    config.model_id,
                    os.getenv("TASK_RUNNER_TOKEN"),
                )
                if response.status_code == 200:
                    print(f"Job {job_id} stopped successfully")
                else:
                    print(
                        f"Failed to stop job {job_id}. Status code: {response.status_code}, Response: {response.text}"
                    )
                reporter.update_deploy_status(config.model_id, "stopped")
            reset_event.clear()  # Clear event after handling timeout


if config.model_options.model_type == ModelType.NDB:
    backend_router_factory = create_ndb_router
elif config.model_options.model_type == ModelType.UDT:
    backend_router_factory = create_udt_router
else:
    raise ValueError(f"Unsupported ModelType '{config.model_options.model_type}'.")

permissions = Permissions(
    model_bazaar_endpoint=config.model_bazaar_endpoint, model_id=config.model_id
)

# We have a case where we copy the ndb model for base model training and
# read the model for deployment we face the open database issue.
max_retries = 2  # Total attempts including the initial one
retry_delay = 5  # Delay in seconds before retrying

for attempt in range(1, max_retries + 1):
    try:
        backend_router = backend_router_factory(config, permissions)
        break  # Exit the loop if model loading is successful
    except Exception as err:
        if attempt < max_retries:
            time.sleep(retry_delay)
        else:
            reporter.update_deploy_status(config.model_id, "failed")
            raise  # Optionally re-raise the exception if you want the application to stop


app.include_router(backend_router, prefix=f"/{config.model_id}")

app.mount("/metrics", make_asgi_app())


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
        await asyncio.sleep(10)
        reporter.update_deploy_status(config.model_id, "complete")
        asyncio.create_task(async_timer())
    except Exception as e:
        reporter.update_deploy_status(config.model_id, "failed")
        print(f"Failed to startup the application, {e}")
        raise e  # Re-raise the exception to propagate it to the main block


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="localhost", port=8000)
    except Exception as e:
        print(f"Uvicorn failed to start: {str(e)}")
        reporter.update_deploy_status(config.model_id, "failed")
