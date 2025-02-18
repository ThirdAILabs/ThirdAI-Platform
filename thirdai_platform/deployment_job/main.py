try:
    import asyncio
    import json
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
    from platform_common.logging import JobLogger, LogCode, setup_logger
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

logger = JobLogger(
    log_dir=log_dir,
    log_prefix="deployment",
    service_type="deployment",
    model_id=config.model_id,
    model_type=config.model_options.model_type,
    user_id=config.user_id,
)

audit_logger = setup_logger(
    log_dir=log_dir / "deployment_audit_logs",
    log_prefix=os.getenv("NOMAD_ALLOC_ID"),
    configure_root=False,
)

reporter = Reporter(config.model_bazaar_endpoint, logger)

verify_license.activate_thirdai_license(config.license_key)

Permissions.init(
    model_bazaar_endpoint=config.model_bazaar_endpoint, model_id=config.model_id
)

app = FastAPI(docs_url=f"/docs", openapi_url=f"/openapi.json")

PUBLIC_MODEL_BAZAAR_ENDPOINT = os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT")
PRIVATE_MODEL_BAZAAR_ENDPOINT = os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT")

ALLOWED_ORIGINS = [PUBLIC_MODEL_BAZAAR_ENDPOINT, PRIVATE_MODEL_BAZAAR_ENDPOINT]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
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
            permissions = Permissions._get_permissions(
                token=request.headers.get("Authorization").split()[1],
            )
            audit_log["username"] = permissions[3]
        except Exception as e:
            audit_log["username"] = "unknown"
        audit_logger.info(json.dumps(audit_log))

    response = await call_next(request)

    logger.debug(
        f"Request: {request.method}; URl: {request.url} - {response.status_code}",
    )

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the traceback
    error_trace = traceback.format_exc()
    logger.error(f"Exception occurred: {error_trace}", code=LogCode.MODEL_INIT)

    # Return the exact exception message in the response
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


if config.model_options.model_type == ModelType.NDB:
    backend_router_factory = NDBRouter
    logger.info("Initializing NDB router", code=LogCode.MODEL_INIT)
elif config.model_options.model_type == ModelType.UDT:
    if config.model_options.udt_sub_type == UDTSubType.token:
        backend_router_factory = UDTRouterTokenClassification

        logger.info(
            "Initializing UDT Token Classification router", code=LogCode.MODEL_INIT
        )
    elif (
        config.model_options.udt_sub_type == UDTSubType.text
        or config.model_options.udt_sub_type == UDTSubType.document
    ):
        backend_router_factory = UDTRouterTextClassification
        logger.info(
            "Initializing UDT Text Classification router", code=LogCode.MODEL_INIT
        )
    else:
        error_message = f"Unsupported UDT Type '{config.model_options.udt_sub_type}'."
        logger.error(error_message, code=LogCode.MODEL_INIT)
        raise ValueError(error_message)
elif config.model_options.model_type == ModelType.ENTERPRISE_SEARCH:
    backend_router_factory = EnterpriseSearchRouter
elif config.model_options.model_type == ModelType.KNOWLEDGE_EXTRACTION:
    backend_router_factory = KnowledgeExtractionRouter
else:
    error_message = f"Unsupported ModelType '{config.model_options.model_type}'."
    logger.error(error_message, code=LogCode.MODEL_INIT)
    raise ValueError(error_message)


# We have a case where we copy the ndb model for base model training and
# read the model for deployment we face the open database issue.
max_retries = 2  # Total attempts including the initial one
retry_delay = 5  # Delay in seconds before retrying

for attempt in range(1, max_retries + 1):
    try:
        backend_router = backend_router_factory(config, reporter, logger)
        logger.info(
            f"Successfully initialized backend router: {backend_router_factory.__name__}",
            code=LogCode.MODEL_INIT,
        )
        break  # Exit the loop if model loading is successful
    except Exception as err:
        if attempt < max_retries:
            time.sleep(retry_delay)
            logger.info(
                "Retrying backend router initialization", code=LogCode.MODEL_INIT
            )
        else:
            error_message = (
                f"Deployment failed after {attempt} attempts with error: {err}"
            )
            reporter.update_deploy_status(
                config.model_id, "failed", message=error_message
            )
            logger.critical(error_message, code=LogCode.MODEL_INIT)
            raise  # Optionally re-raise the exception if you want the application to stop


app.include_router(backend_router.router)

app.mount("/metrics", make_asgi_app())


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Any) -> JSONResponse:
    logger.warning(f"404 Not Found: {request.url.path}", code=LogCode.MODEL_INIT)
    return JSONResponse(
        status_code=404,
        content={"message": f"Request path '{request.url.path}' doesn't exist"},
    )


@app.get("/")
async def homepage(request: Request) -> dict:
    return {"Deployment"}


@app.get("/health")
async def health_check() -> dict:
    return {"status": "success"}


@app.on_event("startup")
async def startup_event() -> None:
    """
    Event handler for application startup.
    """
    asyncio.create_task(delayed_status_update())


async def delayed_status_update():
    try:
        await asyncio.sleep(10)
        reporter.update_deploy_status(config.model_id, "complete")
    except Exception as e:
        error_message = f"Startup event failed with error: {e}"
        reporter.update_deploy_status(config.model_id, "failed", message=error_message)
        logger.critical(error_message, code=LogCode.MODEL_INIT)
        sys.exit(1)


@app.on_event("shutdown")
async def shutdown_event():

    logger.debug(
        f"Shutting down FastAPI Application",
    )

    if isinstance(backend_router, NDBRouter):
        deployment_status = reporter.get_deploy_status(config.model_id)
        if deployment_status == "stopped":
            backend_router.shutdown()


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="localhost", port=8000, log_level="info")
    except Exception as e:
        error_message = f"Uvicorn failed to start: {e}"
        logger.critical(error_message, code=LogCode.MODEL_INIT)
        reporter.update_deploy_status(config.model_id, "failed", message=error_message)
