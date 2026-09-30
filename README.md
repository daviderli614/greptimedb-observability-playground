# GreptimeDB Observability Playground

English | [简体中文](README.zh-CN.md)

Use the OpenTelemetry Astronomy Shop to generate traffic, with metrics, logs, and traces sent through the otel-collector into an already-deployed external GreptimeDB. This is reduced to a single pipeline: **business services → otel-collector → GreptimeDB**. It does not deploy a local GreptimeDB, Prometheus, node-exporter, Grafana, or Flow.

## Prerequisites

- Docker with Compose, Git, and Python 3.9+
- An already-deployed GreptimeDB reachable over OTLP HTTP (with username/password)

## Run

Start Docker, then run:

```bash
git clone https://github.com/daviderli614/greptimedb-observability-playground.git
cd greptimedb-observability-playground

export GREPTIMEDB_ENDPOINT='http://your-greptime-host:4000/v1/otlp'
export GREPTIMEDB_USERNAME='your-user'
export GREPTIMEDB_PASSWORD='your-password'

python3 demo.py up
```

The first run downloads pinned images. The load generator starts shopping traffic automatically; allow time for telemetry to arrive in the external GreptimeDB.

- [Shop](http://localhost:18080)

Once data is ingested, query it directly with SQL in GreptimeDB:

```sql
SELECT * FROM opentelemetry_traces ORDER BY timestamp DESC LIMIT 10;  -- traces
SELECT * FROM opentelemetry_logs   ORDER BY timestamp DESC LIMIT 10;  -- logs
```

Metrics are also written over the same OTLP pipeline; the exact table name depends on the GreptimeDB version and configuration.

## Try a payment failure

1. In [feature flags](http://localhost:18080/feature), set `paymentFailure` to `100%`. This affects all payment requests in the demo.
2. Check out in the shop, or wait for generated traffic. Checkout returns HTTP 422 with `PAYMENT_FAILED`.
3. Query GreptimeDB for the `payment` service's error logs and spans.
4. Restore `paymentFailure` to `off`, including when stopping the demonstration early. Checkout should succeed again.

## Verify and stop

With the payment failure flag off:

```bash
python3 verify.py
python3 demo.py logs otel-collector
python3 demo.py down
```

The verify script places an order and checks that traces/logs were written to the external GreptimeDB, exiting nonzero on failure. It reads `GREPTIMEDB_ENDPOINT`/`GREPTIMEDB_USERNAME`/`GREPTIMEDB_PASSWORD` from the environment automatically (or override with `--greptime`/`--username`/`--password`). `down` removes this project's containers and does not affect data in the external GreptimeDB.

## Runtime details

- Published ports bind to `127.0.0.1`.
- Request counts include only server spans. Business services report over OTLP to the otel-collector, which then writes to the external GreptimeDB over OTLP HTTP with Basic Auth.
- If GreptimeDB has auth disabled: remove `extensions`, the `auth` block in each exporter, and `service.extensions` from `otelcol-config-greptime.yml`, and drop the username/password variables from `compose.greptime.yaml`.
- The traces `x-greptime-pipeline-name: greptime_trace_v1` header requires a pipeline of the same name in the external GreptimeDB; otherwise remove that header or create the pipeline first.
- The launcher uses the `greptime-demo` Compose project and stores generated files in `.runtime/`. Collector configuration is in [otelcol-config-greptime.yml](otelcol-config-greptime.yml).
