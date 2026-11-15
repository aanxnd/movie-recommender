# Native frontend — separate, dormant release artifact

`npm run build:native` explicitly selects `src/native-main.jsx` → `NativeApp`.
The normal build/main.jsx and deployed legacy application remain unchanged.
Use the reviewed backend manifest plus exact `api_origin` and the public
`MOVELLE_NATIVE_PUBLISHABLE_KEY`. Preview/production origins are still unapproved;
no wildcard or guessed deployment URL is supplied. Build/runtime pins must agree
with browser origin, Supabase project and backend origin. Only public pins/key
are compiled; database fields are excluded. Never use a service-role key.

The release composition reuses one SDK/session controller, PKCE callback scrubbing,
cinematic account screens, themes and native movie/group adapters. Anonymous reads
remain public; profile/ratings/recommendations/invitations/settings use backend
policy and numeric ownership. The operator staging bar and test providers are not
imported. Username PATCH uses a server revision and credential/abort fencing;
conflicts request an explicit recheck, while uncertain writes are never replayed.
Settings do not implement destructive deletion or bypass restricted MFA actions.

Offline SDK/transport and artifact checks are not hosted acceptance. Before any
release approve exact frontend/API origins, root `frontend_origin + '/'` in
Supabase redirects, CA$0 hosting, schema-4 migration and the separate native backend
command. Promote `dist-native` only through a separately reviewed release; do not
replace Vercel's normal build or use the private preview gate as public auth.
Revert only to a reviewed native/schema-compatible artifact. Existing hosted budget
is exhausted; no email/factor/account mutation or deployment occurred here.
