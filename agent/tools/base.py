# Interfaces the agents code against. Loki/Prometheus are one adapter each; a Datadog/ELK adapter would be another.
import os
from typing import Protocol

Series = tuple[dict[str, str], list[tuple[float, float]]]   # (labels, [(unix_ts, value), ...])


class BackendUnavailable(Exception):   # KEY: adapters raise this when the backend can't be reached, so nodes stop early instead of waiting on every timeout
    pass


class LogSource(Protocol):   # KEY: any log backend must offer these two methods
    def error_groups(self, start: float, end: float) -> list[tuple[str, str, int]]: ...   # [(path, error, count)]
    def slow_requests(self, start: float, end: float, min_ms: int = 1000) -> list[tuple[str, int]]: ...   # [(path, count)]


class MetricSource(Protocol):   # KEY: any metrics backend must offer a range query
    def range_query(self, promql: str, start: float, end: float, step: int = 15) -> list[Series]: ...


def get_logs() -> LogSource:
    backend = os.getenv("LOGS_BACKEND", "loki")   # KEY: pick the adapter by config, not by code change
    if backend == "loki":
        from agent.tools.loki import LokiLogs
        return LokiLogs()
    raise ValueError(f"unknown LOGS_BACKEND: {backend}")


def get_metrics() -> MetricSource:
    backend = os.getenv("METRICS_BACKEND", "prometheus")
    if backend == "prometheus":
        from agent.tools.prometheus import PrometheusMetrics
        return PrometheusMetrics()
    raise ValueError(f"unknown METRICS_BACKEND: {backend}")
