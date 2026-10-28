import os
from dotenv import load_dotenv, find_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv(find_dotenv())

def get_llm(provider: str | None = None, temperature: float = 0) -> BaseChatModel:
    provider = provider or os.getenv("LLM_PROVIDER", "groq")
    if provider == "groq":
        return ChatGroq(
            model=os.environ["GROQ_MODEL"],         
            temperature=temperature,                
            reasoning_effort="low",                 
            max_retries=2,                         
        )
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.environ["GEMINI_MODEL"],       
            temperature=temperature,                
            max_retries=2,
        )                                          
    raise ValueError(f"unknown provider: {provider}")