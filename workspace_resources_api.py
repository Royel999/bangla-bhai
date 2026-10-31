"""Workspace-scoped private chat/project APIs over fresh resource tables only."""
import json
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

import workspace_resources_store as store


NO_CACHE = {"Cache-Control": "private, no-store", "Vary": "Cookie"}
MAX_BODY_BYTES = 128 * 1024
MAX_MESSAGE_CHARS = 60000


def _error(status_code, message):
    return JSONResponse(
        status_code=status_code,
        content={"error": message},
        headers=NO_CACHE,
    )


def _same_origin(request):
    """Require an explicit same-origin Origin on cookie-authenticated mutations."""
    origin_value = request.headers.get("origin", "")
    host_value = request.headers.get("host", "")
    if not origin_value or not host_value or len(origin_value) > 2048:
        return False
    try:
        origin = urlsplit(origin_value)
        target = urlsplit("//" + host_value)
        if (
            origin.scheme not in ("http", "https")
            or not origin.hostname
            or origin.username
            or origin.password
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
            or not target.hostname
            or target.username
            or target.password
            or target.path
            or target.query
            or target.fragment
        ):
            return False
        origin_port = origin.port or (443 if origin.scheme == "https" else 80)
        target_port = target.port or (443 if origin.scheme == "https" else 80)
        if origin.hostname.casefold() != target.hostname.casefold() or origin_port != target_port:
            return False
    except ValueError:
        return False
    return request.headers.get("sec-fetch-site", "").casefold() != "cross-site"


async def _json_body(request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return None, _error(415, "application/json required")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            return None, _error(413, "request body too large")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _error(400, "invalid JSON")
    if not isinstance(value, dict):
        return None, _error(422, "JSON object required")
    return value, None


def _allowed_fields(body, allowed):
    return set(body).issubset(allowed)


def _text(value, *, maximum, required=True):
    if not isinstance(value, str):
        return None
    if required and not value.strip():
        return None
    if len(value) > maximum:
        return None
    return value


def _origin_failure(request):
    return None if _same_origin(request) else _error(403, "same-origin request required")


def create_workspace_resources_router(db_path, authenticated_user_dependency):
    """Create resource routes bound to the host app's trusted session identity.

    All resources are private to their creator even inside an OFFICIAL workspace.
    Membership/role is not treated as permission to read another member's rows.
    This router does not create workspaces, memberships, or AI-generated replies.
    """
    router = APIRouter(prefix="/api/v1/workspaces", tags=["workspace-resources"])

    @router.get("/{workspace_id}/projects")
    def list_projects(
        workspace_id: str,
        response: Response,
        limit: int = Query(50, ge=1, le=100),
        user_id: str = Depends(authenticated_user_dependency),
    ):
        rows = store.list_projects(db_path, user_id, workspace_id, limit)
        if rows is None:
            return _error(404, "not found")
        response.headers.update(NO_CACHE)
        return rows

    @router.post("/{workspace_id}/projects", status_code=201)
    async def create_project(
        workspace_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _allowed_fields(body, {"name", "instructions"}):
            return _error(422, "unsupported field")
        name = _text(body.get("name", "নতুন প্রজেক্ট"), maximum=120)
        instructions = _text(body.get("instructions", ""), maximum=8000, required=False)
        if name is None or instructions is None:
            return _error(422, "invalid project fields")
        project = store.create_project(db_path, user_id, workspace_id, name, instructions)
        if project is None:
            return _error(404, "not found")
        return JSONResponse(status_code=201, content=dict(project), headers=NO_CACHE)

    @router.get("/{workspace_id}/projects/{project_id}")
    def get_project(
        workspace_id: str,
        project_id: str,
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        project = store.get_project(db_path, user_id, workspace_id, project_id)
        if project is None:
            return _error(404, "not found")
        response.headers.update(NO_CACHE)
        return project

    @router.patch("/{workspace_id}/projects/{project_id}")
    async def update_project(
        workspace_id: str,
        project_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not body or not _allowed_fields(body, {"name", "instructions"}):
            return _error(422, "invalid project fields")
        fields = {}
        if "name" in body:
            fields["name"] = _text(body["name"], maximum=120)
            if fields["name"] is None:
                return _error(422, "invalid project name")
        if "instructions" in body:
            fields["instructions"] = _text(body["instructions"], maximum=8000, required=False)
            if fields["instructions"] is None:
                return _error(422, "invalid project instructions")
        project = store.update_project(db_path, user_id, workspace_id, project_id, fields)
        if project is None:
            return _error(404, "not found")
        return JSONResponse(content=project, headers=NO_CACHE)

    @router.delete("/{workspace_id}/projects/{project_id}")
    def delete_project(
        workspace_id: str,
        project_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        if not store.delete_project(db_path, user_id, workspace_id, project_id):
            return _error(404, "not found")
        return JSONResponse(content={"ok": True}, headers=NO_CACHE)

    @router.get("/{workspace_id}/chats")
    def list_chats(
        workspace_id: str,
        response: Response,
        limit: int = Query(50, ge=1, le=100),
        user_id: str = Depends(authenticated_user_dependency),
    ):
        rows = store.list_chats(db_path, user_id, workspace_id, limit)
        if rows is None:
            return _error(404, "not found")
        response.headers.update(NO_CACHE)
        return rows

    @router.post("/{workspace_id}/chats", status_code=201)
    async def create_chat(
        workspace_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _allowed_fields(body, {"title", "project_id"}):
            return _error(422, "unsupported field")
        title = _text(body.get("title", "নতুন চ্যাট"), maximum=200)
        project_id = body.get("project_id")
        if project_id is not None and (not isinstance(project_id, str) or not project_id):
            return _error(422, "invalid project_id")
        if title is None:
            return _error(422, "invalid chat title")
        chat = store.create_chat(db_path, user_id, workspace_id, title, project_id)
        if chat is None:
            return _error(404, "not found")
        return JSONResponse(status_code=201, content=chat, headers=NO_CACHE)

    @router.get("/{workspace_id}/chats/{chat_id}")
    def get_chat(
        workspace_id: str,
        chat_id: str,
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        chat = store.get_chat(db_path, user_id, workspace_id, chat_id)
        if chat is None:
            return _error(404, "not found")
        response.headers.update(NO_CACHE)
        return chat

    @router.patch("/{workspace_id}/chats/{chat_id}")
    async def update_chat(
        workspace_id: str,
        chat_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not body or not _allowed_fields(body, {"title", "pinned", "project_id"}):
            return _error(422, "invalid chat fields")
        fields = {}
        if "title" in body:
            fields["title"] = _text(body["title"], maximum=200)
            if fields["title"] is None:
                return _error(422, "invalid chat title")
        if "pinned" in body:
            pinned = body["pinned"]
            if not isinstance(pinned, (bool, int)) or pinned not in (False, True, 0, 1):
                return _error(422, "invalid pinned value")
            fields["pinned"] = int(bool(pinned))
        if "project_id" in body:
            project_id = body["project_id"]
            if project_id is not None and (not isinstance(project_id, str) or not project_id):
                return _error(422, "invalid project_id")
            fields["project_id"] = project_id
        chat = store.update_chat(db_path, user_id, workspace_id, chat_id, fields)
        if chat is None:
            return _error(404, "not found")
        return JSONResponse(content=chat, headers=NO_CACHE)

    @router.delete("/{workspace_id}/chats/{chat_id}")
    def delete_chat(
        workspace_id: str,
        chat_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        if not store.delete_chat(db_path, user_id, workspace_id, chat_id):
            return _error(404, "not found")
        return JSONResponse(content={"ok": True}, headers=NO_CACHE)

    @router.post("/{workspace_id}/chats/{chat_id}/messages", status_code=201)
    async def append_message(
        workspace_id: str,
        chat_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _allowed_fields(body, {"content"}):
            return _error(422, "unsupported field")
        content = _text(body.get("content"), maximum=MAX_MESSAGE_CHARS)
        if content is None:
            return _error(422, "invalid message content")
        message = store.append_user_message(
            db_path, user_id, workspace_id, chat_id, content
        )
        if message is None:
            return _error(404, "not found")
        return JSONResponse(status_code=201, content=message, headers=NO_CACHE)

    return router
