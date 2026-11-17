# Streamlit UI for the RCA agent: one-screen live view of a break and its investigation. Reads the API only; never runs the agent itself.
import html
import json
import os
import re
import time
from datetime import datetime

import httpx
import streamlit as st

API = os.getenv("RCA_API_URL", "http://127.0.0.1:8001")             # KEY: one setting; the cloud deploy changes this, not the code

st.set_page_config(page_title="Incident RCA Agent", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {--bg:#0b1220; --card:#111a2b; --line:#22304a; --ink:#e8eef7; --mute:#94a3b8; --green:#22c55e; --amber:#f5b83d; --red:#ef4444; --blue:#3b82f6;}
html, body, .stApp, .stMarkdown, p, li, button, input {font-family:'Inter',sans-serif !important;}
.stApp {background:var(--bg);}
[data-testid="stSelectbox"] * {font-size:1.08rem !important;}
div[class*="st-key-n_"] button p {font-size:1.08rem !important; font-weight:600 !important;}
div[class*="st-key-n_"][class*="_memory"] button p {font-size:1rem !important;}
.st-key-brk button p, .st-key-rst button p {font-size:1.1rem !important; font-weight:700 !important;}
.st-key-evb button p, .st-key-repb button p, .st-key-rawb button p {font-size:1.05rem !important; font-weight:600 !important;}
div[class*="st-key-ev_"] button p {font-size:1rem !important;}
header[data-testid="stHeader"] {background:transparent;}
.block-container {padding:1rem 2.5rem 2rem; max-width:100% !important;}
.topl {display:flex; align-items:center; gap:.5rem; font-size:1.05rem; color:var(--ink); padding-top:.6rem;}
.dot {width:10px; height:10px; border-radius:50%; background:var(--green); box-shadow:0 0 10px var(--green);}
.dot.off {background:var(--red); box-shadow:0 0 10px var(--red);}
.title {text-align:center;}
.title h1 {font-size:2.3rem; font-weight:800; color:var(--ink); margin:0 !important; padding:0 !important; line-height:1.15; letter-spacing:-.02em;}
.title h1 a, .title [data-testid="stHeaderActionElements"] {display:none !important;}
.title p {color:var(--mute); font-size:1.1rem; margin:.15rem 0 0 !important; padding:0 !important;}
.timer {text-align:right; padding-top:.5rem;}
.pill {display:inline-block; font-size:1.05rem; font-weight:600; padding:.4rem .9rem; border-radius:999px; border:1px solid var(--line); color:var(--ink); background:var(--card);}
.pill.wait {border-color:rgba(245,184,61,.5); color:var(--amber);}
.pill.live {border-color:rgba(239,68,68,.5); color:#fca5a5;}
.pill.ok {border-color:rgba(34,197,94,.45); color:#86efac;}
.sec {font-size:.95rem; font-weight:700; color:var(--mute); text-transform:uppercase; letter-spacing:.14em; margin:2rem 0 .8rem;}
.pick {font-size:.9rem; color:var(--mute); text-align:right; white-space:nowrap;}
.left {text-align:center; color:var(--mute); font-size:1rem; margin-top:.3rem;}
.st-key-brk button {background:var(--red) !important; border:0 !important; color:#fff !important; font-weight:700 !important; font-size:1.05rem !important; padding:.65rem 0 !important;}
.st-key-brk button:disabled {background:#3b2430 !important; color:#8b6b75 !important;}
.st-key-rst button {background:var(--card) !important; border:1px solid var(--line) !important; color:var(--ink) !important; font-weight:600 !important; font-size:1.05rem !important; padding:.65rem 0 !important;}
.st-key-rst button:disabled {color:#4b5a70 !important;}
.track {display:flex; align-items:flex-start; margin:.4rem 0 .2rem;}
.stop {display:flex; flex-direction:column; align-items:center; width:150px; min-width:150px;}
.ball {width:22px; height:22px; border-radius:50%; border:3px solid #33415a; background:var(--bg);}
.stop.done .ball {background:var(--green); border-color:var(--green); box-shadow:0 0 12px rgba(34,197,94,.6);}
.stop.now .ball {border-color:var(--amber); animation:pulse 1.2s ease-in-out infinite;}
.stop .nm {margin-top:.55rem; font-size:1.05rem; color:var(--mute); text-align:center;}
.stop.done .nm, .stop.now .nm {color:var(--ink); font-weight:600;}
.seg {flex:1; display:flex; flex-direction:column; align-items:center; padding-top:9px;}
.seg .bar {height:4px; width:100%; background:#22304a; border-radius:2px;}
.seg.done .bar {background:var(--green);}
.seg .dur {font-size:1rem; color:var(--mute); margin-top:.45rem;}
@keyframes pulse {0%,100% {box-shadow:0 0 0 rgba(245,184,61,0);} 50% {box-shadow:0 0 16px rgba(245,184,61,.8);}}
.arrow {text-align:center; color:#4b5a70; font-size:1.5rem;}
.arrow.main {margin-top:-2.6rem;}
.par {font-size:.9rem; color:var(--mute); text-align:center; letter-spacing:.08em; text-transform:uppercase; margin-bottom:.2rem;}
.model {text-align:center; font-size:.9rem; color:#a5b4fc; margin:-.35rem 0 .35rem; min-height:1.4rem;}
.gap {height:7.4rem;}
.note {text-align:center; font-size:.9rem; color:var(--mute); margin-top:-.2rem;}
div[class*="st-key-n_"] button {width:100%; min-height:3.4rem; border-radius:12px !important; font-weight:600 !important; font-size:1.08rem !important; transition:all .2s;}
div[class*="st-key-n_todo_"] button {border:1.5px solid rgba(245,184,61,.55) !important; background:rgba(245,184,61,.07) !important; color:#fde68a !important;}
div[class*="st-key-n_run_"] button {border:1.5px solid var(--amber) !important; background:rgba(245,184,61,.15) !important; color:#fde68a !important; animation:pulse 1.2s ease-in-out infinite;}
div[class*="st-key-n_done_"] button {border:1.5px solid rgba(34,197,94,.7) !important; background:rgba(34,197,94,.12) !important; color:#dcfce7 !important;}
div[class*="st-key-n_idle_"] button {border:1.5px solid var(--line) !important; background:var(--card) !important; color:var(--ink) !important;}
div[class*="_sel_"] button {box-shadow:0 0 0 3px var(--blue) !important;}
div[class*="st-key-n_"][class*="_memory"] button {border-style:dashed !important; min-height:2.8rem; font-size:1rem !important;}
.box {background:var(--card); border:1px solid var(--line); border-radius:14px; padding:1.1rem 1.3rem; margin-top:1rem;}
.box h4 {margin:0 0 .5rem; font-size:1.2rem; color:var(--ink);}
.box .what {color:var(--mute); font-size:1.02rem; margin-bottom:.6rem;}
.box ul {margin:0; padding-left:1.2rem;} .box li {color:var(--ink); font-size:1.08rem; line-height:1.6;}
.box li small {color:var(--mute);}
.banner {border-radius:14px; padding:1rem 1.3rem; margin-top:.6rem; font-size:1.12rem; border:1px solid var(--line); background:var(--card); color:var(--ink); text-align:center;}
.banner.wait {border-color:rgba(245,184,61,.45);} .banner.bad {border-color:rgba(239,68,68,.5);}
.verdict {display:grid; grid-template-columns:1.1fr 1.5fr 1.4fr; gap:1.6rem; background:var(--card); border:1px solid rgba(34,197,94,.45); border-radius:16px; padding:1.4rem 1.6rem;}
.verdict .k {font-size:.88rem; color:var(--mute); text-transform:uppercase; letter-spacing:.12em; margin-bottom:.35rem;}
.verdict .cause {font-size:1.75rem; font-weight:800; color:var(--green); line-height:1.25;}
.verdict .code {font-size:.92rem; color:var(--mute); margin-top:.35rem;}
.verdict .conf {display:inline-block; margin-top:.6rem; font-size:.88rem; font-weight:700; padding:.2rem .6rem; border-radius:6px; background:rgba(34,197,94,.12); color:var(--green); text-transform:uppercase; letter-spacing:.06em;}
.verdict .conf.medium {background:rgba(245,184,61,.12); color:var(--amber);} .verdict .conf.low {background:rgba(239,68,68,.12); color:#fca5a5;}
.verdict .sum {font-size:1.1rem; color:var(--ink); line-height:1.6;}
.verdict ul {margin:0; padding-left:1.1rem;} .verdict li {color:var(--ink); font-size:1.05rem; line-height:1.55; margin-bottom:.3rem;}
.verdict .meta {font-size:1rem; color:var(--mute); margin-top:.8rem;}
.st-key-evb button, .st-key-repb button, .st-key-rawb button {background:var(--card) !important; border:1px solid var(--line) !important; color:var(--ink) !important; font-weight:600 !important; font-size:1.05rem !important; padding:.7rem 0 !important;}
div[class*="st-key-ev_"] button {font-size:1rem !important; background:transparent !important; border:1px solid var(--line) !important; color:var(--mute) !important;}
div[class*="st-key-ev_on_"] button {border-color:var(--blue) !important; color:var(--ink) !important; background:rgba(59,130,246,.12) !important;}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)


def show(h: str):
    st.markdown(h, unsafe_allow_html=True)                            # KEY: HTML must be one line; indented lines would render as a code block


def esc(x) -> str:
    return html.escape(str(x))                                        # KEY: log text can contain < > & quotes; never inject it raw


def api_get(path: str):
    try:
        r = httpx.get(f"{API}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return None


def api_post(path: str) -> tuple[bool, str]:
    try:
        r = httpx.post(f"{API}{path}", timeout=10)
        body = r.json()
        return r.is_success, body.get("detail") or body.get("action", "")
    except httpx.HTTPError as exc:
        return False, str(exc)


def ts(s):                                                            # ISO time from the API -> seconds since 1970 (None stays None)
    return datetime.fromisoformat(s).timestamp() if s else None


def dur(sec: float) -> str:                                           # 95 -> "1m 35s"
    sec = max(0, int(round(sec)))
    return f"{sec // 60}m {sec % 60}s" if sec >= 60 else f"{sec}s"


# ---------- plain-language dictionaries (what a CEO can read) ----------
FAILURE = {  # KEY: scenario id -> what the visitor is choosing to break
    "bad_pool_config": "Bad release: database connection limit cut to 1", "kill_db": "Database crashes",
    "memory_leak": "Bad release: memory leak", "redis_down": "Cart storage (Redis) crashes",
    "postgres_hang": "Database freezes", "redis_hang": "Cart storage (Redis) freezes",
    "shop_api_down": "Shop service stops", "db_lock": "A database table gets locked",
    "redis_oom": "Cart storage runs out of memory", "wrong_service_address": "Bad release: wrong cart-storage address",
    "code_exception": "Bad release: bug in checkout code", "slow_query": "A database query becomes slow",
}
CAUSE = {  # root-cause label -> plain words
    "db_pool_exhausted": "Database connection limit too small", "postgres_down": "The database is down",
    "redis_down": "Cart storage (Redis) is down", "memory_leak": "Memory leak in the shop",
    "slow_query": "A slow database query", "shop_api_down": "The shop service is down",
    "db_lock": "A locked database table", "redis_out_of_memory": "Cart storage is full",
    "wrong_service_address": "The shop points to the wrong address", "code_exception": "A bug in newly released code",
    "insufficient_evidence": "Not enough evidence", "other": "Another cause",
}
ALERT = {  # Prometheus alert -> what the alarm means
    "ShopApiDown": "the shop stopped responding", "PostgresDown": "the database went down", "RedisDown": "cart storage went down",
    "ShopHigh5xxRatio": "more than 5% of customer requests started failing", "ShopHighLatency": "pages became slow",
    "ShopApiHighMemory": "the shop is using too much memory", "ShopApiRestarted": "the shop crashed and restarted",
}
METRIC = {  # abnormal metric -> plain sentence ({area} = which part of the shop)
    "shop_api_up": "The shop stopped answering", "pg_up": "The database went down", "redis_up": "Cart storage went down",
    "pg_exporter_up": "The database stopped answering health checks", "redis_exporter_up": "Cart storage stopped answering health checks",
    "p95_by_path": "Responses became slow on {area}", "5xx_rate_by_path": "Requests started failing on {area}",
    "rss_mib": "The shop's memory use jumped", "restarts": "The shop crashed and restarted",
    "pg_connections_by_state": "Database connections changed sharply", "pg_longest_tx_s": "A database operation ran far too long",
    "pg_exclusive_locks": "Database tables got locked", "seq_tup_read_products": "The database started scanning whole tables",
}
NORMAL = {"pg_up": "database", "redis_up": "cart storage", "shop_api_up": "shop", "rss_mib": "memory", "restarts": "restarts",
          "p95_by_path": "speed", "5xx_rate_by_path": "errors", "pg_connections_by_state": "DB connections",
          "pg_exporter_up": "database checks", "redis_exporter_up": "cart storage checks", "pg_longest_tx_s": "DB operations",
          "pg_exclusive_locks": "DB locks", "seq_tup_read_products": "table scans"}
AREA = {"checkout": "checkout", "cart": "the cart", "products": "the product list", "health": "health checks"}

NODES = {  # graph node -> (name, model if it uses an LLM, what it does)
    "triage": ("Triage", None, "Reads the alarms and works out when the problem started."),
    "logs_agent": ("Logs analyst", "gpt-oss-20b", "Searches the shop's logs for errors and groups them."),
    "metrics_agent": ("Metrics analyst", None, "Compares about 10 health numbers with their normal values."),
    "deploy_agent": ("Deploy inspector", None, "Checks whether a new version was released just before the problem."),
    "diff_agent": ("Code-diff reader", "gpt-oss-20b", "Reads what that release changed in the code and settings."),
    "memory": ("Past incidents", None, "Looks up similar incidents from the past."),
    "correlator": ("Root-cause reasoner", "gpt-oss-120b", "Weighs all the evidence and names one root cause."),
    "critic": ("Critic", "gpt-oss-120b", "Double-checks the answer; can send it back for a rethink."),
    "reporter": ("Reporter", None, "Writes the incident report with the fix."),
}
NEEDS = {"triage": [], "logs_agent": ["triage"], "metrics_agent": ["triage"], "deploy_agent": ["triage"], "diff_agent": ["deploy_agent"],
         "correlator": ["logs_agent", "metrics_agent", "diff_agent"], "memory": ["logs_agent", "metrics_agent", "diff_agent"],
         "critic": ["correlator"], "reporter": ["critic"]}   # KEY: graph edges; a node can run once everything it needs is done


def area(path: str) -> str:                                           # "/users/{user_id}/checkout" -> "checkout"
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    return AREA.get(parts[-1], parts[-1]) if parts else "the shop"


def say_log(f: dict) -> str:
    sig, d = f["signal"], f["detail"]
    if sig == "no error logs":
        return "No errors in the shop's logs"
    if sig == "logs unavailable":
        return "The logs could not be read"
    if sig.startswith("slow requests"):
        return "Some requests took more than 1 second"
    m = re.match(r"^(\d+)x on ([^:]+): (.*)$", d)                     # KEY: "538x on /users/{user_id}/checkout: KeyError: 'N'"
    if m:
        n, paths, err = m.groups()
        kind = re.match(r"^(\w+(?:Error|Exception))\b", err)
        what = kind.group(1) if kind else " ".join(err.split()[:6])
        return f"{what} in {area(paths.split(',')[0].strip())} · {n} failed requests"
    return sig[:1].upper() + sig[1:]


def say_metric(f: dict) -> str:
    sig, d = f["signal"], f["detail"]
    if sig == "normal signals":
        names = []
        for part in d.split(","):
            n = NORMAL.get(re.split(r"[{=]", part.strip())[0])
            if n and n not in names:
                names.append(n)
        return "Normal: " + ", ".join(names) if names else "Other health numbers were normal"
    if sig == "metrics unavailable":
        return "Some health numbers could not be read"
    m = re.match(r"^(\w+)(?:\{\w+=(.+)\})?$", sig)
    base, label = (m.group(1), m.group(2)) if m else (sig, None)
    text = METRIC.get(base, base)
    return text.replace("{area}", area(label) if label else "the shop")


def say_deploy(f: dict) -> str:
    sig, d = f["signal"], f["detail"]
    if sig == "no recent deploy":
        return "No new version was released before the problem, which points to an infrastructure issue"
    if sig == "deploys unavailable":
        return "The release history could not be read"
    m = re.search(r"deployed at (\S+), ([\d.]+) min (before|after) the first alert", d)
    if m:
        return f"A new version went live at {m.group(1)} UTC, {m.group(2)} min {m.group(3)} the problem started"
    return d


def say_diff(f: dict) -> tuple[str, str]:                             # (plain line, small technical line)
    sig = f["signal"]
    if sig == "no shop changes":
        return "The release did not change the shop's code or settings", ""
    if sig == "diff unavailable":
        return "The code change could not be read", ""
    if sig == "changed files":
        return "The release changed some files, none clearly risky", ""
    return "The release changed: " + sig.split(": ", 1)[-1], f["detail"]


SAY = {"logs": say_log, "metrics": say_metric, "deploys": say_deploy}


def evidence(inc: dict, source: str) -> list[tuple[str, str]]:        # plain lines for one evidence tab, most important first
    rank = {"high": 0, "medium": 1, "low": 2}
    rows = sorted((f for f in inc.get("findings") or [] if f["source"] == source), key=lambda f: rank.get(f["severity"], 3))
    out = []
    for f in rows:
        line = say_diff(f) if source == "diff" else (SAY[source](f), "")
        if line[0] not in [o[0] for o in out]:
            out.append(line)
    return out


def node_lines(node: str, inc: dict) -> list[tuple[str, str]]:       # what one agent found, in plain words
    trace = inc.get("trace") or []
    if node == "triage":
        fired = [a.get("labels", {}).get("alertname") for a in (inc.get("payload") or {}).get("alerts", [])]
        fired = [ALERT.get(a, a) for a in dict.fromkeys(fired) if a]
        e = next((e for e in trace if e["node"] == "triage"), {})
        quiet = re.search(r"(\d+) known alerts silent", e.get("text", ""))
        out = [(f"{len(fired)} alarm(s) went off: " + "; ".join(fired), "")] if fired else []
        if quiet:
            out.append((f"{quiet.group(1)} other alarms stayed quiet, which helps rule out other causes", ""))
        return out
    if node == "logs_agent":
        return evidence(inc, "logs")
    if node == "metrics_agent":
        return evidence(inc, "metrics")
    if node == "deploy_agent":
        return evidence(inc, "deploys")
    if node == "diff_agent":
        return evidence(inc, "diff") or [("No release to read", "")]
    if node == "memory":
        e = next((e for e in trace if e["node"] == "memory"), None)
        hits = re.findall(r"→ (\w+) \(distance", e["text"]) if e else []
        return [(f"This looks like a past incident: {CAUSE.get(hits[0], hits[0]).lower()}", "")] if hits else [("No similar past incident", "")]
    if node == "correlator":
        tries = inc.get("hypotheses") or []
        h = inc.get("hypothesis") or {}
        out = []
        if len(tries) > 1 and tries[0].get("cause") != tries[-1].get("cause"):
            out.append((f"First guess was {CAUSE.get(tries[0]['cause'], tries[0]['cause']).lower()}, then changed its mind after the critic's feedback", ""))
        out.append((f"Concluded: {CAUSE.get(h.get('cause'), h.get('cause'))} ({h.get('confidence')} confidence)", ""))
        return out
    if node == "critic":
        verdicts = [str(e["text"]).replace("verdict → ", "") for e in trace if e["node"] == "critic"]
        if any(not v.startswith("ok") for v in verdicts):
            return [("Rejected the first answer as weak and asked for a rethink, then approved the revised one", "")]
        return [("Checked the conclusion against the evidence and approved it", "")]
    if node == "reporter":
        return [("Wrote the incident report with the recommended fix (see Full incident report below)", "")]
    return []



# ---------- data ----------
health = api_get("/health")
chaos = api_get("/chaos") or {}
incidents = api_get("/incidents") or []
inc = api_get(f"/incidents/{incidents[0]['id']}") if incidents else None    # KEY: the screen follows the latest incident only

broke_at = ts(chaos.get("started"))
running = chaos.get("running")
new_break = bool(broke_at and (not inc or ts(inc["received_at"]) < broke_at))   # KEY: a break newer than the latest incident = its alarm hasn't arrived yet
if new_break:
    inc = None                                                        # don't show the previous incident while the new break is live
status = inc["status"] if inc else ("breaking" if new_break and running else "missed" if new_break else "idle")


def signature(chaos: dict, incidents: list, inc: dict | None) -> str:  # anything that should redraw the whole page
    top = incidents[0] if incidents else {}
    return json.dumps([chaos.get("running"), chaos.get("started"), chaos.get("cooldown_left_s", 0) > 0, chaos.get("runs_left"),
                       top.get("id"), top.get("status"), len((inc or {}).get("trace") or [])])


st.session_state["sig"] = signature(chaos, incidents, inc)


# ---------- top bar ----------
left, mid, right = st.columns([1, 2, 1])
with left:
    show(f'<div class="topl"><span class="dot{"" if health else " off"}"></span>{"API online" if health else "API offline"}</div>')
with mid:
    show('<div class="title"><h1>Incident RCA Agent</h1><p>Break a live shop, then watch AI agents find out why.</p></div>')
with right:
    @st.fragment(run_every=1)                                         # KEY: only this small part re-runs every second
    def ticker():
        c = api_get("/chaos") or {}
        incs = api_get("/incidents") or []
        cur = api_get(f"/incidents/{incs[0]['id']}") if incs and incs[0]["status"] == "running" else (inc if incs and inc and incs[0]["id"] == inc["id"] else None)
        if signature(c, incs, cur) != st.session_state.get("sig"):
            st.rerun()                                                # KEY: something changed (alarm arrived, step done) -> redraw the page
        if c.get("running"):
            end = ts(c["started"]) + c.get("chaos_s", 420)
            show(f'<div class="timer"><span class="pill live">Outage live · auto-fix in {dur(end - time.time())}</span></div>')
        elif c.get("cooldown_left_s"):
            show(f'<div class="timer"><span class="pill wait">Next break in {dur(c["cooldown_left_s"])}</span></div>')
        else:
            show('<div class="timer"><span class="pill ok">Ready</span></div>')
    ticker()

# ---------- controls ----------
_, ctr, _ = st.columns([1, 1.2, 1])
with ctr:
    ids = [s["id"] for s in chaos.get("scenarios", [])]
    lc, sc = st.columns([.3, 1], vertical_alignment="center")
    lc.markdown('<div class="pick">Choose a failure</div>', unsafe_allow_html=True)
    sid = sc.selectbox("Choose a failure", ids, format_func=lambda i: FAILURE.get(i, i), disabled=bool(running), label_visibility="collapsed")   # KEY: label shown on the left instead
    b1, b2 = st.columns(2)
    blocked = bool(running) or chaos.get("cooldown_left_s", 0) > 0 or chaos.get("runs_left", 1) == 0 or not ids
    if b1.button("Break now", key="brk", disabled=blocked, use_container_width=True):
        ok, msg = api_post(f"/chaos/{sid}")
        if ok:
            st.rerun()
        st.error(msg)
    if b2.button("Restore", key="rst", disabled=not running, use_container_width=True):
        api_post("/chaos/stop")
        st.rerun()
    show(f'<div class="left">{chaos.get("runs_left", "–")} breaks left today</div>')

# ---------- progress line ----------
received = ts(inc["received_at"]) if inc else None
start = broke_at if broke_at and (received is None or 0 <= received - broke_at < 3600) and status != "idle" else None
rca = ts(inc.get("started_at")) if inc else None
cause_t = None
if inc and status == "done":
    ok_e = next((e for e in inc.get("trace") or [] if e["node"] == "critic" and str(e["text"]).startswith("verdict → ok")), None)
    cause_t = rca + (ok_e["t"] if ok_e else inc.get("agent_s", 0))
done_t = ts(inc.get("finished_at")) if inc and status == "done" else None
stops = [("Process started", start), ("Alert fired", received), ("RCA started", rca), ("Cause identified", cause_t), ("Process completed", done_t)]
if status in ("breaking", "missed") and start is None:
    stops[0] = ("Process started", broke_at)
first_open = next((i for i, (_, t) in enumerate(stops) if t is None), len(stops))
html_track = ""
for i, (name, t) in enumerate(stops):
    is_done = t is not None or (i == 0 and status not in ("idle",))
    cls = "done" if is_done else ("now" if i == first_open and status in ("breaking", "queued", "running") else "")
    html_track += f'<div class="stop {cls}"><div class="ball"></div><div class="nm">{name}</div></div>'
    if i < len(stops) - 1:
        nxt = stops[i + 1][1]
        label = dur(nxt - t) if t is not None and nxt is not None else ""
        html_track += f'<div class="seg {"done" if nxt is not None else ""}"><div class="bar"></div><div class="dur">{label}</div></div>'
show('<div class="sec">Progress</div>')
show(f'<div class="track">{html_track}</div>')

if status == "idle":
    show('<div class="banner">Everything is healthy. Choose a failure and press <b>Break now</b>.</div>')
elif status == "breaking":
    show(f'<div class="banner wait">{esc(FAILURE.get(running, running))} is live. Waiting for the monitoring to raise an alarm…</div>')
elif status == "missed":
    show('<div class="banner">The last break ended before any alarm went off, so there was nothing to investigate. Try another failure.</div>')
elif status == "queued":
    show('<div class="banner wait">Alarm received. Waiting a moment for related alarms, so the agents see the full picture…</div>')
elif status == "failed":
    show(f'<div class="banner bad">The investigation failed: {esc(inc.get("error"))}</div>')

# ---------- agent graph ----------
seen = {e["node"] for e in (inc or {}).get("trace") or []}


def state_of(n: str) -> str:
    if status in ("idle", "missed"):
        return "idle"
    if n in seen or status == "done":
        return "done"
    if status == "running" and all(p in seen for p in NEEDS[n]):
        return "run"
    return "todo"


if "sel" not in st.session_state:
    st.session_state.sel = None


def node(n: str):
    name, model, _ = NODES[n]
    sel = "sel" if st.session_state.sel == n else "no"
    if st.button(name, key=f"n_{state_of(n)}_{sel}_{n}", use_container_width=True):   # KEY: the key carries the colour state for the CSS
        st.session_state.sel = None if st.session_state.sel == n else n
        st.rerun()
    show(f'<div class="model">{model or "&nbsp;"}</div>')            # KEY: every node gets the same caption line, so buttons stay level


show('<div class="sec">How the agents worked</div>')
g = st.columns([1, .18, 2.5, .18, 1.25, .18, 1, .18, 1], vertical_alignment="center")
with g[0]:
    node("triage")
with g[1]:
    show('<div class="arrow main">→</div>')
with g[2]:
    with st.container(border=True):
        show('<div class="par">run in parallel</div>')
        node("logs_agent")
        node("metrics_agent")
        d1, d2, d3 = st.columns([1, .18, 1], vertical_alignment="top")
        with d1:
            node("deploy_agent")
        with d2:
            show('<div class="arrow" style="padding-top:.7rem">→</div>')
        with d3:
            node("diff_agent")
with g[3]:
    show('<div class="arrow main">→</div>')
with g[4]:
    show('<div class="gap"></div>')                                   # KEY: same height as the memory block below, keeps the reasoner on the main line
    node("correlator")
    show('<div class="arrow">↑</div>')
    node("memory")
with g[5]:
    show('<div class="arrow main">→</div>')
with g[6]:
    node("critic")
with g[7]:
    show('<div class="arrow main">→</div>')
with g[8]:
    node("reporter")

pick = st.session_state.sel
if pick:
    name, _, what = NODES[pick]
    if status == "done":
        items = "".join(f"<li>{esc(a)}" + (f"<br><small>{esc(b)}</small>" if b else "") + "</li>" for a, b in node_lines(pick, inc)) or "<li>Nothing found</li>"
    else:
        items = "<li>Results appear here when the investigation finishes.</li>"
    show(f'<div class="box"><h4>{name}</h4><div class="what">{what}</div><ul>{items}</ul></div>')

# ---------- verdict ----------
if status == "done":
    h = inc["hypothesis"]
    facts = "".join(f"<li>{esc(x)}</li>" for x in (h.get("evidence") or [])[:3])
    release = f' · release {esc(h["deploy_tag"])}' if h.get("deploy_tag") else ""
    show('<div class="sec">Verdict</div>')
    show(f'<div class="verdict"><div><div class="k">Root cause</div><div class="cause">{esc(CAUSE.get(h["cause"], h["cause"]))}</div>'
         f'<div class="code">{esc(h["cause"])}</div><span class="conf {esc(h["confidence"])}">{esc(h["confidence"])} confidence</span></div>'
         f'<div><div class="k">What happened</div><div class="sum">{esc(h["summary"])}</div>'
         f'<div class="meta">Diagnosed in {inc["agent_s"]} s · {inc.get("llm_calls")} AI calls{release}</div></div>'
         f'<div><div class="k">Key facts</div><ul>{facts}</ul></div></div>')

    @st.dialog("Full incident report", width="large")
    def report_box():
        st.markdown(inc.get("report") or "No report.")

    @st.dialog("Raw Alertmanager payload", width="large")
    def payload_box():
        st.json(inc.get("payload") or {})

    st.write("")
    e1, e2, e3 = st.columns(3)
    if e1.button("Evidence collected", key="evb", use_container_width=True):
        st.session_state.ev = None if st.session_state.get("ev") else "logs"
    if e2.button("Full incident report", key="repb", use_container_width=True):
        report_box()
    if e3.button("Raw Alertmanager payload", key="rawb", use_container_width=True):
        payload_box()

    tab = st.session_state.get("ev")
    if tab:
        t1, t2, t3, _ = st.columns([1, 1, 1, 1])
        for col, (k, label) in zip((t1, t2, t3), (("logs", "Logs evidence"), ("metrics", "Metrics evidence"), ("deploys", "Deploys and code"))):
            if col.button(label, key=f"ev_{'on' if tab == k else 'off'}_{k}", use_container_width=True):
                st.session_state.ev = k
                st.rerun()
        rows = evidence(inc, "deploys") + evidence(inc, "diff") if tab == "deploys" else evidence(inc, tab)
        items = "".join(f"<li>{esc(a)}" + (f"<br><small>{esc(b)}</small>" if b else "") + "</li>" for a, b in rows) or "<li>Nothing found</li>"
        show(f'<div class="box"><ul>{items}</ul></div>')