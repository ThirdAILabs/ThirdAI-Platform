from cache import Cache, NDBSemanticCache
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


@app.get(
    "/cache/suggestions", dependencies=[Depends(permissions.verify_read_permission)]
)
def suggestions(model_id: str, query: str):
    result = cache.suggestions(model_id=model_id, query=query)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "suggestions": jsonable_encoder(result)},
    )


@app.get("/cache/query", dependencies=[Depends(permissions.verify_read_permission)])
def cache_query(model_id: str, query: str):
    result = cache.query(model_id=model_id, query=query)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "cached_response": jsonable_encoder(result)},
    )


@app.post("/cache/insert", dependencies=[Depends(permissions.verify_read_permission)])
def cache_insert(model_id: str, query: str, llm_res: str):
    cache.insert(model_id=model_id, query=query, llm_res=llm_res)

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
