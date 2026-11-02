# Streamlit UI for the RCA agent: portfolio-style dashboard. Reads the API only; never runs the agent itself.
import html
import os

import httpx
import streamlit as st

API = os.getenv("RCA_API_URL", "http://127.0.0.1:8001")             # KEY: one setting; the cloud deploy changes this, not the code
EVAL_CHIP = "91% top-1 on 11 chaos incidents"                        # from eval/results.md (final run)

st.set_page_config(page_title="Incident RCA Agent", page_icon="🩺", layout="wide")

# ---------- style ----------
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, .stApp, .stMarkdown, p, li {font-family:'Inter',sans-serif;}
.stApp {background: radial-gradient(1100px 520px at 0% -10%, #0e2a3a 0%, #0b0f14 60%) fixed;}
.block-container {padding-top:2.2rem; max-width:1350px;}
[data-testid="stSidebar"] {background:#0d131a; border-right:1px solid #1c2733;}
.hero h1 {font-size:2.5rem; font-weight:800; margin:0; background:linear-gradient(90deg,#00e5a0,#38bdf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
.hero p {color:#8aa0b4; margin:.3rem 0 0 0; font-size:1.02rem;}
.chips {display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.9rem;}
.chip {font-family:'JetBrains Mono',monospace; font-size:.78rem; padding:.28rem .7rem; border:1px solid #1f2a36; border-radius:999px; color:#b9c7d6; background:#0f1620;}
.chip b {color:#00e5a0; font-weight:600;}
.dot {display:inline-block; width:8px; height:8px; border-radius:50%; background:#00e5a0; margin-right:6px; box-shadow:0 0 8px #00e5a0;}
.dot.off {background:#f43f5e; box-shadow:0 0 8px #f43f5e;}
.section {font-family:'JetBrains Mono',monospace; font-size:.78rem; color:#38bdf8; text-transform:uppercase; letter-spacing:.14em; margin:1.6rem 0 .6rem;}
.pipe {display:flex; align-items:center; gap:.45rem; flex-wrap:wrap; padding:1rem; background:#0d141c; border:1px solid #1c2733; border-radius:14px;}
.node {font-family:'JetBrains Mono',monospace; font-size:.8rem; padding:.55rem .85rem; border-radius:10px; border:1px solid #243243; background:#0f1620; color:#5f7387; text-align:center; min-width:96px;}
.node small {display:block; font-size:.68rem; color:#4e5f70; margin-top:2px;}
.node.done {border-color:#00e5a0; color:#d6ffef; box-shadow:0 0 14px rgba(0,229,160,.18);}
.node.done small {color:#7fd9b9;}
.node.run {border-color:#38bdf8; color:#dff4ff; animation:pulse 1.2s ease-in-out infinite;}
.node.fail {border-color:#f43f5e; color:#ffd9df;}
@keyframes pulse {0%,100% {box-shadow:0 0 0 rgba(56,189,248,0);} 50% {box-shadow:0 0 18px rgba(56,189,248,.55);}}
.arrow {color:#34465a; font-size:1.1rem;}
.par {display:flex; flex-direction:column; gap:.35rem;}
.card {background:#0f1620; border:1px solid #1f2a36; border-radius:14px; padding:1.1rem 1.3rem;}
.lbl {font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:#6b7f93;}
.cause {font-family:'JetBrains Mono',monospace; font-size:2rem; font-weight:600; color:#00e5a0; margin:.15rem 0 .4rem;}
.cause.unk {color:#f59e0b;}
.summary {color:#c7d4e1; font-size:.98rem; line-height:1.5;}
.badge {font-family:'JetBrains Mono',monospace; font-size:.72rem; padding:.15rem .55rem; border-radius:6px; margin-left:.4rem; vertical-align:middle;}
.b-high {background:rgba(0,229,160,.12); color:#00e5a0; border:1px solid rgba(0,229,160,.4);}
.b-medium {background:rgba(245,158,11,.12); color:#f59e0b; border:1px solid rgba(245,158,11,.4);}
.b-low {background:rgba(244,63,94,.12); color:#f43f5e; border:1px solid rgba(244,63,94,.4);}
.stats {display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem; margin-top:1rem;}
.stat {background:#0b1118; border:1px solid #1c2733; border-radius:10px; padding:.65rem .85rem;}
.stat .v {font-family:'JetBrains Mono',monospace; font-size:1.25rem; color:#e6f0fa;}
.stat .k {font-size:.68rem; color:#6b7f93; text-transform:uppercase; letter-spacing:.1em;}
.ev {margin:.8rem 0 0 0; padding-left:1.1rem; color:#aebdcc; font-size:.9rem;}
.colhead {font-family:'JetBrains Mono',monospace; font-size:.8rem; color:#38bdf8; text-transform:uppercase; letter-spacing:.12em; margin-bottom:.6rem;}
.f {border-left:3px solid #34465a; background:#0f1620; border-radius:8px; padding:.55rem .75rem; margin-bottom:.5rem;}
.f.high {border-left-color:#f43f5e;} .f.medium {border-left-color:#f59e0b;}
.f .s {font-family:'JetBrains Mono',monospace; font-size:.8rem; color:#e6f0fa;}
.f .d {font-size:.77rem; color:#8aa0b4; margin-top:.25rem; word-break:break-word;}
.empty {color:#6b7f93; font-size:.8rem; font-style:italic;}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)


def show(h: str):
    st.markdown(h, unsafe_allow_html=True)                            # KEY: HTML must be one line; indented lines would render as a code block


def esc(x) -> str:
    return html.escape(str(x))                                        # KEY: log text can contain < > & quotes; never inject it raw


def api_get(path: str):
    try:
        r = httpx.get(f"{API}{path}", timeout=5)                     # short timeout: a stuck API must not freeze the page
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return None


health = api_get("/health")
incidents = api_get("/incidents") or []

# ---------- sidebar: incident picker ----------
with st.sidebar:
    up = '<span class="dot"></span>API online' if health else '<span class="dot off"></span>API offline'
    show(f'<div class="chip">{up}</div>')
    st.write("")
    pick = None
    if incidents:
        ICON = {"queued": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}
        labels = {i["id"]: f"{ICON.get(i['status'], '')} {i['cause'] or i['status']} · {i['received_at'][11:19]}" for i in incidents}
        pick = st.radio("Incidents", list(labels), format_func=labels.get)   # newest first, so the default is the latest
    if st.button("↻ Refresh", use_container_width=True):              # S5 replaces this with auto-refresh
        st.rerun()

# ---------- hero ----------
done = [i for i in incidents if i["status"] == "done"]
avg = f"{sum(i['agent_s'] for i in done) / len(done):.1f} s" if done else "–"
show('<div class="hero"><h1>Incident RCA Agent</h1>'
     '<p>From alert to root cause in seconds. A LangGraph multi-agent pipeline reads logs, metrics and deploys, then explains what broke.</p>'
     f'<div class="chips"><span class="chip">incidents <b>{len(incidents)}</b></span>'
     f'<span class="chip">avg diagnosis <b>{avg}</b></span>'
     f'<span class="chip">eval <b>{EVAL_CHIP}</b></span>'
     '<span class="chip">stack <b>LangGraph · Groq · Prometheus · Loki</b></span></div></div>')

inc = api_get(f"/incidents/{pick}") if pick else None

# ---------- pipeline ----------
def node(name: str, state: str, sub: str = "") -> str:
    return f'<div class="node {state}">{esc(name)}<small>{esc(sub)}</small></div>'


status = inc["status"] if inc else "idle"
STATE = {"idle": "", "queued": "", "running": "run", "done": "done", "failed": "fail"}[status]   # KEY: one incident status -> colour of every agent node
first = "done" if inc else ""                                         # the alert itself already arrived once an incident exists
count = {}
for f in (inc or {}).get("findings") or []:
    count[f["source"]] = count.get(f["source"], 0) + 1
sub = (lambda s: f"{count.get(s, 0)} findings") if status == "done" else (lambda s: "")
A = '<span class="arrow">➜</span>'
show('<div class="section">Agent pipeline</div><div class="pipe">'
     + node("Alert", first, "Alertmanager") + A + node("Triage", STATE, "parse alerts") + A
     + '<div class="par">' + node("Logs", STATE, sub("logs")) + node("Metrics", STATE, sub("metrics"))
     + node("Deploys→Diff", STATE, sub("deploys")) + '</div>' + A
     + node("Correlator", STATE, "root cause") + A + node("Critic", STATE, "check") + A + node("Report", STATE, "markdown")
     + '</div>')

if not inc:
    show('<div class="section">Status</div><div class="card"><span class="summary">No incidents yet. Break something (buttons coming next) and wait for an alert.</span></div>')
    st.stop()

# ---------- verdict ----------
show('<div class="section">Diagnosis</div>')
if status in ("queued", "running"):
    show(f'<div class="card"><div class="lbl">status</div><div class="cause unk">{status}…</div>'
         '<div class="summary">The agent waits for related alerts to settle, then investigates. Press Refresh.</div></div>')
elif status == "failed":
    show(f'<div class="card"><div class="lbl">status</div><div class="cause unk">failed</div><div class="summary">{esc(inc.get("error"))}</div></div>')
else:
    h = inc["hypothesis"]
    unk = " unk" if h["cause"] in ("insufficient_evidence", "other") else ""
    ev = "".join(f"<li>{esc(e)}</li>" for e in h.get("evidence") or [])
    show(f'<div class="card"><div class="lbl">root cause<span class="badge b-{esc(h["confidence"])}">{esc(h["confidence"])} confidence</span></div>'
         f'<div class="cause{unk}">{esc(h["cause"])}</div><div class="summary">{esc(h["summary"])}</div>'
         f'<ul class="ev">{ev}</ul>'
         '<div class="stats">'
         f'<div class="stat"><div class="k">time to diagnosis</div><div class="v">{inc["agent_s"]} s</div></div>'
         f'<div class="stat"><div class="k">LLM calls</div><div class="v">{inc.get("llm_calls")}</div></div>'
         f'<div class="stat"><div class="k">deploy</div><div class="v">{esc(h.get("deploy_tag") or "none")}</div></div>'
         f'<div class="stat"><div class="k">findings</div><div class="v">{len(inc["findings"])}</div></div>'
         '</div></div>')

    # ---------- evidence ----------
    show('<div class="section">Evidence by agent</div>')
    ORDER = {"high": 0, "medium": 1, "low": 2}
    cols = st.columns(3)
    for col, (title, sources) in zip(cols, [("Logs agent", {"logs"}), ("Metrics agent", {"metrics"}), ("Deploy + diff agents", {"deploys", "diff"})]):
        rows = sorted((f for f in inc["findings"] if f["source"] in sources), key=lambda f: ORDER.get(f["severity"], 3))   # high first
        cards = "".join(f'<div class="f {esc(f["severity"])}"><div class="s">{esc(f["signal"])}</div><div class="d">{esc(f["detail"])}</div></div>' for f in rows)
        with col:
            show(f'<div class="colhead">{title}</div>' + (cards or '<div class="empty">nothing found</div>'))

with st.expander("Full incident report (markdown)"):
    st.markdown((inc.get("report") or "").replace("\n", "  \n"))      # 2 spaces before newline = real line breaks
with st.expander("Raw Alertmanager payload"):
    st.json(inc["payload"])