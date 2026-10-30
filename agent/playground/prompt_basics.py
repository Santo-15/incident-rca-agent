from agent.llm import get_llm
from agent.prompts.correlator import CORRELATOR_PROMPT

evidence = {
    "alerts": "PostgresDown at 23:37:22, ShopHigh5xxRatio at ~23:39:30",
    "silent": "ShopApiDown, RedisDown",
    "logs": "\"failed to resolve host 'postgres'\" x480; \"Connection refused\" x20",
    "metrics": "postgres DOWN, shop-api UP, redis UP; 5xx ~90% on all paths that use the DB; p95 ~9 s",
    "deploys": "deploy-20261026-233500 at 23:35, 2 minutes before the first alert; diff changes only README.md",
}

messages = CORRELATOR_PROMPT.format_messages(**evidence)
for m in messages:
    print(f"--- {m.type} ---\n{m.content}\n")

chain = CORRELATOR_PROMPT | get_llm()
reply = chain.invoke(evidence)
print("=== answer ===\n" + reply.content) 