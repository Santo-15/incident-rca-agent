import os
from dotenv import load_dotenv, find_dotenv
from groq import Groq

load_dotenv(find_dotenv())
client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

ERROR_LINE = "OperationalError: (psycopg.OperationalError) failed to resolve host 'postgres': [Errno -2] Name or service not known"

def ask(prompt, temperature):
    resp = client.chat.completions.create(
    model = MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=temperature,
    max_tokens=400,
    reasoning_effort="low"
    )
    return resp.choices[0].message.content.strip(), resp.usage

# 1. Context window: the most tokens this model can handle in one call (prompt + answer together)
info = next(m for m in client.models.list().data if m.id == MODEL)
print(f"model={MODEL} context_window={getattr(info, 'context_window', 'unknown')} tokens")

# 2. Tokens: the same question with 1 log line vs 50 copies (what dumping raw logs into a prompt does)
question = "In one short sentence, what is the most likely root cause?\nLogs:\n"
for n in (1, 50):
    prompt = question + "\n".join([ERROR_LINE] * n)   
    text, usage = ask(prompt, temperature=0)
    print(f"{n:>2} lines: {len(prompt)} chars -> prompt_tokens={usage.prompt_tokens}, "
          f"completion_tokens={usage.completion_tokens} | {text}")

# 3. Temperature: the same request 3 times at 0 and 3 times at 1.5
for t in (0, 1.5):
    print(f"\ntemperature={t}")
    for _ in range(3):                      
        text, _usage = ask("Give a 5-word title for this incident: " + ERROR_LINE, temperature=t)
        print("  ", text)