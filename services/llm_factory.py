from typing import Literal
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from core.config import settings
from services.cache import redis_client

Provider = Literal["groq", "gemini"]

class LLMFactory:
    @staticmethod
    def get_llm(provider: Provider = "gemini", temperature: float = 0.7) -> BaseChatModel:
        if provider == "groq":
            if not settings.groq_api_key:
                raise ValueError("GROQ_API_KEY is not set.")
            model_name = "openai/gpt-oss-20b"
            redis_client.set("cached_llm_model", f"Groq ({model_name})")
            return ChatGroq(
                api_key=settings.groq_api_key,
                model_name=model_name,
                temperature=temperature,
            )
            
        elif provider == "gemini":
            if not settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not set.")
            model_name = "gemini-3.5-flash-lite"
            redis_client.set("cached_llm_model", f"Gemini ({model_name})")
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model=model_name,
                temperature=temperature,
            )
            
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
