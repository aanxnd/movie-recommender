"""Shared native composition, without deployment activation or legacy private routes."""
from contextlib import asynccontextmanager

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import artwork, limits
from app.main import create_app
from app.migrations import check_schema
from app.provisioning_routes import make_provisioning_router
from app.staging_profiles import profile_router
from app.staging_recommendations import recommendation_router
from app.supabase_auth import make_supabase_auth_dependency


PUBLIC = {'/health', '/ready', '/movies/search', '/movies/decades', '/movies/{movie_id}',
          '/recommendations/popular', '/recommendations/genre/{genre}', '/movies/artwork-image/{movie_id}/{role}',
          '/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'}

def compose_native_app(*, prepared_dir, database_url, project_url, publishable_key, audience, origin, title='Movelle native API', preflight_error='Native preflight failed', policy=None):
    """Explicit trusted composition; release/local/private bootstraps retain separate guards."""
    def keyless_artwork(app):
        app.state.artwork = artwork.ArtworkStore(app.state.catalog)
    application = create_app(prepared_dir=prepared_dir, database_url=database_url,
                             schema_initializer=check_schema, artwork_initializer=keyless_artwork)
    # Reuse public algorithms/lifespan/middleware, retaining NO legacy private
    # handler. An allowlist means a new production route cannot leak into staging.
    application.router.routes = [r for r in application.routes if getattr(r, 'path', None) in PUBLIC
                                 and getattr(r, 'methods', set()) <= {'GET', 'HEAD'}]
    application.add_api_route('/movies/artwork-image/{movie_id}/{role}', artwork.cached_artwork_image, methods=['GET'])
    application.title = title
    for middleware in application.user_middleware:
        if middleware.cls is CORSMiddleware:
            middleware.kwargs['allow_origins'] = [origin]
            middleware.kwargs['allow_methods'] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    inherited = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        try:
            # The shared lifecycle checks the current schema directly, never its legacy
            # development migrator or ambient production artwork configuration.
            async with inherited(app):
                yield
        except Exception:
            raise RuntimeError(preflight_error) from None
    application.router.lifespan_context = lifespan

    def sessions():
        return Session(application.state.engine, info={'lifecycle_enabled': getattr(application.state, 'lifecycle_enabled', False)})
    authenticate = make_supabase_auth_dependency(project_url=project_url, audience=audience,
        publishable_key=publishable_key, session_factory=sessions, policy=policy)
    application.include_router(profile_router(authenticate))
    application.include_router(recommendation_router(authenticate))
    application.include_router(make_provisioning_router(project_url=project_url, audience=audience,
        publishable_key=publishable_key, session_factory=sessions, allowed_origins=[origin], policy=policy))

    @application.middleware('http')
    async def boundary(request: Request, call_next):
        origins = request.headers.getlist('origin')
        if origins and origins != [origin]:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Origin not permitted'}, status_code=403, headers={'Cache-Control': 'no-store'})
        try:
            response = await call_next(request)
        except Exception:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Operation unavailable'}, status_code=503,
                                headers={'Cache-Control': 'no-store'})
        response.headers['Cache-Control'] = 'no-store'
        return response

    @application.post('/movies/artwork')
    def images(body: artwork.ArtworkLookup, request: Request, response: Response):
        if body.personal_key is not None:
            authenticate(request, response)  # Native-only; never call legacy artwork authentication.
        with sessions() as session, session.begin():
            limits.consume(session, request.client.host if request.client else 'unknown', 'artwork', 40, 60)
            limits.consume(session, 'all', 'artwork-global', 180, 60)
        store = application.state.artwork
        return {'items': store.batch(body.movie_ids, body.personal_key.get_secret_value() if body.personal_key else None,
                                      body.include_credits), 'configured': bool(store.trakt_id and store.fanart_key),
                'provider': 'trakt+fanart.tv'}
    return application
