# correlator: all findings -> one root-cause hypothesis (CorrelatorAnswer), using the critic's feedback on a retry
import logging
import os
from agent.memory import incident_text, search_similar
from agent.llm import get_llm
from agent.prompts.correlator import CORRELATOR_PROMPT
from agent.schemas import CorrelatorAnswer, Finding
from agent.state import RCAState

logger = logging.getLogger("agent.correlator")


def _section(findings: list[Finding], sources: set[str]) -> str:
    lines = [f"- [{f.severity}] {f.signal}: {f.detail}" for f in findings if f.source in sources]
    return "\n".join(lines) or "none"


def evidence(state: RCAState) -> dict:   # shared with the critic so both see exactly the same evidence
    f = state.get("findings", [])
    return {
        "alerts": "\n".join(state.get("alerts", [])) or "none",
        "silent": ", ".join(state.get("silent", [])) or "none",
        "logs": _section(f, {"logs"}),
        "metrics": _section(f, {"metrics"}),
        "deploys": _section(f, {"deploys", "diff"}),
    }

def _similar(state: RCAState) -> list[dict]:
    if os.getenv("RCA_MEMORY", "on") == "off":   # KEY: switch so Phase 11 eval can compare with vs without memory
        return []
    try:
        text = incident_text(state.get("alerts", []), state.get("silent", []), state.get("findings", []))  # KEY: same format as the seed, or distances are meaningless
        return search_similar(text, k=2)   # cutoff MAX_DISTANCE applied inside
    except Exception as exc:   # KEY: memory is optional; a broken Chroma must never stop a diagnosis
        logger.warning("memory lookup failed: %s", exc)
        return []


def _similar_section(hits: list[dict]) -> str:
    if not hits:
        return "none (no close past incident)"
    return "\n".join(
        f"- {h['scenario']} (cause {h['cause']}, distance {h['distance']}, fix was: {h['fix']})\n  its symptoms: "
        + h["text"].replace("\n", "\n  ")   # indent the stored symptoms under their incident
        for h in hits
    )

def correlator(state: RCAState) -> dict:
    hits = state["similar"] if "similar" in state else _similar(state)   # KEY: search once; the critic retry has the same findings, so reuse
    inputs = evidence(state) | {
        "critique": state.get("critique") or "none (first attempt)",   # KEY: retry sees why the last answer was weak
        "similar": _similar_section(hits),   # KEY: added here, NOT inside evidence(), so the critic judges on live evidence only
    }
    try:
        answer = get_llm("correlator", schema=CorrelatorAnswer).invoke(CORRELATOR_PROMPT.invoke(inputs))
        if answer is None:
            raise ValueError("no structured answer")
        h = answer.model_dump()
    except Exception as exc:   # both LLMs failed: an honest "don't know" instead of a crash
        logger.warning("correlator LLM failed: %s", exc)
        h = CorrelatorAnswer(cause="insufficient_evidence", summary=f"correlator LLM failed: {type(exc).__name__}",
                             evidence=[], silent_signals="", deploy_tag=None, confidence="low").model_dump()
    return {"hypothesis": h, "hypotheses": [h], "loop_count": state.get("loop_count", 0) + 1,
            "llm_calls": 1, "similar": hits}