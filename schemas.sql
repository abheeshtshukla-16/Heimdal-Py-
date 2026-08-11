CREATE TABLE clients (
    user_id     SERIAL PRIMARY KEY,
    hashed_key  TEXT UNIQUE NOT NULL,
    quota_limit INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0
);