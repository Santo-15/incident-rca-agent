# Streamlit UI for the RCA agent: live investigation dashboard. Reads the API only; never runs the agent itself.
import html
import os
import re
import time

import httpx
import streamlit as st

API = os.getenv("RCA_API_URL", "http://127.0.0.1:8001")             # KEY: one setting; the cloud deploy changes this, not the code
EVAL_CHIP = "91% top-1 on 11 chaos incidents"                        # from eval/results.md (final run)

st.set_page_config(page_title="Incident RCA Agent", page_icon="🩺", layout="wide")

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, .stApp, .stMarkdown, p, li {font-family:'Inter',sans-serif;}
.stApp {background: radial-gradient(1000px 500px at 0% -10%, #0e2a3a 0%, #0a0e13 60%) fixed;}
.block-container {padding-top:2rem; max-width:1300px;}
[data-testid="stSidebar"] {background:#0c1218; border-right:1px solid #1a2430;}
.hero h1 {font-size:2.2rem; font-weight:800; margin:0; background:linear-gradient(90deg,#00e5a0,#38bdf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
.hero p {color:#8b9db0; margin:.35rem 0 0 0; font-size:1rem; max-width:820px;}
.chips {display:flex; gap:.45rem; flex-wrap:wrap; margin-top:.8rem;}
.chip {font-size:.76rem; padding:.25rem .65rem; border:1px solid #1d2835; border-radius:999px; color:#a9b8c8; background:#0e151d;}
.chip b {color:#00e5a0; font-weight:600;}
.dot {display:inline-block; width:8px; height:8px; border-radius:50%; background:#00e5a0; margin-right:6px; box-shadow:0 0 8px #00e5a0;}
.dot.off {background:#f43f5e; box-shadow:0 0 8px #f43f5e;}
.h {font-size:.74rem; font-weight:600; color:#6f8399; text-transform:uppercase; letter-spacing:.14em; margin:1.6rem 0 .7rem;}
.banner {display:flex; align-items:center; gap:1rem; padding:1.1rem 1.4rem; border-radius:16px; margin-top:1.4rem; border:1px solid;}
.banner .big {font-size:1.35rem; font-weight:700; color:#eef5fb;}
.banner .small {font-size:.9rem; color:#a9b8c8; margin-top:.15rem;}
.banner .ico {font-size:1.9rem;}
.b-settle {background:linear-gradient(90deg,rgba(245,158,11,.14),rgba(245,158,11,.03)); border-color:rgba(245,158,11,.35);}
.b-run {background:linear-gradient(90deg,rgba(56,189,248,.16),rgba(56,189,248,.03)); border-color:rgba(56,189,248,.4); animation:glow 1.6s ease-in-out infinite;}
.b-done {background:linear-gradient(90deg,rgba(0,229,160,.15),rgba(0,229,160,.03)); border-color:rgba(0,229,160,.4);}
.b-fail {background:linear-gradient(90deg,rgba(244,63,94,.15),rgba(244,63,94,.03)); border-color:rgba(244,63,94,.4);}
.b-idle {background:#0e151d; border-color:#1d2835;}
@keyframes glow {0%,100% {box-shadow:0 0 0 rgba(56,189,248,0);} 50% {box-shadow:0 0 28px rgba(56,189,248,.25);}}
.cause-inline {font-family:'JetBrains Mono',monospace; color:#00e5a0;}
.tl {position:relative; padding-left:.2rem;}
.step {display:flex; gap:.9rem; position:relative; padding-bottom:1rem;}
.step:not(:last-child)::before {content:''; position:absolute; left:19px; top:42px; bottom:0; width:2px; background:#1d2835;}
.step.done:not(:last-child)::before {background:linear-gradient(#00e5a0,#1d2835);}
.ic {width:40px; height:40px; min-width:40px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:1.15rem; background:#0e151d; border:1px solid #1d2835;}
.step.done .ic {border-color:rgba(0,229,160,.5); background:rgba(0,229,160,.08);}
.step.run .ic {border-color:#38bdf8; animation:glow 1.2s ease-in-out infinite;}
.step.todo {opacity:.38;}
.step.warn .ic {border-color:#f59e0b; background:rgba(245,158,11,.1);}
.step.think .ic {border-color:rgba(167,139,250,.6); background:rgba(167,139,250,.1);}
.body {flex:1; padding-top:.15rem;}
.hd {display:flex; align-items:center; gap:.55rem; flex-wrap:wrap;}
.hd b {color:#e8f0f8; font-weight:600; font-size:.95rem;}
.tm {font-family:'JetBrains Mono',monospace; font-size:.72rem; color:#5d7084;}
.m {font-family:'JetBrains Mono',monospace; font-size:.68rem; color:#c4b5fd; border:1px solid #4c3d85; background:rgba(124,92,255,.1); border-radius:6px; padding:.05rem .45rem;}
.tag {font-size:.68rem; color:#7fd9b9; border:1px solid rgba(0,229,160,.35); border-radius:6px; padding:.05rem .45rem;}
.tx {color:#a9b8c8; font-size:.88rem; margin-top:.2rem; line-height:1.45;}
.tx .k {color:#e8f0f8;}
.card {background:#0e151d; border:1px solid #1d2835; border-radius:16px; padding:1.2rem 1.35rem;}
.lbl {font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:#6f8399;}
.cause {font-family:'JetBrains Mono',monospace; font-size:1.9rem; font-weight:600; color:#00e5a0; margin:.2rem 0 .5rem; word-break:break-word;}
.cause.unk {color:#f59e0b;}
.summary {color:#c9d6e3; font-size:.95rem; line-height:1.55;}
.badge {font-size:.68rem; font-weight:600; padding:.15rem .55rem; border-radius:6px; margin-left:.5rem; vertical-align:middle; letter-spacing:.06em; text-transform:uppercase;}
.c-high {background:rgba(0,229,160,.12); color:#00e5a0; border:1px solid rgba(0,229,160,.4);}
.c-medium {background:rgba(245,158,11,.12); color:#f59e0b; border:1px solid rgba(245,158,11,.4);}
.c-low {background:rgba(244,63,94,.12); color:#f43f5e; border:1px solid rgba(244,63,94,.4);}
.ev {margin:.8rem 0 0 0; padding-left:1.1rem; color:#a9b8c8; font-size:.86rem; line-height:1.55;}
.rethink {margin-top:.7rem; font-size:.85rem; color:#c4b5fd;}
.stats {display:grid; grid-template-columns:1fr 1fr; gap:.6rem; margin-top:1rem;}
.stat {background:#0a1016; border:1px solid #1a2430; border-radius:12px; padding:.7rem .85rem;}
.stat .v {font-family:'JetBrains Mono',monospace; font-size:1.3rem; color:#eef5fb;}
.stat .k {font-size:.66rem; color:#6f8399; text-transform:uppercase; letter-spacing:.1em;}
.colhead {font-size:.8rem; font-weight:600; color:#e8f0f8; margin-bottom:.6rem;}
.f {border-left:3px solid #2c3b4c; background:#0e151d; border-radius:10px; padding:.6rem .8rem; margin-bottom:.5rem;}
.f.high {border-left-color:#f43f5e;} .f.medium {border-left-color:#f59e0b;}
.f .s {font-size:.86rem; color:#e8f0f8; font-weight:500;}
.f .d {font-family:'JetBrains Mono',monospace; font-size:.7rem; color:#71859a; margin-top:.3rem; word-break:break-word;}
.empty {color:#5d7084; font-size:.82rem; font-style:italic;}
.how {display:grid; grid-template-columns:repeat(3,1fr); gap:.8rem; margin-top:1rem;}
.how .card b {color:#e8f0f8;} .how .card span {color:#8b9db0; font-size:.88rem;}
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


# ---------- plain-English names ----------
METRIC = {"p95_by_path": "slow responses (p95)", "5xx_rate_by_path": "5xx errors", "pg_up": "Postgres down",
          "redis_up": "Redis down", "shop_api_up": "shop-api not answering", "rss_mib": "memory use", "restarts": "container restarts",
          "pg_connections_by_state": "DB connections", "pg_exporter_up": "Postgres not answering", "redis_exporter_up": "Redis not answering",
          "pg_longest_tx_s": "long DB transaction", "pg_exclusive_locks": "DB locks", "seq_tup_read_products": "full table scans"}


def human(sig: str) -> str:                                          # KEY: "p95_by_path{path=/users/{user_id}/cart}" -> "slow responses (p95) on /cart"
    m = re.match(r"^(\w+)\{\w+=(.+)\}$", sig)
    base, label = (m.group(1), m.group(2)) if m else (sig, None)
    name = METRIC.get(base, base)
    if label is None:
        return name
    path = label.replace("/users/{user_id}", "").replace("{product_id}", "{id}")
    return f"{name} on {path}" if path.startswith("/") else f"{name} ({path})"


STEP = {  # graph node -> (icon, friendly name)
    "triage": ("🧭", "Triage"), "logs_agent": ("📜", "Logs analyst"), "metrics_agent": ("📈", "Metrics analyst"),
    "deploy_agent": ("🚀", "Deploy inspector"), "diff_agent": ("🔍", "Code-diff reader"), "memory": ("🧠", "Incident memory"),
    "correlator": ("🤖", "Root-cause reasoner"), "critic": ("⚖️", "Critic"), "reporter": ("📝", "Reporter"), "llm": ("⚠️", "Model fallback"),
}
ORDER = ["triage", "logs_agent", "metrics_agent", "deploy_agent", "diff_agent", "correlator", "critic", "reporter"]


def one_liner(e: dict) -> str:                                       # what this step concluded, in plain English
    n, high, cnt = e["node"], [esc(human(s)) for s in e.get("high") or []], e.get("count", 0)
    if n == "triage":
        return esc(e["text"])
    if n == "logs_agent":
        return f'<span class="k">{cnt} error pattern(s)</span>' + (f" · {', '.join(high)}" if high else " · no errors in logs")
    if n == "metrics_agent":
        return f'<span class="k">{cnt} signal(s) checked with z-score</span>' + (f" · abnormal: {', '.join(high)}" if high else "")
    if n == "deploy_agent":
        return f'suspect deploy <span class="k">{high[0]}</span>' if high else "no deploy just before the alert"
    if n == "diff_agent":
        return (f"risky change: {', '.join(h.split(': ', 1)[-1] for h in high)}" if high else
                ("nothing to diff" if cnt == 0 else f"{cnt} change(s), none risky"))
    if n == "correlator":
        return f'suspects <span class="cause-inline">{esc(e.get("cause"))}</span> · {esc(e.get("confidence"))} confidence'
    if n == "critic":
        t = str(e["text"]).replace("verdict → ", "")
        return "approved the diagnosis" if t.startswith("ok") else f"rejected it, asked for a rethink: {esc(t[5:])}"
    if n == "memory":
        return esc(e["text"]).replace("similar past incident:", "seen something like this before:")
    if n == "reporter":
        return "wrote the incident report"
    return esc(e["text"])


# ---------- data ----------
health = api_get("/health")
incidents = api_get("/incidents") or []
chaos = None

with st.sidebar:
    up = '<span class="dot"></span>API online' if health else '<span class="dot off"></span>API offline'
    show(f'<div class="chip">{up}</div>')
    show('<div class="h">Break something</div>')
    chaos = api_get("/chaos")
    if chaos:
        if chaos["running"]:
            st.error(f"💥 **{chaos['running']}** is live · auto-restores after {chaos['chaos_s'] // 60} min")
            if st.button("🛠 Restore now", use_container_width=True):
                api_post("/chaos/stop")
                st.rerun()
        else:
            opts = {s["id"]: f"{s['id']} · {s['kind']}" for s in chaos["scenarios"]}
            sid = st.selectbox("Failure to inject", list(opts), format_func=opts.get)
            st.caption(next(s["note"] for s in chaos["scenarios"] if s["id"] == sid))
            wait = chaos["cooldown_left_s"]
            if st.button("💥 Break it", disabled=wait > 0 or chaos.get("runs_left", 1) == 0, use_container_width=True, type="primary"):
                ok, msg = api_post(f"/chaos/{sid}")
                if ok:
                    st.rerun()
                st.error(msg)
            st.caption(f"{chaos.get('runs_left', '?')} demo outages left today")   # daily cap, visible to visitors
            if wait:
                st.caption(f"Cooling down {wait // 60}m {wait % 60}s so the agent gets a clean 10-min baseline.")
            if chaos["last_exit"] not in (None, 0, 130):
                st.warning("Last scenario failed: see /tmp/rca_chaos.log (deploy scenarios need a clean git tree).")
    pick = None
    if incidents:
        show('<div class="h">Incidents</div>')
        ICON = {"queued": "🟠", "running": "🔵", "done": "🟢", "failed": "🔴"}
        labels = {i["id"]: f"{ICON.get(i['status'], '')} {i['cause'] or i['status']} · {i['received_at'][11:16]}" for i in incidents}
        pick = st.radio("Incidents", list(labels), format_func=labels.get, label_visibility="collapsed")   # newest first = auto-picks a new one

inc = api_get(f"/incidents/{pick}") if pick else None
status = inc["status"] if inc else "idle"
trace = (inc or {}).get("trace") or []


def keep_live():                                                      # KEY: auto-refresh only while something is happening
    busy = status in ("queued", "running")
    if busy or (chaos and chaos.get("running")):
        time.sleep(1.5 if busy else 4)
        st.rerun()


# ---------- hero ----------
done = [i for i in incidents if i["status"] == "done"]
avg = f"{sum(i['agent_s'] for i in done) / len(done):.1f} s" if done else "–"
show('<div class="hero"><h1>Incident RCA Agent</h1>'
     '<p>Break a live system, then watch a team of AI agents read its logs, metrics and deploys, argue about the cause, and explain what broke, in seconds.</p>'
     f'<div class="chips"><span class="chip">avg diagnosis <b>{avg}</b></span><span class="chip">eval <b>{EVAL_CHIP}</b></span>'
     '<span class="chip">LangGraph · Groq · Gemini · Chroma · Prometheus · Loki</span></div></div>')

# ---------- status banner ----------
if not inc:
    running = chaos and chaos.get("running")
    show('<div class="banner b-idle"><div class="ico">' + ("💥" if running else "🛰️") + '</div><div><div class="big">'
         + (f"{esc(running)} injected, waiting for the first alert…" if running else "All systems healthy")
         + '</div><div class="small">' + ("Prometheus is noticing the failure; Alertmanager will call the agent." if running else "Pick a failure in the sidebar and press Break it.")
         + '</div></div></div>')
    show('<div class="how">'
         '<div class="card"><b>1 · Break it</b><br><span>A chaos script kills or freezes Postgres or Redis, or ships a bad deploy, in a real Docker stack.</span></div>'
         '<div class="card"><b>2 · Alert fires</b><br><span>Prometheus detects it, Alertmanager calls this agent through a webhook.</span></div>'
         '<div class="card"><b>3 · Agents investigate</b><br><span>Specialists gather evidence in parallel; a reasoner proposes the cause; a critic checks it.</span></div>'
         '</div>')
    keep_live()
    st.stop()

if status == "queued":
    left = max(0, int(inc.get("settle_until", 0) - time.time()))
    show(f'<div class="banner b-settle"><div class="ico">🚨</div><div><div class="big">Outage detected · waiting {left}s for related alerts</div>'
         '<div class="small">Other symptoms take a minute to show up; the agent waits so it sees the full picture.</div></div></div>')
elif status == "running":
    show('<div class="banner b-run"><div class="ico">🔎</div><div><div class="big">Agents investigating…</div>'
         '<div class="small">Specialists are reading logs, metrics and deploys in parallel.</div></div></div>')
elif status == "failed":
    show(f'<div class="banner b-fail"><div class="ico">❌</div><div><div class="big">Diagnosis failed</div><div class="small">{esc(inc.get("error"))}</div></div></div>')
else:
    h = inc["hypothesis"]
    show(f'<div class="banner b-done"><div class="ico">✅</div><div><div class="big">Root cause found: <span class="cause-inline">{esc(h["cause"])}</span></div>'
         f'<div class="small">in {inc["agent_s"]} s · {inc.get("llm_calls")} LLM calls · {len(inc["findings"])} pieces of evidence · {esc(h["confidence"])} confidence</div></div></div>')

# ---------- timeline + verdict ----------
left_col, right_col = st.columns([3, 2], gap="large")
with left_col:
    show('<div class="h">Investigation timeline</div>')
    steps, seen = "", {e["node"] for e in trace}
    for e in trace:                                                   # KEY: real order and timing from the LangGraph stream
        icon, name = STEP.get(e["node"], ("•", e["node"]))
        cls = "warn" if e["node"] == "llm" or (e["node"] == "critic" and not str(e["text"]).startswith("verdict → ok")) else \
              "think" if e["node"] in ("correlator", "critic", "memory") else "done"
        model = f'<span class="m">{esc(e["llm"])}</span>' if e.get("llm") else ('<span class="tag">no LLM</span>' if e["node"] in ("triage", "metrics_agent", "deploy_agent") else "")
        steps += (f'<div class="step {cls}"><div class="ic">{icon}</div><div class="body"><div class="hd"><b>{esc(name)}</b>'
                  f'<span class="tm">+{e["t"]:.1f}s</span>{model}</div><div class="tx">{one_liner(e)}</div></div></div>')
    if status in ("queued", "running"):                               # steps not reached yet: greyed, the next one pulses
        first = True
        for n in ORDER:
            if n in seen:
                continue
            icon, name = STEP[n]
            cls = "run" if first and status == "running" else "todo"
            first = False
            steps += f'<div class="step {cls}"><div class="ic">{icon}</div><div class="body"><div class="hd"><b>{esc(name)}</b></div><div class="tx">waiting…</div></div></div>'
    show(f'<div class="tl">{steps or "<div class=empty>No timeline for this incident.</div>"}</div>')

with right_col:
    show('<div class="h">Verdict</div>')
    if status != "done":
        show('<div class="card"><div class="lbl">root cause</div><div class="cause unk">…</div><div class="summary">The verdict appears here when the critic approves it.</div></div>')
    else:
        unk = " unk" if h["cause"] in ("insufficient_evidence", "other") else ""
        ev = "".join(f"<li>{esc(x)}</li>" for x in (h.get("evidence") or [])[:4])
        tries = inc.get("hypotheses") or []
        rethink = (f'<div class="rethink">🔁 critic forced a rethink: {" → ".join(esc(x.get("cause")) for x in tries)}</div>' if len(tries) > 1
                   and tries[0].get("cause") != tries[-1].get("cause") else "")
        show(f'<div class="card"><div class="lbl">root cause<span class="badge c-{esc(h["confidence"])}">{esc(h["confidence"])}</span></div>'
             f'<div class="cause{unk}">{esc(h["cause"])}</div><div class="summary">{esc(h["summary"])}</div><ul class="ev">{ev}</ul>{rethink}'
             '<div class="stats">'
             f'<div class="stat"><div class="k">time to diagnosis</div><div class="v">{inc["agent_s"]} s</div></div>'
             f'<div class="stat"><div class="k">LLM calls</div><div class="v">{inc.get("llm_calls")}</div></div>'
             f'<div class="stat"><div class="k">suspect deploy</div><div class="v">{esc(h.get("deploy_tag") or "none")}</div></div>'
             f'<div class="stat"><div class="k">evidence</div><div class="v">{len(inc["findings"])}</div></div>'
             '</div></div>')

# ---------- evidence ----------
if status == "done":
    show('<div class="h">Evidence collected</div>')
    SEV = {"high": 0, "medium": 1, "low": 2}
    cols = st.columns(3, gap="medium")
    for col, (title, sources) in zip(cols, [("📜 Logs", {"logs"}), ("📈 Metrics", {"metrics"}), ("🚀 Deploys & code", {"deploys", "diff"})]):
        rows = sorted((f for f in inc["findings"] if f["source"] in sources), key=lambda f: SEV.get(f["severity"], 3))
        cards = "".join(f'<div class="f {esc(f["severity"])}"><div class="s">{esc(human(f["signal"]))}</div><div class="d">{esc(f["detail"])}</div></div>' for f in rows)
        with col:
            show(f'<div class="colhead">{title}</div>' + (cards or '<div class="empty">nothing found</div>'))
    with st.expander("📄 Full incident report"):
        st.markdown((inc.get("report") or "").replace("\n", "  \n"))
with st.expander("🔧 Raw Alertmanager payload"):
    st.json(inc["payload"])

keep_live()