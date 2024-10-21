import logging
import os

import thirdai
from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llm_cache_job.cache import Cache, NDBSemanticCache
from llm_cache_job.permissions import Permissions

app = FastAPI()
router = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

license_key = os.getenv("LICENSE_KEY")
model_bazaar_dir = os.getenv("MODEL_BAZAAR_DIR")
if license_key == "file_license":
    thirdai.licensing.set_path(
        os.path.join(model_bazaar_dir, "license/license.serialized")
    )
else:
    thirdai.licensing.activate(license_key)

permissions = Permissions()

cache: Cache = NDBSemanticCache()


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


@router.get("/suggestions", dependencies=[Depends(permissions.verify_read_permission)])
def suggestions(model_id: str, query: str):
    result = cache.suggestions(model_id=model_id, query=query)

    logging.info(f"found {len(result)} suggestions for query={query}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "suggestions": jsonable_encoder(result)},
    )


@router.get("/query", dependencies=[Depends(permissions.verify_read_permission)])
def cache_query(model_id: str, query: str):
    result = cache.query(model_id=model_id, query=query)

    if result:
        logging.info(f"found cached result for query={query}")
    else:
        logging.info(f"found no cached result for query={query}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "cached_response": jsonable_encoder(result)},
    )


@router.post("/insert")
def cache_insert(
    query: str,
    llm_res: str,
    model_id: str = Depends(permissions.verify_temporary_cache_access_token),
):
    cache.insert(model_id=model_id, query=query, llm_res=llm_res)

    logging.info(f"cached query={query}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "message": "inserted response into cache"},
    )


@router.post("/invalidate", dependencies=[Depends(permissions.verify_write_permission)])
def cache_invalidate(model_id: str):
    cache.invalidate(model_id=model_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "message": "invalidated cache for model id"},
    )


@router.get("/token", dependencies=[Depends(permissions.verify_read_permission)])
def temporary_cache_token(model_id: str):
    logging.info(f"creating cache token for model {model_id}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "success",
            "access_token": permissions.create_temporary_cache_access_token(
                model_id=model_id
            ),
        },
    )


app.include_router(router, prefix="/cache")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
