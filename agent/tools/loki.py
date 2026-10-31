import httpx
from langchain_core.tools import tool

LOKI_URL = "http://127.0.0.1:3100"

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