# Film providers and artwork setup

Movelle enriches its own MovieLens catalogue with Trakt metadata and Fanart.tv artwork. It does not import provider ratings into recommendations, use provider genres for collaborative filtering, change MovieLens IDs, or ask users to sign in to Trakt. No database migration is introduced.

## Backend configuration

| Name | Purpose |
|---|---|
| TRAKT_CLIENT_ID | Trakt application's client ID, sent only as the server's trakt-api-key header. |
| FANART_API_KEY | Fanart.tv project key, sent only as the server's api-key header. |
| MOVELLE_ARTWORK_LINKS | Optional matching MovieLens links.csv with sibling movies.csv, verified against catalogue titles. IMDb IDs are used; other provider ID columns are ignored. |
| MOVELLE_ARTWORK_CACHE_DIR | Optional writable metadata cache. New records live under trakt-fanart-v1. |

No TRAKT_CLIENT_SECRET is used: public metadata/people/search GET endpoints need the client ID, not user OAuth. Never put provider keys or a database connection in VITE variables. Vercel retains only its existing public VITE_API_BASE_URL. The image CSP replaces the retired CDN with https://assets.fanart.tv; other directives are unchanged.

Register/inspect applications at https://developer.trakt.tv/ and https://fanart.tv/get-an-api-key/. Keep both developer contacts accurate. The Fanart.tv project owner must personally verify that their account email remains current. No account settings are modified by this implementation.

## Requests and matching

- With catalogue-verified MovieLens links: GET https://api.trakt.tv/movies/{imdb_id}?extended=full. Returned IMDb identity and release year are checked (at most one year's discrepancy for a verified external ID).
- Without links: GET /search/movie?query=TITLE&extended=full&limit=10, select a unique normalized title/alternate-title and exact year, then confirm it using GET /movies/{trakt_id}?extended=full. Do not select the first fuzzy result. Empty non-Latin transliterations never count as a match. Limited search coverage can result in honest missing metadata.
- Movie details: GET /movies/{trakt_id}/people for available directors, only when details are opened. Empty/unsupported credits remain absent.
- Artwork: GET https://webservice.fanart.tv/v3.2/movies/{imdb_id}?source=imdb with api-key and optional client-key headers. Verify response imdb_id exactly. Select one poster and backdrop, deterministically preferring English, then textless artwork, likes, resolution, and stable identifiers. Validate dimensions and URLs. Do not return the raw artwork catalogue.

Overview, release date, runtime and director text are display fields only. Provider text renders through React text nodes, never HTML. Only HTTPS assets.fanart.tv image paths are accepted, without credentials, traversal, queries or fragments. Documented /preview/ (maximum 200px) and /bigpreview/ (maximum 400px) variants reduce grid downloads; srcset widths account for the actual image aspect ratio. Full backdrops support featured/detail views. Missing images use the existing fallback; there is no alternate-provider fallback.

Trakt may return other provider identifiers and image fields; these are ignored. Fanart.tv internally maps IMDb IDs to its catalogue IDs and can return original image credit links pointing to another provider. Credit links are preserved as passive attribution only, not fetched or used as metadata/image sources. This integration makes no claim about the providers' internal data provenance. TMDB is no longer a runtime client, credential, image origin, cache source or branding dependency. Historical Git commits and upstream MovieLens documentation remain intact.

## Privacy and resource controls

The application endpoint accepts 1-8 canonical MovieLens IDs, not external IDs, arbitrary URLs, paths or provider parameters. It exists solely for Movelle catalogue display. General admission remains in force, plus shared-database artwork limits of 40 requests/minute/source and 180/minute globally. Responses use Cache-Control: no-store. It is not a generic provider proxy, export, or third-party feed.

HTTP concurrency is capped at three per backend process. Each film has an eight-second upstream work budget; HTTP reads have a 2.5-second timeout, bounded response size, and at most one transient retry. Authentication/access errors and 429s are not immediately retried. Retry-After is respected and repeated failures use exponential cooldowns. A conservative 200-request/provider/process/five-minute budget also applies to retries and personal keys. Trakt Standard currently documents 500 GETs/five minutes per client/public IP; account for replica/NAT sharing before scaling. Read real rate-limit headers and respect provider changes. See https://developer.trakt.tv/docs/rate-limiting .

In-process singleflight deduplicates simultaneous lookups. Public metadata/artwork/credits have separate seven-day freshness and six-hour missing-result TTLs; transient failures are never recorded as missing films. Stale public data may cover an outage up to 30 days from fetch. Expired data is removed on access; unused disk records require periodic operator cleanup. Memory is bounded to 2,048 records. These are feature-driven caches, not catalogue harvesting or a reusable dataset. No catalogue prefetch, latest-feed poller or startup network calls exist. New provider keys are required to use their caches; retired cache files are ignored, never converted or republished. Retire old storage/credentials only through an approved operator change.

## Optional personal Fanart.tv keys

Profile -> Artwork access accepts a masked 32-character personal key, only after a Movelle profile is selected. This is optional; ordinary viewing uses the project key. The key is submitted in an HTTPS JSON body to Movelle with owner authorization, then sent to Fanart.tv using its documented client-key header alongside the project api-key header. No key appears in a URL or browser CDN request.

The browser keeps the key only in tab memory, not localStorage/sessionStorage, cookies or identity records. Remove personal key clears it; reload and profile changes also clear it and cancel stale requests. Only syntax is confirmed locally, not provider acceptance. Do not use the optional key to bypass an integration restriction. Raw personal keys are never retained by backend caches or databases; active HTTP processing necessarily receives them. Personal-tier artwork is segregated by an in-memory one-way fingerprint for at most ten minutes, never written to disk or returned to other scopes. Removing a key does not persist a server credential to revoke. Browser memory remains accessible to same-origin scripts and the user's own developer tools.

Supported runtime/dev entrypoints disable raw URL access logs. Request-validation responses retain the fixed SEC-01 projection; provider errors use fixed diagnostics. Operators must separately ensure ingress, request-body capture and telemetry do not record authorization, personal keys, recovery/invitation codes or full confidential URLs.

## Provider policies and attribution

Official references reviewed for this migration:

- Trakt API use policy: https://developer.trakt.tv/docs/api-use-policy (current page dated October 20, 2026). It permits in-app discovery/recommendations and feature-driven caching, including public pages, while prohibiting harvesting, mirroring, redistribution as datasets/feeds, and restriction evasion. It requires a non-endorsement notice. Standard metadata endpoints were verified live with a client ID and no OAuth/client secret. Limited/Premium endpoints are not used. API registrations can be removed after prolonged inactivity or test-only initial use; keep registration/contact status current.
- Trakt authentication/headers: https://developer.trakt.tv/docs/authentication-oauth and https://developer.trakt.tv/docs/required-headers .
- Fanart.tv API: https://api.fanart.tv/ and official client https://github.com/fanart-tv/fanart.tv-api . The live documentation page blocked automated inspection with HTTP 403; indexed official documentation and the official client document v3.2 IMDb lookup, header keys, previews, copyright fields and 429 handling. Project-key requests were verified live. Live personal-tier verification was not performed; synthetic personal keys are intercepted locally in browser tests.
- Fanart.tv image terms: https://fanart.tv/terms-and-conditions/ . Copyright remains with its owners; access is not a copyright transfer or blanket image license. The OpenAPI documentation's license label does not license every film image. Recorded copyright holders/source links are displayed in film details, including honest Unknown values. Verify current API registration terms in the project account before public launch; direct registration/terms pages were blocked from automated inspection here.

Movelle's credits link Trakt and Fanart.tv, give the required Trakt non-endorsement notice, identify the artwork source, and disclaim Fanart.tv endorsement. This project remains a free noncommercial student portfolio: no ads, subscriptions, payments or monetization. Written Fanart.tv consent is required before commercial use. Dataset permission and third-party image rights remain separate from API access. No provider was contacted and no legal permission is inferred from silence.

## Release coordination

Configure these server-side names during a separately authorized Azure rollout, retain the existing Neon database and reference catalogue, and verify the matching frontend's image origin and public API URL. Hold automatic frontend promotion before merge, deploy/verify the backend, then promote the same-SHA Production-target frontend. Old/new image contracts require coordinated promotion; a brief maintenance window may be needed. See DEPLOYMENT.md. Do not merge, modify cloud settings or deploy merely because local tests pass.
