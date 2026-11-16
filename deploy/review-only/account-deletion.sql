-- NOT APPROVED FOR EXECUTION. Application Neon schema only; never Supabase Auth.
-- No role, grant, credential or automatic migration is created by this artifact.
CREATE TABLE account_deletion_intents (
    request_id UUID PRIMARY KEY,
    subject UUID NOT NULL UNIQUE,
    user_id BIGINT NOT NULL UNIQUE,
    issuer VARCHAR(255) NOT NULL,
    provider_created_at VARCHAR(64) NOT NULL,
    created_at BIGINT NOT NULL,
    authorized_until BIGINT NOT NULL,
    authorization_tag VARCHAR(64) NOT NULL,
    phase VARCHAR(24) NOT NULL CHECK (phase IN ('pending', 'provider_absent', 'complete')),
    worker UUID,
    lease_until BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE account_deletion_events (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    event VARCHAR(24) NOT NULL,
    observed_at BIGINT NOT NULL
);
-- No User foreign key: minimal audit/tombstone survives authorized local erasure.
-- A reviewed migration must verify DDL, grants, dependency inventory, backup,
-- retention and lifecycle-aware all-route policy before permitting submission.
