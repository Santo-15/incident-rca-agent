import logging, os, sys, time                      

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")  
if "--groq-down" in sys.argv:                      
    os.environ["GROQ_API_KEY"] = "gsk_fake_key_groq_is_down"   

from agent.llm import get_llm                     
from agent.prompts.correlator import CORRELATOR_PROMPT
from agent.schemas import CorrelatorAnswer

evidence = {                                        
    "alerts": "PostgresDown at 23:37:22, ShopHigh5xxRatio at ~23:39:30",
    "silent": "ShopApiDown, RedisDown",
    "logs": "\"failed to resolve host 'postgres'\" x480; \"Connection refused\" x20",
    "metrics": "postgres DOWN, shop-api UP, redis UP; 5xx ~90% on all paths that use the DB",
    "deploys": "none; newest tag over an hour before the first alert",
}

for role in ("correlator", "logs", "triage"):       
    chain = CORRELATOR_PROMPT | get_llm(role, schema=CorrelatorAnswer)   
    start = time.perf_counter()
    answer = chain.invoke(evidence)
    print(f"[{role:10}] {time.perf_counter() - start:5.1f}s  cause={answer.cause}  confidence={answer.confidence}")