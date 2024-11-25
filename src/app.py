from fastapi import FastAPI

from api.v1.router import router as v1_router


def create_app() -> FastAPI:
    app = FastAPI()

    app.include_router(v1_router, prefix='/v1', tags=['v1'])
    return app

