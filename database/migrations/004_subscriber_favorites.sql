CREATE TABLE IF NOT EXISTS subscriber_favorites (
    subscriber_id BIGINT NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
    channel_code TEXT NOT NULL,
    PRIMARY KEY (subscriber_id, channel_code)
);
