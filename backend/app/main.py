import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.modeling import wire_tracer_store
from app.core.config import settings
from app.workers.import_queue import start_import_worker
from app.workers.index_queue import start_index_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # PR#28 review (issue 4): wire o ModelingTracer singleton à store AGORA,
    # com o app inicializado. Evita o caso degradado onde import-time tinha
    # store=None.
    wire_tracer_store()
    start_index_worker()
    start_import_worker()
    yield


def create_app() -> FastAPI:
    settings.ensure_local_dirs()

    app = FastAPI(
        title="Truth's Forge AI API",
        description="Backend local-first para JUDITE, agentes, RAG e chat multi-modelo.",
        version="0.1.0",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS: enviamos cookies/Authorization (allow_credentials=True), então o
    # coringa "*" é proibido pela spec CORS e perigoso aqui (refletir qualquer
    # Origin com credenciais vaza cross-origin). Se "*" for configurado em
    # TRUTHS_FORGE_ALLOWED_ORIGINS, descartamos e avisamos em vez de aceitar a
    # combinação insegura silenciosamente.
    allowed_origins = settings.allowed_origins
    if "*" in allowed_origins:
        logger.warning(
            "TRUTHS_FORGE_ALLOWED_ORIGINS contém '*' com allow_credentials=True; "
            "o coringa será ignorado (combinação proibida pela spec CORS). "
            "Liste origens explícitas."
        )
        allowed_origins = [origin for origin in allowed_origins if origin != "*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()
