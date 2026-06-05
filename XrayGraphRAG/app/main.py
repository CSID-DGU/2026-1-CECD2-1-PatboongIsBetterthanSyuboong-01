"""FastAPI entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import routes_admin, routes_cases, routes_health, routes_inference
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title="X-ray Reconstruction Error Graph Reasoning System",
        description=(
            "분류 모델을 쓰지 않고 reconstruction error embedding의 vector similarity + "
            "ArangoDB graph reasoning으로 질병 후보를 추론하는 연구/프로토타입 시스템."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_health.router)
    app.include_router(routes_admin.router)
    app.include_router(routes_cases.router)
    app.include_router(routes_inference.router)
    app.mount("/storage", StaticFiles(directory=get_settings().STORAGE_DIR), name="storage")

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
