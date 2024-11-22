try:
    import asyncio
    import logging
    import os
    import sys
    import time
    import traceback
    from pathlib import Path
    from typing import Any

    import uvicorn
    from deployment_job.permissions import Permissions
    from deployment_job.reporter import Reporter
    from deployment_job.routers.enterprise_search import EnterpriseSearchRouter
    from deployment_job.routers.knowledge_extraction import KnowledgeExtractionRouter
    from deployment_job.routers.ndb import NDBRouter
    from deployment_job.routers.udt import (
        UDTRouterTextClassification,
        UDTRouterTokenClassification,
    )
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from licensing.verify import verify_license
    from platform_common.logging import setup_logger
    from platform_common.pydantic_models.deployment import DeploymentConfig, UDTSubType
    from platform_common.pydantic_models.training import ModelType
    from prometheus_client import make_asgi_app
except ImportError as e:
    logging.error(f"Failed to import module: {e}")
    sys.exit(f"ImportError: {e}")


def load_config():
    with open(os.getenv("CONFIG_PATH")) as file:
        return DeploymentConfig.model_validate_json(file.read())


config: DeploymentConfig = load_config()

log_dir: Path = Path(config.model_bazaar_dir) / "logs" / config.model_id

setup_logger(log_dir=log_dir, log_prefix="deployment")

logger = logging.getLogger("deployment")

reporter = Reporter(config.model_bazaar_endpoint, logger)

verify_license.activate_thirdai_license(config.license_key)

Permissions.init(
    model_bazaar_endpoint=config.model_bazaar_endpoint, model_id=config.model_id
)

app = FastAPI(docs_url=f"/docs", openapi_url=f"/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)

    logger.info(
        f"Request: {request.method}; URl: {request.url} - {response.status_code}"
    )

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the traceback
    error_trace = traceback.format_exc()
    logger.error(f"Exception occurred: {error_trace}")

    # Return the exact exception message in the response
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


if config.model_options.model_type == ModelType.NDB:
    backend_router_factory = NDBRouter
elif config.model_options.model_type == ModelType.UDT:
    if config.model_options.udt_sub_type == UDTSubType.token:
        backend_router_factory = UDTRouterTokenClassification
    elif config.model_options.udt_sub_type == UDTSubType.text:
        backend_router_factory = UDTRouterTextClassification
    else:
        error_message = f"Unsupported UDT Type '{config.model_options.udt_sub_type}'."
        logger.error(error_message)
        raise ValueError(error_message)
elif config.model_options.model_type == ModelType.ENTERPRISE_SEARCH:
    backend_router_factory = EnterpriseSearchRouter
elif config.model_options.model_type == ModelType.KNOWLEDGE_EXTRACTION:
    backend_router_factory = KnowledgeExtractionRouter
else:
    error_message = f"Unsupported ModelType '{config.model_options.model_type}'."
    logger.error(error_message)
    raise ValueError(error_message)


# We have a case where we copy the ndb model for base model training and
# read the model for deployment we face the open database issue.
max_retries = 2  # Total attempts including the initial one
retry_delay = 5  # Delay in seconds before retrying

for attempt in range(1, max_retries + 1):
    try:
        backend_router = backend_router_factory(config, reporter, logger)
        logger.info(
            f"Successfully initialized backend router: {backend_router_factory.__name__}"
        )
        break  # Exit the loop if model loading is successful
    except Exception as err:
        logger.error(f"Attempt {attempt} failed to initialize backend router: {err}")
        if attempt < max_retries:
            time.sleep(retry_delay)
            logger.info("Retrying backend router initialization")
        else:
            error_message = (
                f"Deployment failed after {attempt} attempts with error: {err}"
            )
            reporter.update_deploy_status(
                config.model_id, "failed", message=error_message
            )
            logger.critical(error_message)
            raise  # Optionally re-raise the exception if you want the application to stop


app.include_router(backend_router.router)

app.mount("/metrics", make_asgi_app())


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Any) -> JSONResponse:
    logger.warning(f"404 Not Found: {request.url.path}")
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
    except Exception as e:
        error_message = f"Startup event failed with error: {e}"
        reporter.update_deploy_status(config.model_id, "failed", message=error_message)
        logger.critical(error_message)
        raise e  # Re-raise the exception to propagate it to the main block


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="localhost", port=8000, log_level="info")
    except Exception as e:
        error_message = f"Uvicorn failed to start: {e}"
        logger.critical(error_message)
        reporter.update_deploy_status(config.model_id, "failed", message=error_message)
