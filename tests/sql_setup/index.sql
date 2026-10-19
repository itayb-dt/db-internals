\ir _orders.sql
CREATE TABLE docs (id serial PRIMARY KEY, tags text[]);
CREATE TABLE events (id serial PRIMARY KEY, created_at timestamptz);
INSERT INTO events (created_at) SELECT now() - g * interval '1 minute' FROM generate_series(1, 5000) g;
ANALYZE events;
