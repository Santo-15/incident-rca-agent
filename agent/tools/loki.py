import math
import os
import httpx
from langchain_core.tools import tool

LOKI_URL = os.getenv("LOKI_URL", "http://127.0.0.1:3100")

@tool
def get_error_counts(minutes: int = 10) -> str:
    """Count shop-api error lines in Loki for the last N minutes (1-30), grouped by error message.
    Use this first to see what errors the shop is returning during an incident."""
    minutes = max(1, min(minutes, 30))              
    query = f'sum by (error) (count_over_time({{service="shop-api"}} |= "request failed" | json [{minutes}m]))'
    resp = httpx.get(f"{LOKI_URL}/loki/api/v1/query", params={"query": query}, timeout=10)  
    resp.raise_for_status()                         
    results = resp.json()["data"]["result"]         
    if not results:
        return f"No shop-api error lines in the last {minutes} minutes."   
    rows = sorted(results, key=lambda r: -float(r["value"][1]))   
    return "\n".join(
        f'{int(float(r["value"][1]))}x  {r["metric"].get("error", "unknown")[:150]}'   
        for r in rows[:10]                          
    )


PATH_ID = 'label_format path=`{{ regexReplaceAll "[0-9]+" .path "{id}" }}`'   # KEY: /users/42/cart -> /users/{id}/cart, so user ids don't explode the series count
ERR_ID = 'label_format error=`{{ regexReplaceAll "[0-9]+" .error "N" }}`'

class LokiLogs:   # LogSource adapter for Grafana Loki
    def __init__(self, url: str = LOKI_URL):
        self.url = url

    def _instant(self, query: str, end: float) -> list[dict]:
        try:
            resp = httpx.get(f"{self.url}/loki/api/v1/query", params={"query": query, "time": int(end * 1e9)}, timeout=10)
        except httpx.TransportError as exc:
            from agent.tools.base import BackendUnavailable
            raise BackendUnavailable(f"loki: {type(exc).__name__}") from exc
        if resp.status_code >= 400:   # CHANGED  KEY: keep Loki's own message (it named the 500-series limit), not just "400 Bad Request"
            raise RuntimeError(f"loki {resp.status_code}: {resp.text[:200]}")
        return resp.json()["data"]["result"]

    @staticmethod
    def _minutes(start: float, end: float) -> int:
        return max(1, min(30, math.ceil((end - start) / 60)))   # KEY: narrow window, capped at 30 min

    def error_groups(self, start: float, end: float) -> list[tuple[str, str, int]]:
        q = ('sum by (path, error) (count_over_time({service="shop-api"} |= "request failed" | json path="path", error="error" | '
             + PATH_ID + " | " + ERR_ID + f" [{self._minutes(start, end)}m]))")
        rows = [(r["metric"].get("path", "?"), r["metric"].get("error", "unknown"), int(float(r["value"][1])))
                for r in self._instant(q, end)]
        return sorted(rows, key=lambda r: -r[2])[:50]   # cap before normalising

    def slow_requests(self, start: float, end: float, min_ms: int = 1000) -> list[tuple[str, int]]:
        q = (f'sum by (path) (count_over_time({{service="shop-api"}} |= "duration_ms" | json path="path", duration_ms="duration_ms" | duration_ms > {min_ms} | '   # CHANGED  KEY: |= "duration_ms" skips lines without that field, so the number filter never sees ""
            + PATH_ID + f" [{self._minutes(start, end)}m]))")
        rows = [(r["metric"].get("path", "?"), int(float(r["value"][1]))) for r in self._instant(q, end)]
        return sorted(rows, key=lambda r: -r[1])[:10]
