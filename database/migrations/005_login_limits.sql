CREATE TABLE IF NOT EXISTS login_rate_limits (
    limit_key TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL CHECK (attempts > 0),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS login_rate_limits_expiry_idx ON login_rate_limits (expires_at);
