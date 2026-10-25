CREATE TABLE events (id serial PRIMARY KEY, created_at timestamptz NOT NULL, payload text);
INSERT INTO events (created_at, payload) SELECT now() - interval '30 days' + g * interval '10 seconds', 'x' FROM generate_series(1, 20000) g;
ANALYZE events;
CREATE INDEX events_created_brin ON events USING brin (created_at);
