"""Load profile for Pelargonium Shop (Locust).

Buyers browse the catalog (most traffic) and open variety cards; the health check is polled by monitoring.
Orders are not created here: they change stock and would distort the catalog for the next run.

    locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8010 --csv dist/load

Target (docs/testing/test-strategy.md): p95 < 800 ms and 0% errors at 50 simultaneous users.
"""
import random

from locust import HttpUser, between, task

FILTERS = ["", "?type=rosebud", "?color=pink&color=white", "?in_stock=true", "?sort=price_asc", "?q=lord"]


class Buyer(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.ids = [v["id"] for v in self.client.get("/api/varieties").json()]

    @task(6)
    def browse_catalog(self):
        self.client.get("/api/varieties" + random.choice(FILTERS), name="/api/varieties?[filters]")

    @task(3)
    def open_variety(self):
        self.client.get(f"/api/varieties/{random.choice(self.ids)}", name="/api/varieties/[id]")

    @task(1)
    def health(self):
        self.client.get("/api/health")
