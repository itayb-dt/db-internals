CREATE TABLE sessions (id serial PRIMARY KEY, token text);
INSERT INTO sessions (token) SELECT md5(g::text) FROM generate_series(1, 5000) g;
ANALYZE sessions;
CREATE INDEX sessions_token_hash ON sessions USING hash (token);
CREATE INDEX sessions_token_btree ON sessions (token);
