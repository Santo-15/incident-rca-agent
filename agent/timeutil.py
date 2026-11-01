# Time helpers shared by nodes: Alertmanager timestamps -> unix seconds, unix seconds -> readable UTC
import re
from datetime import datetime, timezone


def parse_iso(s: str) -> float:
    s = re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00")   # Alertmanager sends nanoseconds; Python parses up to 6 digits
    return datetime.fromisoformat(s).timestamp()


def hms(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S UTC")
