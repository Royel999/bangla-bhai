"""Read-only workspace registry endpoints for the current-main app."""
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

import workspace_store


def create_workspace_router(db_path, authenticated_user_dependency):
    """Construct routes using the host app's trusted session-user dependency.

    The API accepts no user ID from a request body/query and exposes no
    workspace-creation or membership-management action.
    """
    router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])

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
