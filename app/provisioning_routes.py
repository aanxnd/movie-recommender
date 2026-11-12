"""Explicit dormant route factory. Never imported or mounted by app.main."""
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError

from app import limits
from app.provisioning import inspect_profile, provision_profile, unavailable
from app.provisioning_principal import ProfileInput, make_provisioning_dependency


class _PrivateRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()
        async def redacted(request):
            try:
                response = await handle(request)
                response.headers['Cache-Control'] = 'no-store'
                return response
            except RequestValidationError:
                raise HTTPException(422, 'Invalid profile input', headers={'Cache-Control': 'no-store'}) from None
            except HTTPException as error:
                error.headers = {**(error.headers or {}), 'Cache-Control': 'no-store'}
                raise
        return redacted


def make_provisioning_router(*, project_url, audience, publishable_key, session_factory, allowed_origins):
    """Future approved staging composition only. Parent must install RequestLimits
    and exact-origin CORS (no cookies). No environment variable activates this.
    Factory configuration is trusted server code, never HTTP input.
    """
    origins = frozenset(allowed_origins)
    if not origins or any(type(origin) is not str or
            not (origin == 'http://127.0.0.1:5173' or
                 (urlsplit(origin).scheme == 'https' and urlsplit(origin).netloc and
                  origin == 'https://' + urlsplit(origin).netloc and '@' not in origin)) for origin in origins):
        raise ValueError('Exact approved origins required')
    authenticate = make_provisioning_dependency(project_url=project_url, audience=audience,
                                                 publishable_key=publishable_key)
    router = APIRouter(route_class=_PrivateRoute)

    def admit(request, principal, creating):
        origin_headers = request.headers.getlist('origin')
        if origin_headers and (len(origin_headers) != 1 or origin_headers[0] not in origins):
            raise HTTPException(403, 'Origin not permitted')
        if request.query_params:
            raise HTTPException(422, 'Invalid profile input')
        try:
            # Commit quotas independently so conflicts/rollbacks do not refund them.
            with session_factory() as session, session.begin():
                limits.consume(session, str(principal.subject), 'profile-setup', 30, 60)
                if creating:
                    limits.consume(session, str(principal.subject), 'profile-create', 10, 3600)
                    limits.consume(session, 'all', 'create-global', 1000, 86400)
        except SQLAlchemyError:
            raise unavailable() from None

    def result(profile):
        return {'status': 'complete', 'username': profile.username} if profile else {'status': 'eligible'}

    @router.get('/auth/profile')
    def inspect(request: Request, principal=Depends(authenticate)):
        admit(request, principal, False)
        return result(inspect_profile(session_factory, principal))

    @router.post('/auth/profile')
    def provision(input: ProfileInput, request: Request, principal=Depends(authenticate)):
        admit(request, principal, True)
        return result(provision_profile(session_factory, principal, input))

    return router
