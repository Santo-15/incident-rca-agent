import time
from langchain_core.messages import HumanMessage, SystemMessage
from agent.llm import get_llm

messages=[
    SystemMessage("You are an SRE assistant. Answer in one short sentence."), 
    HumanMessage("Logs: failed to resolve host 'postgres' (x480), Connection refused (x20). "
                 "Most likely root cause?")
]

def text_of(msg):
    if isinstance(msg.content, str):
        return msg.content
    return "".join(p.get("text", "") for p in msg.content if isinstance(p, dict))

for provider in ("groq", "gemini"):
    llm = get_llm(provider)
    start = time.perf_counter()
    reply = llm.invoke(messages)
    secs = time.perf_counter() - start
    print(f"\n[{provider}] {secs:.1f}s  reply type={type(reply).__name__}")
    print("  answer:", text_of(reply).strip())
    print("  usage :", reply.usage_metadata)