CREATE TABLE IF NOT EXISTS subscriber_sessions (
    token_hash BYTEA PRIMARY KEY,
    subscriber_id BIGINT NOT NULL
        REFERENCES subscribers(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
