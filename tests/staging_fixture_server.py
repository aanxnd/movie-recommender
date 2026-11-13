"""TEST ONLY: actual staging HTTP app + isolated PG schema + fictional HTTP Auth.

No production module imports this, and no runtime flag can enable these transport patches.
"""
from contextlib import contextmanager, ExitStack
from pathlib import Path
import csv
import os
import signal
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
from unittest.mock import patch
from urllib.request import build_opener, ProxyHandler, Request as URLRequest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
import uvicorn

from app import database, supabase_policy
from app.models import Base, Credential, User, UserIdentity, UserRating
from app.staging import create_staging_app
from app.supabase_jwt import SupabaseTokenVerifier
from scripts.prepare_movielens import prepare_movielens
from staging_provider import PROJECT, ProviderFixture
from test_postgresql import local_test_url


@contextmanager
def http_server(app, port):
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='error', proxy_headers=False))
    thread = Thread(target=server.run, daemon=True); thread.start()
    deadline = time.monotonic() + 30
    try:
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline: raise RuntimeError('Local fixture startup failed')
            time.sleep(.05)
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True; thread.join(timeout=15)
        if thread.is_alive(): raise RuntimeError('Local fixture shutdown failed')


@contextmanager
def staging_fixture(database_url, *, api_port=19001, provider_port=19002):
    url = local_test_url(database_url)
    if url.database != 'disposable': raise ValueError('Disposable fixture database required')
    admin = database.create_database_engine(database_url=url.render_as_string(hide_password=False))
    schema = 'verify_' + uuid4().hex
    with admin.begin() as connection: connection.execute(text(f'CREATE SCHEMA {schema}'))
    scoped = url.set(query={**url.query, 'options': f'-c search_path={schema}'})
    engine = database.create_database_engine(database_url=scoped.render_as_string(hide_password=False))
    stopped, provider = Event(), ProviderFixture()
    try:
        database.create_schema(engine)
        @provider.app.api_route('/_fixture/{action}', methods=['GET', 'POST'])
        async def control(action: str, request: Request):
            if action == 'shutdown': stopped.set(); return {'ok': True}
            if action == 'reset':
                with engine.begin() as connection:
                    for table in reversed(Base.metadata.sorted_tables):
                        if table.name not in {'schema_version', 'movies'}: connection.execute(table.delete())
                provider.reset(); return {'ok': True}
            if action == 'otp': return {'code': provider.otp()}
            if action == 'outage': provider.outage = request.query_params.get('enabled') == 'true'; return {'ok': True}
            if action == 'link':
                code, link = next((c, l) for c, l in reversed(list(provider.links.items())) if l['method'] == request.query_params['flow'])
                user = provider.users[link['subject']]
                if link['method'] == 'email_change': user['email'] = user.pop('new_email')
                user['email_confirmed_at'] = '2026-01-01T00:00:00Z'
                return {'code': code}
            if action == 'token':
                case = request.query_params.get('case'); changes = {'iss': 'https://foreign.invalid'} if case == 'issuer' else {'exp': 1}
                return {'token': provider.token(next(iter(provider.users)), changes=changes)['access_token']}
            with Session(engine) as session:
                return {name: session.scalar(select(func.count()).select_from(model)) for name, model in
                        [('users', User), ('identities', UserIdentity), ('ratings', UserRating), ('credentials', Credential)]}
        with ExitStack() as stack:
            target = stack.enter_context(http_server(provider.app, provider_port))
            opener = build_opener(ProxyHandler({}))
            def read(url, key=None, token=None):
                if not url.startswith(PROJECT + '/auth/v1/'): raise ValueError('Unexpected fixture destination')
                request = URLRequest(target + url.removeprefix(PROJECT),
                    headers={'Authorization': 'Bearer '+token} if token else {})
                with opener.open(request, timeout=3) as response: return response.read(65537)
            stack.enter_context(patch.object(supabase_policy, '_read_user', read))
            stack.enter_context(patch.object(supabase_policy, 'SupabaseTokenVerifier',
                lambda origin, audience: SupabaseTokenVerifier(origin, audience=audience, fetch=read)))
            directory = Path(stack.enter_context(TemporaryDirectory(prefix='movelle-staging-fixture-')))
            for filename, rows in [('movies.csv', [('movieId','title','genres'), (1,'First Film','Drama'),
                (2,'Second Film','Drama'), (3,'Third Film','Drama'), (4,'Fourth Film','Drama'), (5,'Fifth Film','Drama')]),
                ('ratings.csv', [('userId','movieId','rating')] +
                 [(uid, mid, 1+(uid+mid*2)%5) for uid in range(1, 26) for mid in range(1, 6)])]:
                with (directory/filename).open('w', newline='', encoding='utf-8') as file: csv.writer(file).writerows(rows)
            (directory/'README.txt').write_text('Fictional offline integration data', encoding='utf-8')
            prepared = prepare_movielens(directory, directory/'prepared')
            application = create_staging_app(prepared_dir=prepared, database_url=scoped.render_as_string(hide_password=False),
                project_url=PROJECT, publishable_key='sb_publishable_offline')
            api = stack.enter_context(http_server(application, api_port))
            yield api, target, stopped
    finally:
        engine.dispose()
        with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        admin.dispose()


if __name__ == '__main__':
    marker = Path(__file__).resolve().parents[1]/'.pytest-tmp'/'staging-fixture.done'
    marker.parent.mkdir(exist_ok=True); marker.unlink(missing_ok=True)
    outcome = 'failed'
    try:
        with staging_fixture(os.environ['POSTGRES_TEST_URL']) as (_, _, stopped):
            signal.signal(signal.SIGTERM, lambda *_: stopped.set())
            signal.signal(signal.SIGINT, lambda *_: stopped.set())
            print('OFFLINE STAGING FIXTURE READY', flush=True)
            stopped.wait()
        outcome = 'clean'
    except Exception:
        raise SystemExit('Offline staging fixture failed; no hosted request was made') from None
    finally:
        temporary = marker.with_suffix('.tmp')
        temporary.write_text(outcome, encoding='utf-8')
        temporary.replace(marker)  # Atomic process-lifecycle status, never identity/token evidence.
