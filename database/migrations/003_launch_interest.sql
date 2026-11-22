CREATE TABLE IF NOT EXISTS launch_interest (
    email TEXT NOT NULL,
    country CHAR(2) NOT NULL CHECK (country IN ('US', 'NG')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (email, country)
);
