# One place that builds LLMs for every agent: model per role, timeouts, Groq -> Google fallback  # what this file is for
import logging                                     
from dotenv import load_dotenv, find_dotenv         
from langchain_core.language_models import BaseChatModel   
from langchain_core.runnables import Runnable, RunnableLambda   
from langchain_google_genai import ChatGoogleGenerativeAI   
from langchain_groq import ChatGroq                 

load_dotenv(find_dotenv())                          
logger = logging.getLogger("agent.llm")             
TIMEOUT_S = 30                                     

ROLES = {                                          
    "correlator": (("groq", "openai/gpt-oss-120b"), ("gemini", "gemini-3.5-flash-lite")),   
    "critic":     (("groq", "openai/gpt-oss-120b"), ("gemini", "gemini-3.5-flash-lite")),
    "logs":       (("groq", "openai/gpt-oss-20b"),  ("gemini", "gemini-3.1-flash-lite")),   
    "diff":       (("groq", "openai/gpt-oss-20b"),  ("gemini", "gemini-3.1-flash-lite")),
    "triage":     (("groq", "qwen/qwen3.8-27b"),    ("gemini", "gemini-3.1-flash-lite")),          
    "reporter":   (("groq", "qwen/qwen3.8-27b"),    ("gemini", "gemini-3.1-flash-lite")),
}


def build_model(provider: str, model: str, temperature: float = 0) -> BaseChatModel:   
    if provider == "groq":
        extra = {"reasoning_effort": "low"} if model.startswith("openai/gpt-oss") else {}  
        return ChatGroq(model=model, temperature=temperature, timeout=TIMEOUT_S, max_retries=2, **extra)   
    if provider == "gemini":
        return ChatGoogleGenerativeAI(model=model, temperature=temperature, timeout=TIMEOUT_S, max_retries=2)
    raise ValueError(f"unknown provider: {provider}")   


def _shape(llm: BaseChatModel, schema=None, tools=None) -> Runnable:
    if schema is not None:
        if isinstance(llm, ChatGroq) and llm.model_name.startswith("openai/gpt-oss"):   # KEY: only gpt-oss on Groq gets strict json_schema
            return llm.with_structured_output(schema, method="json_schema", strict=True)  # KEY: Groq enforces the schema, so the model can't echo it
        return llm.with_structured_output(schema)   # Gemini / other models keep the default method
    if tools:
        return llm.bind_tools(tools)
    return llm

def _log_failures(primary, role):
    def call(x, config=None):
        try:
            return primary.invoke(x, config=config)
        except Exception as e:
            logger.warning("primary failed role=%s: %r", role, e)  # KEY: real error; uses your `logger`
            raise                                                 # KEY: re-raise so the fallback still runs
    return RunnableLambda(call)


def get_llm(role: str = "correlator", schema=None, tools=None) -> Runnable:
    (p_prov, p_model), (f_prov, f_model) = ROLES[role]
    primary = _shape(build_model(p_prov, p_model), schema, tools)
    fallback = _shape(build_model(f_prov, f_model), schema, tools)

    def run_fallback(inp):
        logger.warning("fallback role=%s: %s:%s failed -> using %s:%s", role, p_prov, p_model, f_prov, f_model)
        return fallback.invoke(inp)

    return _log_failures(primary, role).with_fallbacks([RunnableLambda(run_fallback)])  # KEY: wrapper now in the chain