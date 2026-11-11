"""Tiny instrumented web service used as the monitored workload.

Exposes the RED metrics (Rate, Errors, Duration) plus an in-flight gauge
(saturation) and a /chaos endpoint to inject errors/latency on demand.
"""
import os
import random
import time

from flask import Flask, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

app = Flask(__name__)

REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
IN_FLIGHT = Gauge("http_requests_in_flight", "Requests currently being processed")

chaos = {
    "error_rate": float(os.getenv("BASE_ERROR_RATE", "0.01")),
    "extra_latency": 0.0,
}
BASE_ERROR_RATE = chaos["error_rate"]

IGNORED = {"/metrics", "/healthz"}


@app.before_request
def start_timer():
    if request.path in IGNORED:
        return
    g.start = time.perf_counter()
    g.tracked = True
    IN_FLIGHT.inc()


@app.after_request
def record_metrics(response):
    if getattr(g, "tracked", False):
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        LATENCY.labels(endpoint).observe(time.perf_counter() - g.start)
        REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    return response


@app.teardown_request
def finish(_exc):
    if getattr(g, "tracked", False):
        IN_FLIGHT.dec()
        g.tracked = False


def simulate(low, high, error_multiplier=1.0):
    time.sleep(random.uniform(low, high) + chaos["extra_latency"])
    if random.random() < chaos["error_rate"] * error_multiplier:
        return jsonify(error="simulated failure"), 500
    return jsonify(status="ok")


@app.get("/")
def index():
    return jsonify(service="demo-app", endpoints=["/api/users", "/api/orders", "/api/checkout"])


@app.get("/api/users")
def users():
    return simulate(0.005, 0.05)


@app.get("/api/orders")
def orders():
    return simulate(0.01, 0.15)


@app.get("/api/checkout")
def checkout():
    return simulate(0.05, 0.30, error_multiplier=2.0)


@app.get("/chaos")
def set_chaos():
    """/chaos?error_rate=0.4&latency=1.2  -> inject failures / delay."""
    if "error_rate" in request.args:
        chaos["error_rate"] = min(max(float(request.args["error_rate"]), 0.0), 1.0)
    if "latency" in request.args:
        chaos["extra_latency"] = max(float(request.args["latency"]), 0.0)
    return jsonify(chaos)


@app.get("/chaos/reset")
def reset_chaos():
    chaos.update(error_rate=BASE_ERROR_RATE, extra_latency=0.0)
    return jsonify(chaos)


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
