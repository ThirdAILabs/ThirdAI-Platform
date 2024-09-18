import asyncio
import time
from datetime import datetime
from functools import wraps
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from reporter import Reporter
from routers.model import ModelManager, get_model
from routers.ndb import ndb_router
from routers.udt import udt_router
from utils import delete_deployment_job
from variables import GeneralVariables, ModelType

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

# We have a case where we copy the ndb model for base model training and
# read the model for deployment we face the open database issue.
max_retries = 2  # Total attempts including the initial one
retry_delay = 5  # Delay in seconds before retrying

for attempt in range(1, max_retries + 1):
    try:
        model = get_model()
        break  # Exit the loop if model loading is successful
    except Exception as err:
        if attempt < max_retries:
            time.sleep(retry_delay)
        else:
            reporter.update_deploy_status(general_variables.model_id, "failed")
            raise  # Optionally re-raise the exception if you want the application to stop


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
                model_id=general_variables.model_id
            )
            if active_workflows_count == 0:
                response, job_id = delete_deployment_job(
                    general_variables.get_nomad_endpoint(),
                    general_variables.model_id,
                    general_variables.task_runner_token,
                )
                if response.status_code == 200:
                    model.logger.info(f"Job {job_id} stopped successfully")
                else:
                    model.logger.error(
                        f"Failed to stop job {job_id}. Status code: {response.status_code}, Response: {response.text}"
                    )
                reporter.update_deploy_status(general_variables.model_id, "stopped")
            reset_event.clear()  # Clear event after handling timeout


async def check_for_model_updates():
    global model
    last_loaded_timestamp = None
    model_id = general_variables.model_id

    while True:
        try:
            # Get the current model update timestamp from Redis using model_id
            current_timestamp = model.redis_client.get(f"model_last_updated:{model_id}")
            if current_timestamp:
                current_timestamp = current_timestamp.decode()

                # If the timestamp is newer than the last loaded one, reload the model
                if not last_loaded_timestamp or datetime.fromisoformat(
                    current_timestamp
                ) > datetime.fromisoformat(last_loaded_timestamp):
                    model.logger.info(
                        f"New model update detected at {current_timestamp}. Reloading model..."
                    )
                    # when we rest the instance will be cleared, so forcing to load the latest model instance.
                    ModelManager.reset_instances()
                    model = get_model()
                    last_loaded_timestamp = current_timestamp
                    model.logger.info("Model successfully reloaded.")

        except Exception as e:
            model.logger.error(f"Error checking for model update: {str(e)}")

        # Sleep for a short period before checking again
        await asyncio.sleep(10)  # Adjust the sleep time according to your needs


if general_variables.type == ModelType.NDB:
    app.include_router(ndb_router, prefix=f"/{general_variables.model_id}")
elif general_variables.type == ModelType.UDT:
    app.include_router(udt_router, prefix=f"/{general_variables.model_id}")

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
        reporter.update_deploy_status(general_variables.model_id, "complete")
        asyncio.create_task(async_timer())
        asyncio.create_task(check_for_model_updates())
    except Exception as e:
        reporter.update_deploy_status(general_variables.model_id, "failed")
        model.logger.error(f"Failed to startup the application, {e}")
        raise e  # Re-raise the exception to propagate it to the main block


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="localhost", port=8000)
    except Exception as e:
        model.logger.error(f"Uvicorn failed to start: {str(e)}")
        reporter.update_deploy_status(general_variables.model_id, "failed")
