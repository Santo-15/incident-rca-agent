# MetricSource adapter for Prometheus: range queries over the HTTP API
import math
import os
import httpx
from agent.tools.base import BackendUnavailable, Series

PROM_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090")


class PrometheusMetrics:
    def __init__(self, url: str = PROM_URL):
        self.url = url

    def range_query(self, promql: str, start: float, end: float, step: int = 15) -> list[Series]:
        try:
            resp = httpx.get(f"{self.url}/api/v1/query_range",
                             params={"query": promql, "start": start, "end": end, "step": step}, timeout=10)
        except httpx.TransportError as exc:
            raise BackendUnavailable(f"prometheus: {type(exc).__name__}") from exc
        resp.raise_for_status()
        out = []
        for s in resp.json()["data"]["result"]:
            points = [(float(t), float(v)) for t, v in s["values"] if math.isfinite(float(v))]   # KEY: drop NaN (histogram_quantile with no traffic)
            out.append((s["metric"], points))
        return out
