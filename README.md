# GreptimeDB Observability Playground

English | [简体中文](README.zh-CN.md)

Use the OpenTelemetry Astronomy Shop to generate traffic and send telemetry into an already-deployed external GreptimeDB through three pipelines:

- **business services → otel-collector → GreptimeDB** (metrics/logs/traces over OTLP HTTP)
- **node-exporter → prometheus → GreptimeDB** (host metrics via Prometheus remote write)
- **init-flows → GreptimeDB** (creates the streaming Flow over SQL)

It does not deploy a local GreptimeDB or Grafana. Prometheus and node-exporter run locally and write into the external GreptimeDB.

## Prerequisites

- Docker with Compose, Git, and Python 3.9+
- An already-deployed GreptimeDB reachable over OTLP HTTP and the Prometheus write endpoint (with username/password)

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
SELECT * FROM node_cpu_seconds_total ORDER BY greptime_timestamp DESC LIMIT 10;  -- host metrics
SELECT * FROM service_error_rate_1m ORDER BY time_window DESC LIMIT 10;          -- flow output
```

Business metrics are also written over the OTLP pipeline; the exact table name depends on the GreptimeDB version and configuration. The `node-exporter → prometheus → GreptimeDB` pipeline stores each Prometheus metric as a table of the same name.

## Try a payment failure

1. In [feature flags](http://localhost:18080/feature), set `paymentFailure` to `100%`. This affects all payment requests in the demo.
2. Check out in the shop, or wait for generated traffic. Checkout returns HTTP 422 with `PAYMENT_FAILED`.
3. Query GreptimeDB for the `payment` service's error logs and spans.
4. Restore `paymentFailure` to `off`, including when stopping the demonstration early. Checkout should succeed again.

## Verify and stop

With the payment failure flag off:

```bash
python3 verify.py
python3 demo.py logs otel-collector init-flows prometheus
python3 demo.py down
```

The verify script places an order and checks that traces/logs, host metrics, and Flow output were written to the external GreptimeDB, exiting nonzero on failure. It reads `GREPTIMEDB_ENDPOINT`/`GREPTIMEDB_USERNAME`/`GREPTIMEDB_PASSWORD` from the environment automatically (or override with `--greptime`/`--username`/`--password`). `down` removes this project's containers and does not affect data in the external GreptimeDB.

## Runtime details

- Published ports bind to `127.0.0.1`; node_exporter uses host networking on port 9100 instead.
- Prometheus scrapes node_exporter and remote-writes host metrics into GreptimeDB with Basic Auth, keeping its local TSDB for only 2 hours. Its config is rendered into `.runtime/prometheus.yml` from the `GREPTIMEDB_*` environment variables.
- Request counts include only server spans. Business services report over OTLP to the otel-collector, which then writes to the external GreptimeDB over OTLP HTTP with Basic Auth.
- `init-flows` creates the `service_error_rate_1m` Flow via SQL; it waits for the first trace before running `CREATE FLOW`.
- If GreptimeDB has auth disabled: remove `extensions`, the `auth` block in each exporter, and `service.extensions` from `otelcol-config-greptime.yml`, and drop the username/password variables from `compose.greptime.yaml`.
- The traces `x-greptime-pipeline-name: greptime_trace_v1` header requires a pipeline of the same name in the external GreptimeDB; otherwise remove that header or create the pipeline first.
- The launcher uses the `greptime-demo` Compose project and stores generated files in `.runtime/`. Collector configuration is in [otelcol-config-greptime.yml](otelcol-config-greptime.yml); the Prometheus template is in [prometheus.yml](prometheus.yml).
