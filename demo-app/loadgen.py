"""Generates steady, slightly random traffic against the demo app."""
import os
import random
import threading
import time

import requests

TARGET = os.getenv("TARGET", "http://demo-app:8000")
RPS = float(os.getenv("RPS", "10"))
WORKERS = int(os.getenv("WORKERS", "8"))
ENDPOINTS = ["/api/users", "/api/orders", "/api/checkout"]
WEIGHTS = [5, 3, 2]


def wait_for_target():
    while True:
        try:
            requests.get(f"{TARGET}/healthz", timeout=2)
            return
        except requests.RequestException:
            print("waiting for target...", flush=True)
            time.sleep(2)


def worker():
    session = requests.Session()
    per_worker_rate = RPS / WORKERS
    while True:
        endpoint = random.choices(ENDPOINTS, weights=WEIGHTS)[0]
        try:
            session.get(TARGET + endpoint, timeout=10)
        except requests.RequestException:
            pass
        time.sleep(random.expovariate(per_worker_rate))


if __name__ == "__main__":
    wait_for_target()
    print(f"sending ~{RPS} req/s to {TARGET}", flush=True)
    for _ in range(WORKERS):
        threading.Thread(target=worker, daemon=True).start()
    while True:
        time.sleep(3600)
