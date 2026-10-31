"""Owner-controlled OFFICIAL membership requests and decisions."""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

import workspace_membership_store as store
from workspace_resources_api import NO_CACHE, _error, _json_body, _origin_failure


def _body_must_be_empty_object(body):
    return not body


def create_workspace_membership_router(db_path, authenticated_user_dependency, configured_owner_id):
    """Construct membership routes using the app's session actor and exact owner ID."""
    router = APIRouter(prefix="/api/v1/workspace-memberships", tags=["workspace-memberships"])

    @router.get("/management")
    def management(
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        data = store.owner_membership_management(db_path, user_id, configured_owner_id)
        if data is None:
            return _error(404, "not found")
        response.headers.update(NO_CACHE)
        return data

    @router.get("/requests/mine")
    def my_requests(
        response: Response,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        response.headers.update(NO_CACHE)
        return store.list_my_membership_requests(db_path, user_id)

    @router.post("/requests/{workspace_id}")
    async def request_membership(
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
        if not _body_must_be_empty_object(body):
            return _error(422, "unsupported field")
        try:
            result = store.request_official_membership(db_path, user_id, workspace_id)
        except store.MembershipNotFound:
            return _error(404, "not found")
        except store.MembershipConflict:
            return _error(409, "membership request is not available in the current state")
        response = JSONResponse(
            status_code=201 if result["created"] else 200,
            content={"id": result["id"], "status": result["status"]},
            headers=NO_CACHE,
        )
        return response

    @router.post("/requests/{request_id}/approve")
    async def approve_request(
        request_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _body_must_be_empty_object(body):
            return _error(422, "unsupported field")
        try:
            result = store.decide_membership_request(
                db_path, user_id, configured_owner_id, request_id, "approved"
            )
        except store.MembershipNotFound:
            return _error(404, "not found")
        except store.MembershipConflict:
            return _error(409, "request has already been decided or needs manual review")
        return JSONResponse(content=result, headers=NO_CACHE)

    @router.post("/requests/{request_id}/reject")
    async def reject_request(
        request_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _body_must_be_empty_object(body):
            return _error(422, "unsupported field")
        try:
            result = store.decide_membership_request(
                db_path, user_id, configured_owner_id, request_id, "rejected"
            )
        except store.MembershipNotFound:
            return _error(404, "not found")
        except store.MembershipConflict:
            return _error(409, "request has already been decided")
        return JSONResponse(content=result, headers=NO_CACHE)

    @router.post("/workspaces/{workspace_id}/members/{member_user_id}/revoke")
    async def revoke_member(
        workspace_id: str,
        member_user_id: str,
        request: Request,
        user_id: str = Depends(authenticated_user_dependency),
    ):
        denied = _origin_failure(request)
        if denied:
            return denied
        body, error = await _json_body(request)
        if error:
            return error
        if not _body_must_be_empty_object(body):
            return _error(422, "unsupported field")
        try:
            result = store.revoke_official_membership(
                db_path, user_id, configured_owner_id, workspace_id, member_user_id
            )
        except store.MembershipNotFound:
            return _error(404, "not found")
        except store.MembershipConflict:
            return _error(409, "membership cannot be revoked in the current state")
        return JSONResponse(content=result, headers=NO_CACHE)

    return router
