# triage: turn the Alertmanager payload into fired/silent alerts and the evidence time window. No LLM: it's pure parsing.
import time
from agent.state import RCAState
from agent.timeutil import hms, parse_iso

ALL_ALERTS = ["ShopApiDown", "PostgresDown", "RedisDown", "ShopHigh5xxRatio",
              "ShopHighLatency", "ShopApiHighMemory", "ShopApiRestarted"]
LOOKBACK_S = 10 * 60      # logs/metrics start 10 min before the first alert
MAX_AFTER_S = 15 * 60     # and stop 15 min after it (or now, if sooner)


def _is_firing(alert: dict) -> bool:
    status = alert.get("status")
    state = status.get("state") if isinstance(status, dict) else status   # /api/v2/alerts: {"state": "active"}; webhook: "firing"
    return state in ("firing", "active")


def triage(state: RCAState) -> dict:
    now = time.time()
    fired = [a for a in state.get("payload", {}).get("alerts", []) if _is_firing(a)]
    lines, names, starts = {}, set(), []
    for a in sorted(fired, key=lambda a: parse_iso(a["startsAt"])):
        labels = a.get("labels", {})
        name = labels.get("alertname", "unknown")
        ts = parse_iso(a["startsAt"])
        key = f"{name}{{path={labels['path']}}}" if "path" in labels else name   # ShopHighLatency fires once per path
        lines.setdefault(key, f"{key} since {hms(ts)}")   # dedupe, keep the earliest
        names.add(name)
        starts.append(ts)
    first = min(starts) if starts else now
    return {
        "alerts": list(lines.values()),
        "silent": [n for n in ALL_ALERTS if n not in names],   # KEY: silent alerts are evidence too (playbook step 1)
        "first_alert": first,
        "window_start": first - LOOKBACK_S,
        "window_end": min(now, first + MAX_AFTER_S),   # KEY: narrow window, also works when re-running an old incident
        "loop_count": 0,
    }
