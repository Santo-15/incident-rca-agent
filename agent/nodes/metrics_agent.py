# metrics_agent: z-score of each signal (incident window vs baseline before it). Plain Python, no LLM.
import logging
import statistics
from agent.schemas import Finding
from agent.state import RCAState
from agent.timeutil import hms
from agent.tools.base import BackendUnavailable, get_metrics

logger = logging.getLogger("agent.metrics")
BASELINE_S = 10 * 60   # baseline = the 10 min before onset
ONSET_S = 5 * 60       # onset = 5 min before the first alert (alerts fire after the problem starts)
Z_ABNORMAL = 3.0
MAX_FINDINGS = 12

SIGNALS = [   # KEY: (name, PromQL, min_std) — the playbook's "is it up / which paths / deeper metrics" checks
    ("shop_api_up", 'up{job="shop-api"}', 0.1),
    ("pg_up", "pg_up", 0.1),
    ("redis_up", "redis_up", 0.1),
    ("5xx_rate_by_path", 'sum by (path) (rate(http_requests_total{job="shop-api", status=~"5.."}[1m]))', 0.05),
    ("p95_by_path", 'histogram_quantile(0.95, sum by (le, path) (rate(http_request_duration_seconds_bucket{job="shop-api", path!~"/health|/metrics|unmatched"}[1m])))', 0.1),
    ("rss_mib", 'process_resident_memory_bytes{job="shop-api"} / 1048576', 5),
    ("restarts", 'changes(process_start_time_seconds{job="shop-api"}[5m])', 0.2),
    ("seq_tup_read_products", 'rate(pg_stat_user_tables_seq_tup_read{relname="products"}[1m])', 100),
    ("pg_connections_by_state", "sum by (state) (pg_stat_activity_count)", 1),
    ("pg_longest_tx_s", "max(pg_stat_activity_max_tx_duration)", 5),                   
    ("pg_exclusive_locks", 'sum(pg_locks_count{mode="accessexclusivelock"})', 0.2),
    ("pg_exporter_up", 'up{job="postgres"}', 0.1),
    ("redis_exporter_up", 'up{job="redis"}', 0.1),
]


def zscore(points: list[tuple[float, float]], onset: float, min_std: float) -> dict | None:
    base = [v for t, v in points if t < onset]
    after = [(t, v) for t, v in points if t >= onset]
    if not after:
        return None
    mean = statistics.fmean(base) if base else 0.0   # no baseline = series didn't exist before (e.g. the first 5xx)
    std = max(statistics.pstdev(base) if len(base) > 1 else 0.0, min_std)   # KEY: std floor; a flat baseline (pg_up always 1) would divide by 0
    scored = [(t, v, (v - mean) / std) for t, v in after]
    peak = max(scored, key=lambda x: abs(x[2]))
    first = next((t for t, _, z in scored if abs(z) >= Z_ABNORMAL), None)   # KEY: when it went abnormal: shows which path broke first
    return {"mean": mean, "peak": peak[1], "z": peak[2], "first": first, "last": after[-1][1]}


def _labels(metric: dict) -> str:
    keep = [f"{k}={metric[k]}" for k in ("path", "state") if k in metric]
    return "{" + ",".join(keep) + "}" if keep else ""


def metrics_agent(state: RCAState) -> dict:
    onset = state["first_alert"] - ONSET_S
    metrics = get_metrics()
    abnormal, normal, failed = [], [], []
    for name, promql, min_std in SIGNALS:
        try:
            series = metrics.range_query(promql, onset - BASELINE_S, state["window_end"])
        except BackendUnavailable as exc:   # backend down: stop, don't wait on 9 timeouts
            logger.warning("metrics unavailable: %s", exc)
            failed = ["all (" + str(exc) + ")"]
            break
        except Exception as exc:   # one bad query: skip just that signal
            failed.append(f"{name} ({type(exc).__name__})")
            continue
        for metric, points in series:
            r = zscore(points, onset, min_std)
            if r is None:
                continue
            label = name + _labels(metric)
            if abs(r["z"]) >= Z_ABNORMAL:
                abnormal.append((label, r))
            else:
                normal.append(f"{label}={r['last']:.3g}")

    findings = []
    for label, r in sorted(abnormal, key=lambda x: -abs(x[1]["z"]))[:MAX_FINDINGS]:
        z = abs(r["z"])
        findings.append(Finding(
            source="metrics", signal=label, severity="high" if z >= 10 else "medium" if z >= 5 else "low",
            detail=f"baseline {r['mean']:.3g} -> peak {r['peak']:.3g} (z={r['z']:+.1f}), "
                   f"abnormal from {hms(r['first'])}, latest {r['last']:.3g}"))
    if normal:   # KEY: normal signals are evidence too (e.g. pg_up=1 rules out postgres_down)
        findings.append(Finding(source="metrics", signal="normal signals", detail=", ".join(normal[:15]), severity="low"))
    if failed:
        findings.append(Finding(source="metrics", signal="metrics unavailable", detail=", ".join(failed), severity="low"))
    return {"findings": findings}
