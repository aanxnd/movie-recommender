"""Explicit candidate factory only. Current native/legacy/private bootstraps never call it."""
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import limits
from app.account_settings_routes import account_settings_router
from app.deletion_authorization import DeletionAuthorizer, DeletionAwarePolicy
from app.deletion_store import DeletionStore, DeletionUnavailable, metadata
from app.native_app import compose_native_app
from app.provisioning_routes import _PrivateRoute
from app.supabase_auth import _bearer_token, _invalid_credentials
from app.supabase_jwt import InvalidAccessToken
from app.supabase_policy import AccessDenied


class DeletionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    request_id: UUID
    password: SecretStr
    confirmation: str
    factor_id: UUID | None = None
    code: SecretStr | None = None

    @field_validator('request_id')
    @classmethod
    def nonzero(cls, value):
        if not value.int: raise ValueError('Invalid account input')
        return value


def deletion_router(store, authorizer, origin):
    if store.issuer != authorizer.issuer:
        raise DeletionUnavailable()
    router = APIRouter(route_class=_PrivateRoute)

    @router.post('/auth/deletion')
    def request_deletion(request: Request, response: Response, body: DeletionInput):
        if request.query_params or (request.headers.getlist('origin') not in ([], [origin])):
            raise HTTPException(403, 'Request not permitted')
        if body.confirmation != 'PERMANENTLY DELETE MY ACCOUNT':
            raise HTTPException(422, 'Invalid account input')
        token = _bearer_token(request, response)
        try:
            with store.sessions() as session, session.begin():
                limits.consume(session, request.client.host if request.client else 'unknown', 'delete-request', 3, 3600)
                limits.consume(session, 'all', 'delete-global', 20, 86400)
            principal = authorizer.authorize(token, body.password, body.factor_id, body.code)
            store.request(principal, body.request_id, body.confirmation)
            return {'status': 'pending'}  # Never claim identity/data deletion from enqueue success.
        except (AccessDenied, InvalidAccessToken):
            raise _invalid_credentials() from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'Account deletion unavailable', headers={'Cache-Control': 'no-store'}) from None
    return router


def compose_deletion_candidate(*, signing_key, reviewed=False, **config):
    if reviewed is not True:
        raise DeletionUnavailable()
    holder = {}
    sessions = lambda: Session(holder['app'].state.engine)
    authorizer = DeletionAuthorizer(config['project_url'], config['publishable_key'])
    store = DeletionStore(sessions, authorizer.issuer, signing_key)
    policy = DeletionAwarePolicy(authorizer.policy, store)
    app = compose_native_app(**config, policy=policy)
    app.router.routes = [r for r in app.routes if getattr(r, 'path', None) not in
                        {'/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'}]
    holder['app'] = app
    app.state.lifecycle_enabled = True
    resource_sessions = lambda: Session(app.state.engine, info={'lifecycle_enabled': True})
    app.include_router(account_settings_router(project_url=config['project_url'], audience=config['audience'],
        publishable_key=config['publishable_key'], session_factory=resource_sessions, origin=config['origin'], policy=policy))
    app.include_router(deletion_router(store, authorizer, config['origin']))
    inherited = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with inherited(application):
            inspector = inspect(application.state.engine)
            for table in metadata.sorted_tables:
                if not inspector.has_table(table.name) or not set(table.columns.keys()) <= {c['name'] for c in inspector.get_columns(table.name)}:
                    raise RuntimeError('Lifecycle schema unavailable')
            yield
    app.router.lifespan_context = lifespan
    return app
