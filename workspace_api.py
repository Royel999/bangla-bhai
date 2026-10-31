"""Workspace registry endpoints for the current-main app."""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

import workspace_store
import workspace_membership_store as membership_store
from workspace_resources_api import _allowed_fields, _error, _json_body, _origin_failure, _text


def create_workspace_router(db_path, authenticated_user_dependency, configured_owner_id=None):
    """Construct routes using the host app's trusted session-user dependency.

    User identity is always supplied by the host app's authenticated session.
    PERSONAL creation is explicit; OFFICIAL membership changes live in the
    separate owner-controlled membership router. OFFICIAL creation is an explicit,
    configured-owner-only action; the session role is never used for governance.
    """
    router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])

    @router.post("", status_code=201)
    async def create_personal_workspace(
        request: Request,
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _allowed_fields(body, {"name"}):
            return _error(422, "unsupported field")
        name = _text(body.get("name", "ব্যক্তিগত"), maximum=120)
        if name is None:
            return _error(422, "invalid workspace name")
        try:
            workspace = membership_store.create_personal_workspace(db_path, user_id, name)
        except membership_store.MembershipConflict:
            return _error(409, "PERSONAL workspace already exists")
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        return workspace

    @router.post("/official", status_code=201)
    async def create_official_workspace(
        request: Request,
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _allowed_fields(body, {"name"}):
            return _error(422, "unsupported field")
        name = _text(body.get("name"), maximum=120)
        if name is None:
            return _error(422, "invalid workspace name")
        try:
            workspace = membership_store.create_official_workspace(
                db_path, user_id, configured_owner_id, name
            )
        except membership_store.MembershipNotFound:
            return _error(404, "not found")
        except membership_store.MembershipConflict:
            return _error(409, "active OFFICIAL workspace name already exists")
        except ValueError:
            return _error(422, "invalid workspace name")
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        return workspace

    @router.get("")
    def list_workspaces(
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        return workspace_store.list_active_workspaces(db_path, user_id)

    @router.get("/{workspace_id}")
    def get_workspace(
        workspace_id: str,
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        workspace = workspace_store.get_active_workspace(db_path, user_id, workspace_id)
        if workspace is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not found"},
                headers={"Cache-Control": "private, no-store", "Vary": "Cookie"},
            )
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        return workspace

    return router
