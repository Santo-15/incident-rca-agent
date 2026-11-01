# deploy_agent: deploy tags near the first alert. diff_agent: what those deploys changed (GitHub compare API + LLM).
import logging
from agent.llm import get_llm
from agent.prompts.diff import DIFF_PROMPT
from agent.schemas import Finding, FindingList
from agent.state import RCAState
from agent.timeutil import hms
from agent.tools.github import compare, list_deploy_tags

logger = logging.getLogger("agent.deploys")
SUSPECT_BEFORE_S = 30 * 60   # a deploy up to 30 min before the first alert is a suspect
SUSPECT_AFTER_S = 60         # small slack for clock differences
MAX_SUSPECTS = 2
IGNORE = ("docs/", "chaos/", "agent/", "traffic/", "README")   # KEY: not on the shop's request path, don't spend tokens on them
MAX_PATCH_FILE = 1500        # chars per file patch
MAX_PATCH_TOTAL = 5000       # chars for all patches together


def deploy_agent(state: RCAState) -> dict:
    first = state["first_alert"]
    try:
        tags = list_deploy_tags()
    except Exception as exc:
        logger.warning("deploys unavailable: %s", exc)
        return {"deploys": [], "findings": [Finding(source="deploys", signal="deploys unavailable", detail=str(exc)[:200], severity="low")]}

    suspects = [{"tag": tag, "base": tags[i - 1][0] if i else None, "time": ts}   # KEY: base = previous tag, for the diff
                for i, (tag, ts) in enumerate(tags) if first - SUSPECT_BEFORE_S <= ts <= first + SUSPECT_AFTER_S][-MAX_SUSPECTS:]
    if not suspects:   # KEY: no deploy near the alert points to infra (playbook step 3)
        prev = [t for t in tags if t[1] < first]
        detail = "no deploy tag in the 30 min before the first alert"
        if prev:
            detail += f"; previous deploy {prev[-1][0]} was {(first - prev[-1][1]) / 3600:.1f} h earlier"
        return {"deploys": [], "findings": [Finding(source="deploys", signal="no recent deploy", detail=detail, severity="medium")]}

    findings = []
    for s in suspects:
        mins = (first - s["time"]) / 60
        when = f"{mins:.1f} min before" if mins >= 0 else f"{-mins:.1f} min after"
        findings.append(Finding(source="deploys", signal=s["tag"], severity="high",
                                detail=f"{s['tag']} deployed at {hms(s['time'])}, {when} the first alert (previous tag {s['base']})"))
    return {"deploys": suspects, "findings": findings}


def diff_agent(state: RCAState) -> dict:
    deploys = [d for d in state.get("deploys", []) if d["base"]]
    if not deploys:
        return {"findings": []}   # nothing to diff: no LLM call
    parts, budget = [], MAX_PATCH_TOTAL
    try:
        for d in deploys:
            files = [f for f in compare(d["base"], d["tag"])
                     if not f["filename"].startswith(IGNORE) and not f["filename"].endswith(".md")]
            parts.append(f"### {d['tag']} (previous {d['base']}): " + (", ".join(f["filename"] for f in files) or "no shop files changed"))
            for f in files:
                patch = f.get("patch", "")[:min(MAX_PATCH_FILE, budget)]   # KEY: hard cap on what the LLM sees
                if patch:
                    parts.append(f"--- {f['filename']}\n{patch}")
                    budget -= len(patch)
    except Exception as exc:
        logger.warning("diff unavailable: %s", exc)
        return {"findings": [Finding(source="diff", signal="diff unavailable", detail=str(exc)[:200], severity="low")]}

    if budget == MAX_PATCH_TOTAL:   # no shop patches at all
        return {"findings": [Finding(source="diff", signal="no shop changes", detail=" | ".join(parts), severity="low")]}
    try:
        drafts = get_llm("diff", schema=FindingList).invoke(DIFF_PROMPT.invoke({"diffs": "\n".join(parts)})).findings[:4]
        findings = [Finding(source="diff", signal=f"{deploys[-1]['tag']}: {d.signal}", detail=d.detail, severity=d.severity) for d in drafts]
    except Exception as exc:
        logger.warning("diff LLM failed: %s", exc)
        findings = [Finding(source="diff", signal="changed files", detail=" | ".join(p for p in parts if p.startswith("###")), severity="medium")]
    return {"findings": findings, "llm_calls": 1}
