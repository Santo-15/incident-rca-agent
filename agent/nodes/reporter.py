# reporter: final markdown report. No LLM: the content is already structured, and fixes come from the playbook, not invented.
from agent.state import RCAState

FIXES = {   # from docs/playbook.md "Fixes"; the 5 new causes are deliberately NOT in the playbook (unseen scenarios for the rule baseline)
    "db_pool_exhausted": 'git revert <bad commit> + ./deploy.sh "rollback ..."',
    "memory_leak": 'git revert <bad commit> + ./deploy.sh "rollback ..."',
    "postgres_down": "docker compose start postgres; shop-api reconnects (pool_pre_ping)",
    "redis_down": "docker compose start redis; carts return from AOF",
    "slow_query": "CREATE INDEX ix_products_price ON products (price);",
    "shop_api_down": "docker compose start shop-api",                                   # NEW
    "db_lock": "find the blocker in pg_stat_activity (oldest xact_start), then SELECT pg_terminate_backend(<pid>);",   # NEW
    "redis_out_of_memory": "redis-cli CONFIG SET maxmemory 0 (or raise it), then find what filled Redis",              # NEW
    "wrong_service_address": 'git revert <bad commit> + ./deploy.sh "rollback ..."',   # NEW
    "code_exception": 'git revert <bad commit> + ./deploy.sh "rollback ..."',          # NEW
    "insufficient_evidence": "no fix suggested: check the deciding signal named in the summary",
    "other": "no playbook fix: see the summary for the suspected cause",   # NEW
}   # KEY: every Cause needs a key here, or FIXES[h['cause']] raises KeyError at the very last node and the whole run crashes


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
