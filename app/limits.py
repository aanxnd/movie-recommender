"""Database-backed fixed-window admission, shared by every replica."""

import asyncio
import hashlib
import time

from fastapi import HTTPException
from sqlalchemy import case, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.database import conflict_insert
from app.models import RateBucket


MAX_BODY_BYTES = 16 * 1024
MAX_PROFILE_RATINGS = 100
MAX_GROUP_RATINGS = 200
MAX_GROUP_MEMBERS = 5


def consume(session, subject: str, scope: str, allowance: int, seconds: int, *, now: int | None = None):
    now = int(time.time()) if now is None else now
    window = now // seconds
    key = scope + ':' + hashlib.sha256(subject.encode()).hexdigest()
    statement = conflict_insert(RateBucket, session.get_bind().dialect.name).values(
        key=key, window=window, count=1, expires_at=(window + 1) * seconds)
    statement = statement.on_conflict_do_update(index_elements=['key'], set_={
        'window': window,
        'count': case((RateBucket.window != window, 1), else_=RateBucket.count + 1),
        'expires_at': (window + 1) * seconds,
    }, where=(RateBucket.window != window) | (RateBucket.count < allowance)).returning(RateBucket.count)
    if session.execute(statement).scalar_one_or_none() is None:
        raise HTTPException(429, 'Request limit reached; wait before trying again', headers={'Retry-After': str(seconds - now % seconds)})


def public_admission(engine, host, creating):
    # Commit admission separately: rejected endpoint work must not refund abuse quotas.
    with Session(engine) as session, session.begin():
        consume(session, host, 'public', 180, 60)
        if creating:
            consume(session, host, 'create', 10, 3600)
            consume(session, 'all', 'create-global', 1000, 86400)
        # Bounded retention of counters only; never delete profiles or ratings.
        session.execute(delete(RateBucket).where(RateBucket.expires_at < int(time.time()) - 86400))


def owner_admission(engine, user_id, scope, allowance):
    with Session(engine) as session, session.begin():
        consume(session, str(user_id), scope, allowance, 60)
        if scope == 'recommend':
            consume(session, 'all', 'recommend-global', 30, 60)


class RequestLimits:
    """Bound HTTP bodies before JSON decoding, including chunked transfers."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, send)
        path = scope['path']
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    body.extend(message.get('body', b''))
                    if len(body) > MAX_BODY_BYTES:
                        return await JSONResponse({'detail': 'Request body too large'}, status_code=413)(scope, receive, send)
                    if not message.get('more_body', False):
                        break
        except TimeoutError:
            return await JSONResponse({'detail': 'Request body timeout'}, status_code=408)(scope, receive, send)
        if path not in {'/health', '/ready'}:
            try:
                engine = scope['app'].state.engine
                host = (scope.get('client') or ('unknown', 0))[0]
                await run_in_threadpool(public_admission, engine, host, path == '/users' and scope['method'] == 'POST')
            except HTTPException as error:
                return await JSONResponse({'detail': error.detail}, status_code=error.status_code, headers=error.headers)(scope, receive, send)
            except SQLAlchemyError:
                return await JSONResponse({'detail': 'Admission service unavailable'}, status_code=503)(scope, receive, send)
        consumed = False
        async def buffered_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        await self.app(scope, buffered_receive, send)
