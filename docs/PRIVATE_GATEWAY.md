# Private owner gateway — server-only, not deployed

`frontend/private/gateway.mjs` is outside the normal Vercel `api` directory and
Vite import graph. The later private packaging step alone selects its Node handler.
It requires `VERCEL_ENV=preview`, explicit private mode, approved exact targets and
the server-only gate credential. Never put that credential in a `VITE_*` variable.

The Vercel project must enforce owner/project-member authentication on **every**
preview URL, without bypass links/exceptions. Require the approved `.vercel.app`
origin; Standard Protection excludes custom production domains. The gateway does
not invent a caller identity from Vercel headers/cookies. Platform authentication
must be verified separately before exposing the private app.

Only enumerated catalogue, profile/provisioning, rating, invitation and recommendation
methods/paths forward. No legacy issuance, arbitrary destination, encoded traversal,
redirect, cookie or caller gate/proxy header is forwarded. The upstream origin comes
only from reviewed server targets. Authorization still goes to the native backend;
the private capability alone grants no Movelle account/resource permission.

Writes are bounded to16KiB, responses2MiB, total I/O25s. JSON/schema validation and
all rate/ownership/MFA checks remain backend-authoritative. HTTP error codes and
numeric Retry-After survive; redirects/provider diagnostics/set-cookie do not.
Logs never include URLs, body, Authorization or the capability. No retry/fallback.

Offline tests mock Vercel's documented Node request/query/stream shape. Its rewrite
supplies one `__movelle_route` parameter; duplicate arrays fail. Actual routing,
preview protection, secret isolation and TLS remain hosted acceptance gates after
explicit deployment approval, not guarantees established by local fixtures.
