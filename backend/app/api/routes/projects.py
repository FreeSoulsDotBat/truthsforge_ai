from fastapi import APIRouter, HTTPException

from app.chat.session_cleanup import delete_chat_session_with_files
from app.core.contracts import (
    Project,
    ProjectCreate,
    ProjectFolder,
    ProjectFolderCreate,
    ProjectFolderDeleteResult,
    ProjectFolderUpdate,
    ProjectUpdate,
)
from app.storage.store import get_store

router = APIRouter()


@router.get("", response_model=list[Project])
def list_projects() -> list[Project]:
    store = get_store()
    if not hasattr(store, "list_projects"):
        return []
    return store.list_projects()


@router.post("", response_model=Project)
def create_project(payload: ProjectCreate) -> Project:
    store = get_store()
    if not hasattr(store, "create_project"):
        raise HTTPException(status_code=501, detail="Projetos não suportados neste backend.")
    return store.create_project(payload)


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdate) -> Project:
    store = get_store()
    if not hasattr(store, "update_project"):
        raise HTTPException(status_code=501, detail="Projetos não suportados neste backend.")
    return store.update_project(project_id, payload)


@router.get("/folders", response_model=list[ProjectFolder])
def list_project_folders(project_id: str | None = None) -> list[ProjectFolder]:
    store = get_store()
    if not hasattr(store, "list_project_folders"):
        return []
    return store.list_project_folders(project_id)


@router.post("/folders", response_model=ProjectFolder)
def create_project_folder(payload: ProjectFolderCreate) -> ProjectFolder:
    store = get_store()
    if not hasattr(store, "create_project_folder"):
        raise HTTPException(
            status_code=501, detail="Pastas de projeto não suportadas neste backend."
        )
    try:
        return store.create_project_folder(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/folders/{folder_id}", response_model=ProjectFolder)
def update_project_folder(folder_id: str, payload: ProjectFolderUpdate) -> ProjectFolder:
    store = get_store()
    if not hasattr(store, "update_project_folder"):
        raise HTTPException(
            status_code=501, detail="Pastas de projeto não suportadas neste backend."
        )
    try:
        return store.update_project_folder(folder_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/folders/{folder_id}", response_model=ProjectFolderDeleteResult)
def delete_project_folder(folder_id: str) -> ProjectFolderDeleteResult:
    store = get_store()
    if not hasattr(store, "list_project_folders") or not hasattr(store, "delete_project_folder"):
        raise HTTPException(
            status_code=501, detail="Pastas de projeto não suportadas neste backend."
        )

    folders = store.list_project_folders()
    existing = next((folder for folder in folders if folder.id == folder_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")

    descendants = {folder_id}
    changed = True
    while changed:
        changed = False
        for folder in folders:
            if folder.project_id != existing.project_id:
                continue
            if folder.parent_id in descendants and folder.id not in descendants:
                descendants.add(folder.id)
                changed = True

    chat_session_ids = [
        session.id
        for session in store.list_chat_sessions()
        if session.project_id == existing.project_id and session.folder_id in descendants
    ]
    deleted_chat_session_ids: list[str] = []
    for session_id in chat_session_ids:
        try:
            delete_chat_session_with_files(store, session_id, delete_files=True)
            deleted_chat_session_ids.append(session_id)
        except HTTPException:
            continue

    try:
        deleted_folder_ids, store_deleted_session_ids = store.delete_project_folder(folder_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    merged_chat_ids = sorted(set(deleted_chat_session_ids + list(store_deleted_session_ids)))
    return ProjectFolderDeleteResult(
        folder_id=folder_id,
        deleted_folder_ids=deleted_folder_ids,
        deleted_chat_session_ids=merged_chat_ids,
    )
