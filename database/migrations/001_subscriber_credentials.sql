CREATE TABLE IF NOT EXISTS subscriber_credentials (
    subscriber_id BIGINT PRIMARY KEY
        REFERENCES subscribers(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL
);
