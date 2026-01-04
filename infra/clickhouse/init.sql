-- Create database if not exists
CREATE DATABASE IF NOT EXISTS rca;

USE rca;

-- Metrics timeseries table
CREATE TABLE IF NOT EXISTS metrics_timeseries
(
    ts DateTime64(3),
    service LowCardinality(String),
    metric LowCardinality(String),
    value Float64,
    tags Map(String, String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (service, metric, ts)
TTL ts + INTERVAL 90 DAY;

-- Logs table
CREATE TABLE IF NOT EXISTS logs
(
    ts DateTime64(3),
    service LowCardinality(String),
    level LowCardinality(String),
    event LowCardinality(String),
    message String,
    fields Map(String, String),
    trace_id String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (service, level, event, ts)
TTL ts + INTERVAL 90 DAY;

-- Create materialized views for common aggregations (optional, for performance)
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_1m_agg
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (service, metric, ts)
AS SELECT
    toStartOfMinute(ts) as ts,
    service,
    metric,
    avg(value) as avg_value,
    quantile(0.95)(value) as p95_value,
    quantile(0.99)(value) as p99_value,
    count() as count
FROM metrics_timeseries
GROUP BY ts, service, metric;


