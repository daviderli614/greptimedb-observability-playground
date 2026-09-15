# GreptimeDB Observability Playground

English | [简体中文](README.zh-CN.md)

Run the OpenTelemetry Astronomy Shop with traces, logs, application metrics, and Linux host metrics stored in one GreptimeDB instance. Four Grafana dashboards, each available in English and Simplified Chinese, provide service filters, log search, and trace drill-down.

## Start

Requires Docker, Docker Compose, Git, and Python 3.11. Docker must be running. The first start downloads application and observability images.

```bash
git clone https://github.com/killme2008/greptimedb-observability-playground.git
cd greptimedb-observability-playground
python3.11 demo.py up
```

The launcher uses a pinned upstream commit and image digests from `images.lock.json`. It stores upstream source in `.runtime/opentelemetry-demo` and the rendered Compose configuration in `.runtime/compose.json`. Containers and networks use the separate `greptime-demo` project name. Compose publishes ports on `127.0.0.1`. node_exporter uses host networking and listens on port 9100 of the Linux Docker host; that binding restriction does not apply to node_exporter.

| Entry | Address |
| --- | --- |
| Shop | http://localhost:18080 |
| Grafana Overview | http://localhost:13000/d/astronomy-shop-greptimedb |
| Services | http://localhost:13000/d/astronomy-services |
| Logs & traces | http://localhost:13000/d/astronomy-logs-traces |
| Host metrics | http://localhost:13000/d/astronomy-host |
| Feature flags | http://localhost:18080/feature |
| GreptimeDB Dashboard | http://localhost:24000/dashboard |
| MySQL | `mysql -h 127.0.0.1 -P 24002 public` |

Grafana allows anonymous Admin access without login. The load generator produces shopping traffic automatically. Flow evaluates every 30 seconds; host rate charts require at least two samples after startup.

```bash
# Show container status
python3.11 demo.py ps

# Show the last 100 log lines for selected services
python3.11 demo.py logs otel-collector init-flows

# Remove this project's containers and retain the GreptimeDB volume
python3.11 demo.py down
```

## Dashboards

Use **简体中文** or **English** in dashboard navigation to switch languages while preserving the time range and filters. English is the default. [Open the Chinese overview](http://localhost:13000/d/astronomy-shop-greptimedb-zh). Panel titles and descriptions are translated; service names, metric names, SQL fields, and telemetry values retain their original names.

| Dashboard | Contents |
| --- | --- |
| Overview | Server requests, error rate, P95, services, scrape status, and data freshness |
| Services | Requests per minute, P50/P95/P99, operations, slow requests, and client/server duration comparison |
| Logs & traces | Log filters by service, severity, and text; trace waterfall and span details by trace ID |
| Host metrics | Total and per-core CPU, memory, load, uptime, filesystems, disk throughput and utilization, and network traffic and drops |

Dashboard navigation links preserve the time range and filter variables. Service names in Overview link to Services. Trace IDs in request and cross-service call tables link to Logs & traces. The **Log trace links** table also provides trace ID links. The waterfall and span details load all stored spans for the selected trace ID, independently of the dashboard time range. An empty trace ID loads no spans. Logs remain subject to the time range and other filters.

Request counts and error rates include only `SPAN_KIND_SERVER`; errors are spans with `STATUS_CODE_ERROR`. Latency percentiles are approximate. Flow counts for the current minute are incomplete. Traces without logs have an empty correlated log list.

Log severity uses OTLP `severity_number`, accommodating SDK text values such as `info`, `INFO`, and `Information`. Logs without a severity number appear as `UNSPECIFIED`.

The **Unified SQL · requests, logs, host** panel in Overview uses one SQL query to join per-minute request and error counts from the trace Flow, application log counts, and available host memory from node_exporter. Each source is aggregated before joining. Host metrics describe the entire VM and do not establish a causal relationship with a service error.

On macOS, node_exporter measures the Docker / OrbStack Linux VM, not macOS itself. The container memory panel includes all projects on the same Docker host and does not change with the service filter.

## Demonstrate a payment failure

1. Open Overview, set the time range to the last 15 minutes, and select `payment` in **Service**. Check requests, error rate, and the Unified SQL panel.
2. Open the feature flags page and set `paymentFailure` to `100%`. The selection saves automatically.
3. Add a product to the cart and check out, or wait for the load generator to submit an order. Payment failures return HTTP 422 with `PAYMENT_FAILED` from the checkout API.
4. In Services, select a failed payment request in **Recent requests · errors first** and click its trace ID.
5. In Logs & traces, inspect the `checkout` → `payment` call and error span. Set **Level** to `WARN` and **Log text** to `Invalid token` to find payment failure logs for the same trace ID. The payment service logs this business failure as a warning.
6. On the feature flags page, restore `paymentFailure` to `off` and check out again. An order should be created. Flow updates every 30 seconds; the error rate recovers in subsequent minutes, while records from the failure period remain.

Restore `paymentFailure = off` when the demonstration ends or is interrupted. This flag affects all payment requests in this demo.

## Verify

After startup and telemetry ingestion, run:

```bash
python3.11 verify.py \
  --shop http://localhost:18080 \
  --grafana http://localhost:13000 \
  --greptime http://localhost:24000
```

Verification covers the shop and product, currency, recommendation, and ad APIs; a simulated checkout and its ingested quote span; Grafana data sources; three scrape targets; recent server spans, application logs, host metrics, and Flow output; all queries in 80 data panels across both languages; INFO log filtering across SDKs; and complete-trace and empty-ID queries outside the dashboard time range. Query errors, missing data, failed checkout, or unavailable scrape targets produce a nonzero exit code. Disable the payment failure flag before running verification. The script generates traffic through application APIs and does not insert test data directly into telemetry tables.

## Ingestion

| Data | Path | Tables |
| --- | --- | --- |
| Application traces | SDK → Collector → OTLP HTTP, `greptime_trace_v1` | `opentelemetry_traces`, TTL 7d |
| Application logs | SDK → Collector → OTLP HTTP | `opentelemetry_logs` |
| Application and container metrics | Collector: OTLP, docker_stats, Redis, PostgreSQL, NGINX, HTTP check, span_metrics → OTLP HTTP | One table per metric |
| Host metrics | node_exporter → Prometheus → remote write | `node_*` |
| Ad Prometheus metrics | Ad `/metrics` → Prometheus → remote write | Corresponding metric tables |
| GreptimeDB metrics | GreptimeDB `/metrics` → Prometheus → remote write | `greptime_*` and other metric tables |
| Requests and errors per minute | Flow continuously aggregates server spans | `service_error_rate_1m` |

Prometheus retains two hours of local data. Grafana's PromQL data source queries GreptimeDB. SQL, logs, and traces panels use the GreptimeDB plugin. Log service names come from `service.name` in `resource_attributes`. Business panels filter on `service.namespace = opentelemetry-demo`.

The Collector's `host_metrics` and `prometheus/ad` receivers are not enabled in its pipelines. Prometheus scrape metrics use remote write.

## Troubleshooting

- **Image download failure:** Check the registry reported in the error and the Docker daemon's proxy configuration, then run `python3.11 demo.py up` again. Changing shell proxy variables does not necessarily change the daemon's proxy.
- **Port already in use:** Check listeners on 13000, 18080, 18081, and 24000–24003. The launcher does not stop other projects' services.
- **Empty business panels:** Check `load-generator`, `frontend-proxy`, and `otel-collector` logs, then run `verify.py`. Host metrics alone do not establish that application telemetry is flowing.
- **Flow initialization failure:** Check `init-flows` logs and the `opentelemetry_traces` table. The initialization script waits for the trace table's business namespace column before creating the Flow. SQL failure makes the container exit with a nonzero status.
- **Metric timestamp type conflict:** Check whether the same Prometheus scrape metric is being ingested through both OTLP and remote write. This configuration delegates Ad scraping to Prometheus.
- **Trace export reports `Partial success response`:** Check `dropped_spans` in Collector logs. This response indicates lost data. The `transform/http_body_sizes` processor normalizes HTTP body size attributes from the PHP quote SDK: numeric strings become integers, and empty strings for unknown lengths become missing attributes. Without normalization, empty strings conflict with integer columns created by other SDKs and cause entire spans to be rejected.
