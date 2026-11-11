#!/usr/bin/env python3
"""Generates the Grafana dashboard JSON files in grafana/dashboards/.

Dashboards-as-code: edit this file, run `make dashboards`, commit the JSON.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "grafana" / "dashboards"
DS = {"type": "prometheus", "uid": "prometheus"}

GREEN_YELLOW_RED = [(None, "green"), (70, "yellow"), (90, "red")]
RED_GREEN = [(None, "red"), (99, "yellow"), (99.5, "green")]


def steps(pairs):
    return [{"color": c, "value": v} for v, c in pairs]


class Dashboard:
    def __init__(self, uid, title, tags, variables=None, time_from="now-1h"):
        self.uid, self.title, self.tags = uid, title, tags
        self.variables = variables or []
        self.time_from = time_from
        self.panels = []
        self._id = 0

    def _pid(self):
        self._id += 1
        return self._id

    @staticmethod
    def _targets(exprs, **extra):
        out = []
        for i, item in enumerate(exprs):
            expr, legend = item if isinstance(item, tuple) else (item, "")
            out.append({"datasource": DS, "expr": expr, "legendFormat": legend,
                        "refId": chr(65 + i), **extra})
        return out

    def row(self, title, y):
        self.panels.append({"id": self._pid(), "type": "row", "title": title, "collapsed": False,
                            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []})

    def stat(self, title, expr, x, y, w=4, h=4, unit="none", thresholds=None, decimals=None,
             min_=None, max_=None, description=""):
        defaults = {"unit": unit,
                    "thresholds": {"mode": "absolute", "steps": steps(thresholds or [(None, "blue")])}}
        if decimals is not None:
            defaults["decimals"] = decimals
        if min_ is not None:
            defaults["min"] = min_
        if max_ is not None:
            defaults["max"] = max_
        self.panels.append({
            "id": self._pid(), "type": "stat", "title": title, "description": description,
            "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": self._targets([expr]),
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background" if thresholds else "value", "graphMode": "area",
                        "textMode": "auto", "justifyMode": "auto"},
        })

    def timeseries(self, title, exprs, x, y, w=12, h=8, unit="none", stack=False, min_=None,
                   max_=None, threshold_lines=None, description="", fill=10):
        custom = {"lineWidth": 1, "fillOpacity": fill, "showPoints": "never", "spanNulls": True,
                  "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
        defaults = {"unit": unit, "custom": custom,
                    "thresholds": {"mode": "absolute", "steps": steps(threshold_lines or [(None, "green")])}}
        if threshold_lines:
            custom["thresholdsStyle"] = {"mode": "dashed"}
        if min_ is not None:
            defaults["min"] = min_
        if max_ is not None:
            defaults["max"] = max_
        self.panels.append({
            "id": self._pid(), "type": "timeseries", "title": title, "description": description,
            "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": self._targets(exprs),
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}},
        })

    def heatmap(self, title, expr, x, y, w=12, h=8):
        self.panels.append({
            "id": self._pid(), "type": "heatmap", "title": title, "datasource": DS,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{"datasource": DS, "expr": expr, "format": "heatmap",
                         "legendFormat": "{{le}}", "refId": "A"}],
            "fieldConfig": {"defaults": {}, "overrides": []},
            "options": {"calculate": False, "yAxis": {"unit": "s", "axisPlacement": "left"},
                        "color": {"mode": "scheme", "scheme": "Spectral", "fill": "dark-orange",
                                  "scale": "exponential", "steps": 64},
                        "cellGap": 1, "tooltip": {"show": True}, "legend": {"show": True}},
        })

    def table(self, title, expr, x, y, w=12, h=8, hide=(), rename=None, value_mapping=False):
        overrides = []
        if value_mapping:
            overrides.append({"matcher": {"id": "byName", "options": "Status"}, "properties": [
                {"id": "mappings", "value": [{"type": "value", "options": {
                    "0": {"text": "DOWN", "color": "red", "index": 0},
                    "1": {"text": "UP", "color": "green", "index": 1}}}]},
                {"id": "custom.cellOptions", "value": {"type": "color-background"}}]})
        self.panels.append({
            "id": self._pid(), "type": "table", "title": title, "datasource": DS,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{"datasource": DS, "expr": expr, "instant": True, "format": "table", "refId": "A"}],
            "fieldConfig": {"defaults": {}, "overrides": overrides},
            "options": {"showHeader": True, "cellHeight": "sm"},
            "transformations": [{"id": "organize", "options": {
                "excludeByName": {k: True for k in ("Time", "__name__", *hide)},
                "renameByName": rename or {}}}],
        })

    def build(self):
        templating = []
        for name, query in self.variables:
            templating.append({
                "name": name, "label": name, "type": "query", "datasource": DS,
                "query": {"query": query, "refId": f"var_{name}"}, "refresh": 2,
                "includeAll": True, "multi": True, "allValue": ".*",
                "current": {"selected": True, "text": "All", "value": "$__all"},
                "sort": 1})
        return {
            "uid": self.uid, "title": self.title, "tags": self.tags, "schemaVersion": 39, "version": 1,
            "editable": True, "refresh": "10s", "timezone": "browser", "graphTooltip": 1,
            "time": {"from": self.time_from, "to": "now"},
            "templating": {"list": templating}, "annotations": {"list": []},
            "panels": self.panels,
        }

    def write(self):
        path = OUT / f"{self.uid}.json"
        path.write_text(json.dumps(self.build(), indent=2) + "\n")
        print("wrote", path.relative_to(OUT.parent.parent))


FIRING = 'count(ALERTS{alertstate="firing",alertname!="Watchdog"}) or vector(0)'
FS = 'fstype!~"tmpfs|overlay|squashfs|ramfs|fuse.*"'
NET_DEV = 'device!~"lo|veth.*|docker.*|br-.*"'


# =============================================================== 1. Infrastructure
def infrastructure():
    d = Dashboard("infrastructure-overview", "Infrastructure Overview (CPU / Memory / Disk / Network)",
                  ["infrastructure", "node-exporter"], variables=[("instance", "label_values(node_uname_info, instance)")])
    I = 'instance=~"$instance"'
    d.row("Saturation at a glance", 0)
    d.stat("CPU utilisation", f'100 * (1 - avg(rate(node_cpu_seconds_total{{{I},mode="idle"}}[$__rate_interval])))',
           0, 1, unit="percent", thresholds=[(None, "green"), (80, "yellow"), (95, "red")], decimals=1, min_=0, max_=100)
    d.stat("Memory utilisation", f'100 * (1 - sum(node_memory_MemAvailable_bytes{{{I}}}) / sum(node_memory_MemTotal_bytes{{{I}}}))',
           4, 1, unit="percent", thresholds=[(None, "green"), (85, "yellow"), (95, "red")], decimals=1, min_=0, max_=100)
    d.stat("Root disk used", f'max(100 * (1 - node_filesystem_avail_bytes{{{I},mountpoint="/",{FS}}} / node_filesystem_size_bytes{{{I},mountpoint="/",{FS}}}))',
           8, 1, unit="percent", thresholds=[(None, "green"), (75, "yellow"), (90, "red")], decimals=1, min_=0, max_=100)
    d.stat("Load (5m) per core", f'avg(node_load5{{{I}}} / on(instance) count by (instance)(node_cpu_seconds_total{{{I},mode="idle"}}))',
           12, 1, thresholds=[(None, "green"), (1, "yellow"), (1.5, "red")], decimals=2)
    d.stat("Uptime", f'min(time() - node_boot_time_seconds{{{I}}})', 16, 1, unit="s")
    d.stat("Firing alerts", FIRING, 20, 1, thresholds=[(None, "green"), (1, "red")], decimals=0)

    d.row("CPU & Memory", 5)
    d.timeseries("CPU usage by mode", [(f'100 * avg by (mode)(rate(node_cpu_seconds_total{{{I},mode!="idle"}}[$__rate_interval]))', "{{mode}}")],
                 0, 6, unit="percent", stack=True, min_=0, max_=100)
    d.timeseries("Memory", [
        (f'node_memory_MemTotal_bytes{{{I}}} - node_memory_MemAvailable_bytes{{{I}}}', "used"),
        (f'node_memory_Cached_bytes{{{I}}}', "page cache"),
        (f'node_memory_MemAvailable_bytes{{{I}}}', "available"),
        (f'node_memory_SwapTotal_bytes{{{I}}} - node_memory_SwapFree_bytes{{{I}}}', "swap used")],
        12, 6, unit="bytes", min_=0)

    d.row("Disk", 14)
    d.timeseries("Filesystem used %", [(f'100 * (1 - node_filesystem_avail_bytes{{{I},{FS}}} / node_filesystem_size_bytes{{{I},{FS}}})', "{{mountpoint}}")],
                 0, 15, unit="percent", min_=0, max_=100, threshold_lines=[(None, "green"), (85, "red")])
    d.timeseries("Disk I/O throughput", [
        (f'sum by (device)(rate(node_disk_read_bytes_total{{{I}}}[$__rate_interval]))', "{{device}} read"),
        (f'sum by (device)(rate(node_disk_written_bytes_total{{{I}}}[$__rate_interval]))', "{{device}} write")],
        12, 15, unit="Bps", min_=0)

    d.row("Network", 23)
    d.timeseries("Network throughput", [
        (f'sum by (device)(rate(node_network_receive_bytes_total{{{I},{NET_DEV}}}[$__rate_interval]))', "{{device}} rx"),
        (f'sum by (device)(rate(node_network_transmit_bytes_total{{{I},{NET_DEV}}}[$__rate_interval]))', "{{device}} tx")],
        0, 24, unit="Bps", min_=0)
    d.timeseries("Network errors & drops", [
        (f'sum by (device)(rate(node_network_receive_errs_total{{{I},{NET_DEV}}}[$__rate_interval]))', "{{device}} rx errors"),
        (f'sum by (device)(rate(node_network_transmit_errs_total{{{I},{NET_DEV}}}[$__rate_interval]))', "{{device}} tx errors"),
        (f'sum by (device)(rate(node_network_receive_drop_total{{{I},{NET_DEV}}}[$__rate_interval]))', "{{device}} rx drops"),
        (f'sum by (device)(rate(node_network_transmit_drop_total{{{I},{NET_DEV}}}[$__rate_interval]))', "{{device}} tx drops")],
        12, 24, unit="pps", min_=0)

    d.row("System", 32)
    d.timeseries("Load average", [(f'node_load1{{{I}}}', "1m"), (f'node_load5{{{I}}}', "5m"), (f'node_load15{{{I}}}', "15m")], 0, 33, min_=0)
    d.timeseries("File descriptors & context switches", [
        (f'node_filefd_allocated{{{I}}}', "open file descriptors"),
        (f'rate(node_context_switches_total{{{I}}}[$__rate_interval])', "context switches/s")], 12, 33, min_=0)
    return d


# =============================================================== 2. Golden signals
def golden_signals():
    d = Dashboard("service-golden-signals", "Service Reliability (Latency / Traffic / Errors / Saturation)",
                  ["reliability", "sre", "golden-signals"])
    J = 'job="demo-app"'
    d.row("Service level at a glance", 0)
    d.stat("Availability (1h)", f'100 * (1 - (sum(increase(http_requests_total{{{J},status=~"5.."}}[1h])) / sum(increase(http_requests_total{{{J}}}[1h]))))',
           0, 1, unit="percent", thresholds=RED_GREEN, decimals=3, description="SLO target: 99.5%")
    d.stat("Error ratio (5m)", f'job:http_error_ratio:rate5m{{{J}}}', 4, 1, unit="percentunit",
           thresholds=[(None, "green"), (0.02, "yellow"), (0.072, "red")], decimals=2)
    d.stat("p95 latency", f'job:http_request_duration_seconds:p95{{{J}}}', 8, 1, unit="s",
           thresholds=[(None, "green"), (0.3, "yellow"), (0.5, "red")], decimals=3)
    d.stat("Request rate", f'job:http_requests:rate5m{{{J}}}', 12, 1, unit="reqps", decimals=1)
    d.stat("In-flight requests", f'sum(http_requests_in_flight{{{J}}})', 16, 1,
           thresholds=[(None, "green"), (25, "yellow"), (50, "red")], decimals=0)
    d.stat("Firing alerts", FIRING, 20, 1, thresholds=[(None, "green"), (1, "red")], decimals=0)

    d.row("Latency", 5)
    d.timeseries("Latency percentiles", [
        (f'histogram_quantile(0.50, sum by (le)(rate(http_request_duration_seconds_bucket{{{J}}}[$__rate_interval])))', "p50"),
        (f'histogram_quantile(0.95, sum by (le)(rate(http_request_duration_seconds_bucket{{{J}}}[$__rate_interval])))', "p95"),
        (f'histogram_quantile(0.99, sum by (le)(rate(http_request_duration_seconds_bucket{{{J}}}[$__rate_interval])))', "p99")],
        0, 6, unit="s", min_=0, fill=0, threshold_lines=[(None, "green"), (0.5, "red")],
        description="Dashed line = p95 alert threshold (500ms)")
    d.timeseries("p95 latency by endpoint", [
        (f'histogram_quantile(0.95, sum by (le, endpoint)(rate(http_request_duration_seconds_bucket{{{J}}}[$__rate_interval])))', "{{endpoint}}")],
        12, 6, unit="s", min_=0, fill=0)
    d.heatmap("Latency distribution", f'sum by (le)(increase(http_request_duration_seconds_bucket{{{J}}}[$__rate_interval]))', 0, 14)

    d.row("Traffic & Errors", 22)
    d.timeseries("Request rate by endpoint", [(f'sum by (endpoint)(rate(http_requests_total{{{J}}}[$__rate_interval]))', "{{endpoint}}")],
                 0, 23, unit="reqps", stack=True, min_=0)
    d.timeseries("Error ratio (5xx)", [
        (f'sum(rate(http_requests_total{{{J},status=~"5.."}}[$__rate_interval])) / sum(rate(http_requests_total{{{J}}}[$__rate_interval]))', "5xx ratio")],
        12, 23, unit="percentunit", min_=0, threshold_lines=[(None, "green"), (0.02, "yellow"), (0.072, "red")],
        description="Yellow = warning (2%), red = fast error-budget burn (7.2%)")
    d.timeseries("Responses by status code", [(f'sum by (status)(rate(http_requests_total{{{J}}}[$__rate_interval]))', "{{status}}")],
                 0, 31, unit="reqps", stack=True, min_=0)
    d.timeseries("Errors by endpoint", [(f'sum by (endpoint)(rate(http_requests_total{{{J},status=~"5.."}}[$__rate_interval]))', "{{endpoint}}")],
                 12, 31, unit="reqps", min_=0)

    d.row("Saturation", 39)
    d.timeseries("In-flight requests", [(f'sum(http_requests_in_flight{{{J}}})', "in flight")], 0, 40, w=8, min_=0,
                 threshold_lines=[(None, "green"), (50, "red")])
    d.timeseries("Container CPU (cores)", [('sum by (name)(rate(container_cpu_usage_seconds_total{name!=""}[$__rate_interval]))', "{{name}}")],
                 8, 40, w=8, min_=0)
    d.timeseries("Container memory (working set)", [('container_memory_working_set_bytes{name!=""}', "{{name}}")],
                 16, 40, w=8, unit="bytes", min_=0)
    return d


# =============================================================== 3. Alerts & pipeline health
def alerts_overview():
    d = Dashboard("alerts-pipeline-health", "Alerts & Monitoring Pipeline Health", ["alerts", "prometheus", "alertmanager"])
    d.row("Alert state", 0)
    d.stat("Firing", 'count(ALERTS{alertstate="firing",alertname!="Watchdog"}) or vector(0)', 0, 1, thresholds=[(None, "green"), (1, "red")], decimals=0)
    d.stat("Pending", 'count(ALERTS{alertstate="pending"}) or vector(0)', 4, 1, thresholds=[(None, "green"), (1, "yellow")], decimals=0)
    d.stat("Targets up", 'count(up == 1)', 8, 1, thresholds=[(None, "green")], decimals=0)
    d.stat("Targets down", 'count(up == 0) or vector(0)', 12, 1, thresholds=[(None, "green"), (1, "red")], decimals=0)
    d.stat("Watchdog heartbeat", 'sum(ALERTS{alertname="Watchdog",alertstate="firing"}) or vector(0)', 16, 1,
           thresholds=[(None, "red"), (1, "green")], decimals=0, description="1 = alerting pipeline is evaluating rules")
    d.stat("Notifications failed (1h)", 'sum(increase(alertmanager_notifications_failed_total[1h])) or vector(0)', 20, 1,
           thresholds=[(None, "green"), (1, "red")], decimals=0)

    d.table("Active alerts", 'ALERTS{alertname!="Watchdog"}', 0, 5, w=14, h=9,
            hide=("Value", "job", "stack", "environment"),
            rename={"alertname": "Alert", "alertstate": "State", "severity": "Severity", "resource": "Resource", "instance": "Instance"})
    d.table("Scrape targets", 'up', 14, 5, w=10, h=9, hide=("environment", "stack"),
            rename={"Value": "Status", "job": "Job", "instance": "Instance"}, value_mapping=True)

    d.row("Alerts over time", 14)
    d.timeseries("Alerts firing / pending by name", [('count by (alertname, alertstate)(ALERTS{alertname!="Watchdog"})', "{{alertname}} ({{alertstate}})")],
                 0, 15, w=24, h=7, min_=0, stack=True)

    d.row("Prometheus & Alertmanager internals", 22)
    d.timeseries("Samples ingested / s", [('rate(prometheus_tsdb_head_samples_appended_total[$__rate_interval])', "samples/s")], 0, 23, w=8, min_=0)
    d.timeseries("Active series (head)", [('prometheus_tsdb_head_series', "series")], 8, 23, w=8, min_=0)
    d.timeseries("Scrape duration by job", [('avg by (job)(scrape_duration_seconds)', "{{job}}")], 16, 23, w=8, unit="s", min_=0)
    d.timeseries("Rule group evaluation time", [('prometheus_rule_group_last_duration_seconds', "{{rule_group}}")], 0, 31, w=12, unit="s", min_=0)
    d.timeseries("Alertmanager notifications / s", [('sum by (integration)(rate(alertmanager_notifications_total[$__rate_interval]))', "{{integration}} sent"),
                                                    ('sum by (integration)(rate(alertmanager_notifications_failed_total[$__rate_interval]))', "{{integration}} failed")],
                 12, 31, w=12, unit="ops", min_=0)
    return d


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for build in (infrastructure, golden_signals, alerts_overview):
        build().write()
