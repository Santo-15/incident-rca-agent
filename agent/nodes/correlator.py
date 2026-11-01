# correlator: all findings -> one root-cause hypothesis (CorrelatorAnswer), using the critic's feedback on a retry
import logging
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


def correlator(state: RCAState) -> dict:
    inputs = evidence(state) | {"critique": state.get("critique") or "none (first attempt)"}   # KEY: retry sees why the last answer was weak
    try:
        answer = get_llm("correlator", schema=CorrelatorAnswer).invoke(CORRELATOR_PROMPT.invoke(inputs))
        if answer is None:
            raise ValueError("no structured answer")
        h = answer.model_dump()
    except Exception as exc:   # both LLMs failed: an honest "don't know" instead of a crash
        logger.warning("correlator LLM failed: %s", exc)
        h = CorrelatorAnswer(cause="insufficient_evidence", summary=f"correlator LLM failed: {type(exc).__name__}",
                             evidence=[], silent_signals="", deploy_tag=None, confidence="low").model_dump()
    return {"hypothesis": h, "hypotheses": [h], "loop_count": state.get("loop_count", 0) + 1, "llm_calls": 1}
