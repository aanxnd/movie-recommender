"""Outer ASGI gate: deny before body parsing, database admission or provider I/O."""
from hashlib import sha256
from hmac import compare_digest
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

HEADER = b'x-movelle-private-gate'


class PrivateGate:
    def __init__(self, app, *, secret, frontend, backend):
        self.app, self.digest = app, sha256(secret.encode('ascii')).digest()
        self.frontend, self.host = frontend.encode('ascii'), urlsplit(backend).netloc.encode('ascii')

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = scope['headers']
        values = lambda name: [v for k, v in headers if k.lower() == name]
        gates = values(HEADER)
        if (len(gates) != 1 or len(gates[0]) != 43
                or not compare_digest(sha256(gates[0]).digest(), self.digest)
                or values(b'host') != [self.host] or values(b'origin') != [self.frontend]):
            return await JSONResponse({'detail': 'Private access denied'}, status_code=403,
                headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})(scope, receive, send)
        # Strip the capability and every client-controlled proxy identity before
        # application/error handlers. Shared gateway IP quotas remain conservative.
        safe = [(k, v) for k, v in headers if k.lower() != HEADER
                and not k.lower().startswith((b'x-forwarded-', b'forwarded', b'x-real-ip'))]
        await self.app({**scope, 'headers': safe}, receive, send)
