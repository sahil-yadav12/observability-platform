# Infrastructure Observability Platform (Prometheus + Grafana)

A reproducible, Docker Compose–based monitoring stack that tracks **CPU, memory, disk and network**
health, evaluates alerting rules with **Prometheus + Alertmanager**, and visualises the **golden signals
(latency, traffic, errors, saturation)** in **Grafana**. A built-in demo service and failure-injection
commands let you watch the whole detect → alert → notify → resolve loop end to end.

```
                         ┌────────────────┐
 node-exporter ─┐        │  Alertmanager  │──► webhook-logger (stand-in for Slack / email / PagerDuty)
 cAdvisor ──────┼──scrape►  Prometheus ───┤     grouping · routing · inhibition
 demo-app ──────┤        │ rules + alerts │
 (loadgen drives│        └───────┬────────┘
  traffic)      │                │ PromQL
                └────────────────▼
                             Grafana  (3 provisioned dashboards)
```

## Quick start

```bash
cp .env.example .env     # optional: change Grafana credentials
make up                  # docker compose up -d --build
```

| Service      | URL                    | Notes                         |
|--------------|------------------------|-------------------------------|
| Grafana      | http://localhost:3000  | admin / admin                 |
| Prometheus   | http://localhost:9090  | Alerts tab shows rule state   |
| Alertmanager | http://localhost:9093  | Active alerts, silences       |
| Demo app     | http://localhost:8000  | `/metrics`, `/chaos`          |
| Webhook sink | http://localhost:5001  | JSON history of notifications |

Dashboards load automatically into the **Reliability** folder (the home dashboard is *Service Reliability*).
Give Prometheus ~1 minute to collect data.

## What's inside

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Prometheus, Alertmanager, Grafana, node-exporter, cAdvisor, demo-app, loadgen, webhook-logger |
| `prometheus/prometheus.yml` | Scrape jobs, rule files, Alertmanager wiring |
| `prometheus/rules/recording.yml` | Pre-computed utilisation, error ratios (5m/30m/1h/6h), p95/p99 latency |
| `prometheus/rules/alerts.yml` | 22 alerts: availability, host saturation, service SLOs, monitoring self-checks |
| `prometheus/tests/alerts_test.yml` | `promtool` unit tests for the alert rules |
| `alertmanager/alertmanager.yml` | Routing by severity, grouping, inhibition, receivers (Slack/email/PagerDuty examples) |
| `grafana/provisioning/` | Datasources + dashboard provider (no manual setup) |
| `grafana/dashboards/` | Generated dashboard JSON |
| `scripts/generate_dashboards.py` | Dashboards-as-code generator (`make dashboards`) |
| `.github/workflows/validate.yml` | CI: lint configs, run rule tests, ensure dashboards are in sync |

## Dashboards

1. **Service Reliability** – availability vs 99.5% SLO, request rate, error ratio, p50/p95/p99 latency,
   latency heatmap, per-endpoint breakdown, in-flight requests, container CPU/memory.
2. **Infrastructure Overview** – CPU by mode, memory, filesystem usage, disk I/O, network throughput,
   errors/drops, load average. Filter by `$instance`.
3. **Alerts & Pipeline Health** – active alerts, scrape target status, Watchdog heartbeat, notification failures,
   Prometheus ingestion rate, rule evaluation time.

## Alerting design

| Area | Alerts (warning → critical) |
|------|------------------------------|
| Availability | `InstanceDown` |
| CPU | `HostHighCpu` (>80%) → `HostCriticalCpu` (>95%), `HostHighLoad` |
| Memory | `HostHighMemory` (>85%) → `HostCriticalMemory` (>95%), `ContainerHighMemory` |
| Disk | `HostDiskSpaceLow` (<15%) → `HostDiskSpaceCritical` (<5%), `HostDiskWillFillIn24h` (`predict_linear`) |
| Network | `HostNetworkErrors`, `HostNetworkSaturation` |
| Errors | `ServiceHighErrorRate` (>2%) → `ServiceErrorBudgetFastBurn`; `ServiceErrorBudgetSlowBurn` |
| Latency | `ServiceHighLatencyP95` (>500ms) → `ServiceCriticalLatencyP99` (>1s) |
| Saturation / traffic | `ServiceHighConcurrency`, `ServiceNoTraffic` |
| Pipeline | `Watchdog`, `PrometheusNotConnectedToAlertmanager`, `PrometheusRuleEvaluationFailures` |

Design choices worth knowing:

- **Multi-window burn-rate alerts** for the 99.5% SLO (14.4× over 5m+1h, 6× over 30m+6h) page on real
  budget consumption rather than brief blips.
- **Severity routing** – `critical` goes to its own receiver with no `group_wait`; `warning` is batched.
- **Inhibition** – a critical alert suppresses the matching warning (same `resource`/`instance`/`job`), and
  `InstanceDown` suppresses everything else on that instance, so on-call gets one notification, not five.
- **Watchdog** – an always-firing alert routed to `null`; wire an external dead-man's-switch to it in production.
- **`for:` durations are short** so the demo is quick. Lengthen them in real environments.

## Try it: trigger incidents

Open the Service Reliability dashboard and the webhook log (`make alerts`) side by side.

```bash
make demo-errors     # 40% 5xx    → ServiceHighErrorRate → ErrorBudgetFastBurn (critical)
make demo-latency    # +1.2s      → ServiceHighLatencyP95 → ServiceCriticalLatencyP99 (critical)
make demo-reset      # heal; alerts resolve and "RESOLVED" notifications arrive
make demo-outage     # stop app   → InstanceDown (critical); other app alerts are inhibited
make demo-recover
make demo-cpu        # burn CPU   → HostHighCpu after 5m (stop with make demo-cpu-stop)
```

Alert lifecycle: **inactive → pending** (condition true, waiting out `for:`) **→ firing** (sent to Alertmanager)
**→ resolved**. Watch it on http://localhost:9090/alerts.

## Testing & validation

```bash
make validate     # promtool check config + amtool check-config
make test-rules   # promtool unit tests (healthy traffic stays quiet, failures fire correctly)
make reload       # hot-reload Prometheus after editing rules
```

## Sending real notifications

Uncomment a receiver in `alertmanager/alertmanager.yml` (Slack, email, PagerDuty examples included),
point a route at it, then `docker compose restart alertmanager`. Keep secrets in files or env, not in git.

## Platform notes

- **Linux** gives the most accurate host metrics. On **Docker Desktop (Mac/Windows)**, node-exporter and
  cAdvisor report the metrics of Docker's Linux VM, and node-exporter's network panels reflect the
  container's own interface — fine for the demo, not representative of the physical host.
- If cAdvisor fails to start on your platform, remove it from `docker-compose.yml` and its scrape job;
  only the container panels/alert depend on it.
- Prometheus keeps 15 days of data (`--storage.tsdb.retention.time`).

## Possible extensions

Blackbox exporter for HTTP/TCP probes · Loki for logs · Grafana-managed alerts · remote_write to long-term
storage (Thanos/Mimir) · service discovery (file/DNS/Kubernetes) instead of static targets.
