# GreptimeDB Observability Playground

[English](README.md) | 简体中文

运行 OpenTelemetry Astronomy Shop，将 traces、logs、应用指标和 Linux 主机指标写入同一个 GreptimeDB。Grafana 提供四个大盘，每个大盘均有英文和简体中文版，支持按服务筛选、日志搜索和 trace 下钻。

## 启动

需要 Docker、Docker Compose、Git 和 Python 3.11。Docker 必须处于运行状态，首次启动需要下载应用和观测组件的镜像。

```bash
git clone https://github.com/killme2008/greptimedb-observability-playground.git
cd greptimedb-observability-playground
python3.11 demo.py up
```

启动脚本使用固定的上游提交和 `images.lock.json` 中的镜像摘要。上游代码保存在 `.runtime/opentelemetry-demo`，合并后的 Compose 配置保存在 `.runtime/compose.json`。容器和网络使用独立的 `greptime-demo` 项目名，Compose 发布的端口绑定到 `127.0.0.1`。node_exporter 使用 host 网络，在 Linux Docker host 的 9100 端口监听，不受该端口绑定限制。

| 入口 | 地址 |
| --- | --- |
| 商店 | http://localhost:18080 |
| Grafana Overview | http://localhost:13000/d/astronomy-shop-greptimedb |
| Services | http://localhost:13000/d/astronomy-services |
| Logs & traces | http://localhost:13000/d/astronomy-logs-traces |
| Host metrics | http://localhost:13000/d/astronomy-host |
| 故障开关 | http://localhost:18080/feature |
| GreptimeDB Dashboard | http://localhost:24000/dashboard |
| MySQL | `mysql -h 127.0.0.1 -P 24002 public` |

Grafana 启用了匿名 Admin 访问，不需要登录。负载生成器自动产生购物流量。首次启动后，Flow 每 30 秒计算一次；主机速率图需要至少两个采样点。

```bash
# 查看容器状态
python3.11 demo.py ps

# 查看指定服务的最近 100 行日志
python3.11 demo.py logs otel-collector init-flows

# 停止并移除本项目容器，保留 GreptimeDB 数据卷
python3.11 demo.py down
```

## 大盘

大盘顶部的 **简体中文** / **English** 链接切换语言，并保留时间范围和筛选条件。默认显示英文。[打开中文概览](http://localhost:13000/d/astronomy-shop-greptimedb-zh)。面板标题和说明提供翻译；服务名、指标名、SQL 字段和遥测数据值保持原文。

| 大盘 | 内容 |
| --- | --- |
| Overview | Server 请求量、错误率、P95、服务列表、采集状态、数据新鲜度 |
| Services | 每分钟请求量、P50/P95/P99、操作排行、慢请求、client/server 耗时对照 |
| Logs & traces | 按服务、级别、文本搜索日志；按 Trace ID 查看瀑布图和 span 明细 |
| Host metrics | CPU 总量与各核、内存、负载、运行时间、文件系统、磁盘吞吐与繁忙度、网络流量与丢包 |

大盘顶部链接保留时间范围和筛选变量。Overview 中的服务名链接到 Services，慢请求和跨服务调用表中的 Trace ID 链接到 Logs & traces。日志面板下方的 **Log trace links** 表也提供 Trace ID 链接。瀑布图和 span 明细按 Trace ID 查询全部已存储的 spans，不受大盘时间范围限制；Trace ID 为空时不加载。日志仍受时间范围及其他筛选条件限制。

请求量和错误率只统计 `SPAN_KIND_SERVER`，错误定义为 `STATUS_CODE_ERROR`。延迟分位数为近似分位数。Flow 中当前分钟的计数尚未完整。没有日志的 trace，其关联日志列表为空。

日志级别按 OTLP `severity_number` 分组，兼容各 SDK 的 `info`、`INFO`、`Information` 等文本。未指定级别的日志显示为 `UNSPECIFIED`。

Overview 的 **Unified SQL · requests, logs, host** 面板使用一条 SQL，按分钟关联 trace Flow 的请求及错误计数、应用日志计数和 node_exporter 的主机可用内存。三类数据先分别聚合，再联表；同一分钟的主机指标属于整个 VM，不表示与某个服务错误存在因果关系。

macOS 上的 node_exporter 采集 Docker / OrbStack Linux VM 的指标，不采集 macOS 本身。容器内存面板包含同一 Docker host 上的所有项目，不随服务筛选变化。

## 支付故障演示

1. 打开 Overview，时间范围设为最近 15 分钟，Service 选择 `payment`。检查请求量、错误率和 Unified SQL 面板。
2. 打开故障开关页面，将 `paymentFailure` 设为 `100%`。选择后自动保存。
3. 在商店添加商品并结账，或等待负载生成器发起结账请求。支付失败时，结账接口返回 HTTP 422 和 `PAYMENT_FAILED`。
4. 打开 Services，在 **Recent requests · errors first** 表中选择支付服务的错误请求，点击 Trace ID。
5. 在 Logs & traces 查看 `checkout` → `payment` 调用及错误 span。Level 选择 `WARN`，Log text 输入 `Invalid token`，查看同一 Trace ID 的支付失败日志。该业务失败由支付服务记录为 warning。
6. 回到故障开关页面，将 `paymentFailure` 恢复为 `off`，重新结账。订单应创建成功。Flow 每 30 秒更新一次；错误率在后续分钟恢复，故障分钟的历史记录保留。

演示结束或中途停止时，恢复 `paymentFailure = off`。该开关影响当前 demo 的所有支付请求。

## 验证

服务启动并产生流量后执行：

```bash
python3.11 verify.py \
  --shop http://localhost:18080 \
  --grafana http://localhost:13000 \
  --greptime http://localhost:24000
```

验证包含商店及商品、汇率、推荐、广告接口，一次模拟下单及其 quote span 入库，Grafana 数据源，三个 scrape target，近期 server spans、应用日志、主机指标、Flow 输出、中英文共 80 个数据面板的全部查询、跨 SDK 的 INFO 日志筛选，以及时间范围外的完整 trace 和空 Trace ID 查询。查询报错、没有数据、下单失败或 scrape target 不可用时返回非零退出码。执行前应关闭支付故障开关。验证通过应用接口产生购物流量，不直接向遥测表写入测试数据。

## 数据接入

| 数据 | 路径 | 表 |
| --- | --- | --- |
| 应用 traces | SDK → Collector → OTLP HTTP，`greptime_trace_v1` | `opentelemetry_traces`，TTL 7d |
| 应用 logs | SDK → Collector → OTLP HTTP | `opentelemetry_logs` |
| 应用与容器指标 | Collector：OTLP、docker_stats、Redis、PostgreSQL、NGINX、HTTP check、span_metrics → OTLP HTTP | 每个指标一张表 |
| 主机指标 | node_exporter → Prometheus → remote write | `node_*` |
| Ad 的 Prometheus 指标 | Ad `/metrics` → Prometheus → remote write | 对应 Prometheus 指标表 |
| GreptimeDB 自身指标 | GreptimeDB `/metrics` → Prometheus → remote write | `greptime_*` 等 |
| 每分钟请求与错误数 | Flow 连续聚合 server spans | `service_error_rate_1m` |

Prometheus 本地保留 2 小时数据；Grafana 的 PromQL 数据源查询 GreptimeDB。SQL、logs 和 traces 面板使用 GreptimeDB 插件。日志服务名来自 `resource_attributes` 中的 `service.name`，业务面板限定 `service.namespace = opentelemetry-demo`。

Collector 的 `host_metrics` 和 `prometheus/ad` receiver 不在启用的 pipeline 中。Prometheus 格式的 scrape 指标统一通过 remote write 写入。

## 故障排查

- **镜像下载失败**：检查报错中的镜像仓库和 Docker daemon 的代理配置，再运行 `python3.11 demo.py up`。只修改 shell 的代理变量不会必然改变 Docker daemon 的代理。
- **端口已占用**：检查 13000、18080、18081 和 24000–24003 的监听进程。启动脚本不停止其他项目的服务。
- **业务面板为空**：检查 `load-generator`、`frontend-proxy` 和 `otel-collector` 日志，并运行 `verify.py`。主机面板有数据不代表应用遥测已接入。
- **Flow 初始化失败**：检查 `init-flows` 日志及 `opentelemetry_traces` 表。初始化脚本等待 trace 表的业务 namespace 列后创建 Flow，SQL 失败会使容器以非零状态退出。
- **指标导出报时间类型冲突**：检查是否把同名 Prometheus scrape 指标同时通过 OTLP 和 remote write 写入。此配置将 Ad scrape 统一交给 Prometheus。
- **Trace 导出出现 `Partial success response`**：检查 Collector 日志中的 `dropped_spans`。该响应表示部分数据已丢失，不能按完整写入处理。本配置通过 `transform/http_body_sizes` 修正 PHP quote SDK 的 HTTP body size 属性：数字字符串转为整数，未知长度的空字符串作为缺失值。未修正时，空字符串与其他 SDK 创建的整数列冲突，会导致整条 span 被拒收。
