from dotenv import load_dotenv

load_dotenv()

from cache import Cache, NDBSemanticCache
import logging
from fastapi import Depends, FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from permissions import Permissions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


permissions = Permissions()

cache: Cache = NDBSemanticCache()


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


@app.get(
    "/cache/suggestions", dependencies=[Depends(permissions.verify_read_permission)]
)
def suggestions(model_id: str, query: str):
    result = cache.suggestions(model_id=model_id, query=query)

    logging.info(f"found {len(result)} suggestions for query={query}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "suggestions": jsonable_encoder(result)},
    )


@app.get("/cache/query", dependencies=[Depends(permissions.verify_read_permission)])
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


@app.post("/cache/insert")
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


@app.post(
    "/cache/invalidate", dependencies=[Depends(permissions.verify_read_permission)]
)
def cache_invalidate(model_id: str):
    cache.invalidate(model_id=model_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "message": "invalidated cache for model id"},
    )


@app.get("/cache/token", dependencies=[Depends(permissions.verify_read_permission)])
def temporary_cache_token(model_id: str):
    logging.info(f"creating cache token for model {model_id}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "sucess",
            "access_token": permissions.create_temporary_cache_access_token(
                model_id=model_id
            ),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
