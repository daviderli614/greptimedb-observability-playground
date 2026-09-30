# GreptimeDB Observability Playground

[English](README.md) | 简体中文

使用 OpenTelemetry Astronomy Shop 产生流量，将 metrics、logs 和 traces 通过 otel-collector 写入「已部署好的外部 GreptimeDB」。当前精简为一条链路：**业务服务 → otel-collector → GreptimeDB**，不部署本地 GreptimeDB、Prometheus、node-exporter、Grafana 和 Flow。

## 前置条件

- Docker（含 Compose）、Git 和 Python 3.9+
- 一个已部署、可通过 OTLP HTTP 访问的 GreptimeDB 实例（需用户名/密码）

## 运行

启动 Docker 后执行：

```bash
git clone https://github.com/daviderli614/greptimedb-observability-playground.git
cd greptimedb-observability-playground

export GREPTIMEDB_ENDPOINT='http://你的GreptimeDB地址:4000/v1/otlp'
export GREPTIMEDB_USERNAME='用户名'
export GREPTIMEDB_PASSWORD='密码'

python3 demo.py up
```

首次运行会下载固定版本的镜像。负载生成器自动产生购物流量，遥测数据需要一段时间写入外部 GreptimeDB。

- [商店](http://localhost:18080)

写入后可直接在 GreptimeDB 中用 SQL 查询：

```sql
SELECT * FROM opentelemetry_traces ORDER BY timestamp DESC LIMIT 10;  -- traces
SELECT * FROM opentelemetry_logs   ORDER BY timestamp DESC LIMIT 10;  -- logs
```

metrics 也通过同一 OTLP 链路写入，具体表名取决于 GreptimeDB 版本与配置。

## 演示支付故障

1. 在[故障开关](http://localhost:18080/feature)中将 `paymentFailure` 设为 `100%`。该开关影响 demo 的所有支付请求。
2. 在商店结账，或等待自动流量。结账接口返回 HTTP 422 和 `PAYMENT_FAILED`。
3. 在 GreptimeDB 中查询 `payment` 服务对应的错误日志与 span。
4. 将 `paymentFailure` 恢复为 `off`，确认结账成功。中途停止演示时也需关闭该开关。

## 验证与停止

关闭支付故障开关后执行：

```bash
python3 verify.py
python3 demo.py logs otel-collector
python3 demo.py down
```

验证脚本会下一单，并检查 traces/logs 是否写入外部 GreptimeDB，失败时返回非零退出码。它会自动读取 `GREPTIMEDB_ENDPOINT`/`GREPTIMEDB_USERNAME`/`GREPTIMEDB_PASSWORD` 环境变量（也可用 `--greptime`/`--username`/`--password` 覆盖）。`down` 移除本项目容器，不影响外部 GreptimeDB 中的数据。

## 运行说明

- 发布端口绑定 `127.0.0.1`。
- 请求量只统计 server spans。业务服务统一通过 OTLP 上报到 otel-collector，再经 OTLP HTTP（Basic Auth）写入外部 GreptimeDB。
- 若 GreptimeDB 未开启认证：删除 `otelcol-config-greptime.yml` 中的 `extensions`、各 exporter 的 `auth` 以及 `service.extensions`，并去掉 `compose.greptime.yaml` 里的用户名/密码变量。
- traces 的 `x-greptime-pipeline-name: greptime_trace_v1` 需要外部 GreptimeDB 存在同名 pipeline；否则去掉该 header 或先创建 pipeline。
- 启动脚本使用 `greptime-demo` Compose 项目，生成文件保存在 `.runtime/`。Collector 配置见 [otelcol-config-greptime.yml](otelcol-config-greptime.yml)。
