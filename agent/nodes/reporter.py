# reporter: final markdown report. No LLM: the content is already structured, and fixes come from the playbook, not invented.
from agent.state import RCAState

FIXES = {   # from docs/playbook.md "Fixes"
    "db_pool_exhausted": 'git revert <bad commit> + ./deploy.sh "rollback ..."',
    "memory_leak": 'git revert <bad commit> + ./deploy.sh "rollback ..."',
    "postgres_down": "docker compose start postgres; shop-api reconnects (pool_pre_ping)",
    "redis_down": "docker compose start redis; carts return from AOF",
    "slow_query": "CREATE INDEX ix_products_price ON products (price);",
    "insufficient_evidence": "no fix suggested: check the deciding signal named in the summary",
}


def reporter(state: RCAState) -> dict:
    h = state["hypothesis"]
    evidence = "\n".join(f"- {e}" for e in h["evidence"]) or "- none"
    report = f"""# Incident report
**Root cause:** {h['cause']} (confidence {h['confidence']})
**Summary:** {h['summary']}

**Alerts fired:** {', '.join(state.get('alerts', [])) or 'none'}
**Alerts silent:** {', '.join(state.get('silent', [])) or 'none'}

**Evidence**
{evidence}

**Silent signals:** {h['silent_signals']}
**Deploy:** {h.get('deploy_tag') or 'not deploy-related'}
**Suggested fix (playbook):** {FIXES[h['cause']]}

_Critic: {state.get('critique')} · correlator runs: {state.get('loop_count')} · LLM calls: {state.get('llm_calls', 0)}_"""
    return {"report": report}
