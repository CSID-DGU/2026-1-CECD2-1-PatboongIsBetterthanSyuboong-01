from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import ServiceContainer, get_container
from app.db.schema import (
    ensure_collections,
    ensure_graph,
    ensure_vector_indexes,
    seed_defaults,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/init-db")
def init_db(container: ServiceContainer = Depends(get_container)) -> dict:
    ensure_collections(container.db)
    ensure_graph(container.db, container.settings)
    seed_defaults(container.db)
    vec = ensure_vector_indexes(container.db, container.settings)
    return {
        "status": "initialized",
        "vectorIndex": vec,
        "graph": container.settings.ARANGO_GRAPH_NAME,
        "embeddingDim": container.settings.EMBEDDING_DIM,
    }
