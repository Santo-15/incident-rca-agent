from agent.llm import get_llm
from agent.prompts.correlator import CORRELATOR_PROMPT
from agent.schemas import CorrelatorAnswer

evidence = {
    "alerts": "PostgresDown at 23:37:22, ShopHigh5xxRatio at ~23:39:30",
    "silent": "ShopApiDown, RedisDown",
    "logs": "\"failed to resolve host 'postgres'\" x480; \"Connection refused\" x20",
    "metrics": "postgres DOWN, shop-api UP, redis UP; 5xx ~90% on all paths that use the DB; p95 ~9 s",
    "deploys": "none; newest tag deploy-20261026-165909 at 22:29, over an hour before the first alert",
}

structured_llm = get_llm().with_structured_output(CorrelatorAnswer)
chain = CORRELATOR_PROMPT | structured_llm

answer = chain.invoke(evidence)
print("type      :", type(answer).__name__)
print("cause     :", answer.cause)
print("summary   :", answer.summary)
print("evidence  :", answer.evidence)
print("silent    :", answer.silent_signals)
print("deploy_tag:", answer.deploy_tag)
print("confidence:", answer.confidence)
print("\nas dict:", answer.model_dump()) 