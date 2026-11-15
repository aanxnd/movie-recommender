"""Explicit native composition only; no default/legacy application import."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.account_settings import UsernameInput, profile_settings
from app.provisioning_principal import make_provisioning_dependency
from app.provisioning_routes import _PrivateRoute


def account_settings_router(*, project_url, audience, publishable_key, session_factory, origin, policy=None):
    authenticate = make_provisioning_dependency(project_url=project_url, audience=audience,
                                               publishable_key=publishable_key, policy=policy)
    router = APIRouter(route_class=_PrivateRoute)
    Principal = Annotated[object, Depends(authenticate)]

    def admit(request):
        origins = request.headers.getlist('origin')
        if request.query_params or (origins and origins != [origin]):
            raise HTTPException(403, 'Request not permitted')

    @router.get('/auth/settings')
    def inspect(request: Request, principal: Principal):
        admit(request)
        return profile_settings(session_factory, principal)

    @router.patch('/auth/settings')
    def change(request: Request, body: UsernameInput, principal: Principal):
        admit(request)
        return profile_settings(session_factory, principal, body)

    return router
