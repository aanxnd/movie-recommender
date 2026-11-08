# Film providers and artwork setup

Movelle enriches its own MovieLens catalogue with Trakt metadata and Fanart.tv/Trakt artwork. It does not import provider ratings into recommendations, use provider genres for collaborative filtering, change MovieLens IDs, or ask users to sign in to Trakt. No database migration is introduced.

## Backend configuration

| Name | Purpose |
|---|---|
| TRAKT_CLIENT_ID | Trakt application's client ID, sent only as the server's trakt-api-key header. |
| FANART_API_KEY | Fanart.tv project key, sent only as the server's api-key header. |
| MOVELLE_ARTWORK_LINKS | Optional matching MovieLens links.csv with sibling movies.csv, verified against catalogue titles. Overrides matching bundled IMDb entries; other provider ID columns are ignored. |
| MOVELLE_ARTWORK_CACHE_DIR | Optional writable cache root. Metadata uses trakt-fanart-v2; bounded WebP bytes use trakt-images-v1. Without this setting, image bytes use the OS temporary directory plus bounded process memory. |

No TRAKT_CLIENT_SECRET is used: public metadata/people/search GET endpoints need the client ID, not user OAuth. Never put provider keys or a database connection in VITE variables. Vercel retains only its existing public VITE_API_BASE_URL. Image CSP permits Fanart.tv and the exact existing Azure API origin for cached images; other directives are unchanged. No Trakt CDN browser hotlinks are permitted.

Register/inspect applications at https://developer.trakt.tv/ and https://fanart.tv/get-an-api-key/. Keep both developer contacts accurate. The Fanart.tv project owner must personally verify that their account email remains current. No account settings are modified by this implementation.

## Requests and matching

- With catalogue-verified MovieLens links: GET https://api.trakt.tv/movies/{imdb_id}?extended=full, then /shows/{imdb_id} only if the movie is absent. Returned IMDb identity and release year are checked (at most one year's discrepancy for a verified external ID). This supports documentaries and miniseries represented in MovieLens.
- Without links: search movies, then shows when no movie matches, using query=TITLE&extended=full&limit=10. Select a unique normalized title/alternate-title and exact year, then confirm using the corresponding summary endpoint. Ambiguous matches are rejected. Empty non-Latin transliterations never count as a match. Limited search coverage can result in honest missing metadata.
- Movie details: GET /movies/{trakt_id}/people for available directors, only when details are opened. Empty/unsupported credits remain absent.
- Artwork: GET https://webservice.fanart.tv/v3.2/movies/{imdb_id}?source=imdb with api-key and optional client-key headers. Verify response imdb_id exactly. Select one poster and backdrop, deterministically preferring English, then textless artwork, likes, resolution, and stable identifiers. Validate dimensions and URLs. Do not return the raw artwork catalogue.
- For a verified show, use Trakt's positive TVDB ID with Fanart.tv /v3.2/tv/{tvdb_id}; require matching thetvdb_id and use tvposter/showbackground fields. No title-to-TVDB guesses are made.

Overview, release date, runtime and director text are display fields only. Provider text renders through React text nodes, never HTML. Fanart images accept only HTTPS assets.fanart.tv paths, without credentials, traversal, queries or fragments. Documented /preview/ (maximum 200px) and /bigpreview/ (maximum 400px) variants reduce grid downloads; srcset widths account for the actual image aspect ratio. Full backdrops support featured/detail views.

Other provider identifiers are ignored except verified IMDb/TVDB identities. Fanart.tv may return original image credit links pointing to another provider. Credit links are passive attribution, never fetched or used as metadata/image sources. This integration makes no claim about providers' internal data provenance. There is no TMDB runtime client, credential, image origin, cache source or branding dependency. Historical Git commits and upstream MovieLens documentation remain intact.

## Trakt fallback and cached bytes

Cover candidates are ordered: Fanart poster, Trakt poster, Fanart background, Trakt background, then placeholder. The browser advances on image failure, not just missing metadata. Background covers have a visible Film still label and background alt text. Film details credit the source and kind actually displayed; Trakt is not invented as the copyright holder. Backdrops try Fanart then Trakt. The response retains poster_path/backdrop_path for compatibility and adds ordered cover_candidates/backdrop_candidates.

Official https://developer.trakt.tv/docs/images documents images.poster and images.fanart on extended=full summaries, scheme-less HTTPS URLs, WebP (including .jpg.webp/.png.webp), and mandatory application/server caching. Current live movie/show responses were verified to use media.trakt.tv/{movies|shows}/{trakt_id}/medium/{poster|fanart}.webp. Older documented walter-r2.trakt.tv/images/... paths are also accepted. Only these exact hosts and identity-bound path grammars are allowed, never wildcard domains. New formats fail safely until verified.

The browser receives /movies/artwork-image/{canonical_movielens_id}/{poster|backdrop}; it never receives a raw Trakt CDN URL. The endpoint does not accept a URL, external ID, or credentials. DNS results must all be globally routable; the validated destination IP is pinned while TLS verifies the original hostname. Redirects are refused. Downloads require HTTP 200, image/webp, valid bounded RIFF/WebP framing, at most 2 MiB, 2.5-second socket timeouts and a six-second work deadline. No provider credentials are sent to image hosts. Limits are 60 image requests/minute/source and 180 globally, in addition to general admission.

Bytes are fully cached before serving: two downloads/process at once, per-URL singleflight, 24 MiB/128-entry memory and 128 MiB/256-file disk limits. Freshness is seven days; stale outage fallback ends at 30 days. Missing images cool down six hours; transient failures/rate limits cool down at least 30 seconds, honoring bounded Retry-After. Unwritable disk falls back to bounded memory. No startup prefetch or catalogue image harvesting occurs. Responses have image/webp, nosniff, SHA-256 ETags, conditional 304 support and public max-age=86400. Missing images return a fixed 404 with no-store. Caches are disposable across restarts/replicas and may need refetching.

## Reproducible IMDb companion

The production prepared-reference archive deliberately does not include links.csv. Missing MOVELLE_ARTWORK_LINKS forced title matching, which misses alternate titles and shows. app/resources now packages a compressed IMDb-only companion for the existing verified MovieLens 32M catalogue (87,585 IDs), alongside source checksums and the unmodified upstream README/license. No ratings, prepared arrays, catalogues, manifests, archive allowlists, or bootstrap integrity checks are modified. Runtime only enables this companion when the verified prepared catalogue SHA-256 matches exactly, verifies the companion checksum and bounded schema/IDs, and otherwise falls back safely. Small/custom catalogues can still provide title-checked links explicitly.

To regenerate offline from the official matching MovieLens archive (verify the published checksums first):

```powershell
.\.venv\Scripts\python.exe scripts/build_artwork_ids.py --source PATH_TO_EXTRACTED_ML32M --prepared PATH_TO_VERIFIED_PREPARED --output app/resources
```

The builder requires source movies.csv, links.csv and README.txt; checks source movie SHA-256 against the prepared manifest, complete title/ID equality, unique complete link inventory and prepared catalogue SHA-256; writes deterministic gzip and source pins; copies legal text verbatim. It never writes prepared files. See the official dataset README: https://files.grouplens.org/datasets/movielens/ml-32m-README.html and citation https://doi.org/10.1145/2827872 . The companion is a dataset transformation distributed under the same published conditions; noncommercial research/portfolio scope is retained. Revenue-bearing use requires separate faculty permission. Dataset terms do not license film images.

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
- The same API policy explicitly allows displayed images and requires image caching; it does not impose a blanket ban on in-app personalized recommendations. This implementation uses the permitted in-app display scope, not training exports or provider-derived recommendation datasets. No separate TMDB account/API/CDN or TMDB contractual permission is introduced by using Trakt's documented image API. This does not establish ownership of underlying film images or transfer third-party copyrights. Trakt's general user terms could not be independently inspected here (reader HTTP 400, anonymous browser HTTP 403); the accessible API policy states its API-specific scope. Summary/cache guidance: https://developer.trakt.tv/docs/caching-and-fresh-data .
- Trakt authentication/headers: https://developer.trakt.tv/docs/authentication-oauth and https://developer.trakt.tv/docs/required-headers .
- Fanart.tv API: https://api.fanart.tv/ and official client https://github.com/fanart-tv/fanart.tv-api . The live documentation page blocked automated inspection with HTTP 403; indexed official documentation and the official client document v3.2 IMDb lookup, header keys, previews, copyright fields and 429 handling. Project-key requests were verified live. Live personal-tier verification was not performed; synthetic personal keys are intercepted locally in browser tests.
- Fanart.tv image terms: https://fanart.tv/terms-and-conditions/ . Copyright remains with its owners; access is not a copyright transfer or blanket image license. The OpenAPI documentation's license label does not license every film image. Recorded copyright holders/source links are displayed in film details, including honest Unknown values. Verify current API registration terms in the project account before public launch; direct registration/terms pages were blocked from automated inspection here.

Movelle's credits link Trakt and Fanart.tv, give the required Trakt non-endorsement notice, identify the artwork source, and disclaim Fanart.tv endorsement. This project remains a free noncommercial student portfolio: no ads, subscriptions, payments or monetization. Written Fanart.tv consent is required before commercial use. Dataset permission and third-party image rights remain separate from API access. No provider was contacted and no legal permission is inferred from silence.

## Release coordination

For this additive fallback release, the new frontend also accepts the existing Fanart-only response, so verify its Vercel Production deployment before releasing the backend that exposes cached Trakt URLs. Retain the existing provider secrets, public API URL, Neon database and verified reference catalogue. No new cloud configuration is required for the bundled matching companion. Use the existing main-only Controlled production release workflow with its CI, immutable-image smoke, protected environment and stale-main guard; do not bypass approvals. See DEPLOYMENT.md. Releases still require explicit authorization.

## Coverage measurement (November 7, 2026)

The same 24 canonical titles were tested before/after, including popular films, alternate titles, documentaries and six series/miniseries. Their titles match both bundled Small and production's 32M catalogue. Baseline used existing Fanart-only/movie-only code without an external links setting and actual provider responses: 15/24 metadata matches (62.5%), 14/24 usable covers (58.3%). The repaired implementation with the verified companion matched 24/24 and downloaded usable portrait poster bytes for 24/24 (100%): 19 Fanart, five cached Trakt. This is a diagnostic cohort, not estimated full-catalogue coverage. Representative newly covered titles: Paris Is Burning, Harlan County U.S.A., Aelita, The Story of Film and The Civil War. No pre-deployment production POST was used for the baseline. Provider responses and screenshots stay in ignored local QA storage.
