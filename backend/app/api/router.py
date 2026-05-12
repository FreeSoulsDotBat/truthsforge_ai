from fastapi import APIRouter

from app.api.routes import (
    agents,
    audit,
    chat,
    cost,
    documents,
    files,
    health,
    imports,
    knowledge,
    modeling,
    models,
    projects,
    prompts,
    server,
    settings,
    tools,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(server.router, prefix="/api/server", tags=["server"])
api_router.include_router(chat.router, prefix="/api/chat", tags=["chat"])
api_router.include_router(models.router, prefix="/api/models", tags=["models"])
api_router.include_router(agents.router, prefix="/api/agents", tags=["agents"])
api_router.include_router(prompts.router, prefix="/api/prompts", tags=["prompts"])
api_router.include_router(projects.router, prefix="/api/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/api/documents", tags=["documents"])
api_router.include_router(knowledge.router, prefix="/api/knowledge-bases", tags=["knowledge"])
api_router.include_router(files.router, prefix="/api/files", tags=["files"])
api_router.include_router(imports.router, prefix="/api/imports", tags=["imports"])
api_router.include_router(audit.router, prefix="/api/audit", tags=["audit"])
api_router.include_router(cost.router, prefix="/api/cost", tags=["cost"])
api_router.include_router(settings.router, prefix="/api/settings", tags=["settings"])
api_router.include_router(tools.router, prefix="/api/tools", tags=["tools"])
api_router.include_router(modeling.router, prefix="/api/3d", tags=["3d-modeling"])
