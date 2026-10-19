CREATE TABLE sessions (id serial PRIMARY KEY, token text);
INSERT INTO sessions (token) SELECT md5(g::text) FROM generate_series(1, 5000) g;
ANALYZE sessions;
