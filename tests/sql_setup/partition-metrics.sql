-- the events table from the partitioning article, with data and one query run per partition
CREATE TABLE events (
    id         bigint GENERATED ALWAYS AS IDENTITY,
    created_at timestamptz NOT NULL,
    user_id    bigint,
    payload    text,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE TABLE events_2026_02 PARTITION OF events FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE events_2026_03 PARTITION OF events FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE INDEX events_created_idx ON events (created_at);
INSERT INTO events (created_at, user_id, payload)
SELECT timestamptz '2026-02-01' + (g % 55) * interval '1 day', g % 1000, repeat('x', 100)
FROM generate_series(1, 30000) g;
ANALYZE events;
SELECT count(*) FROM events WHERE user_id = 7;
