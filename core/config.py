from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

env_file = (".env", ".env.local")


class Settings(BaseSettings):
    # Server Configuration
    port: int = 8000
    environment: str = "development"
    allowed_origins: str = "https://keynesfariz.github.io,http://localhost:3000"

    # Redis Configuration
    redis_url: str

    # Supabase Configuration
    supabase_url: str
    supabase_key: str

    # Pinecone Configuration
    pinecone_api_key: str
    pinecone_index_name: str = "keynesfariz-rag"
    pinecone_namespace: str = "__default__"

    # LLM API Keys
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None

    # Embeddings API Key
    jina_api_key: Optional[str] = None

    # Webhook Secret & PAT
    github_webhook_secret: str
    github_pat: Optional[str] = None

    model_config = SettingsConfigDict(env_file=env_file, env_file_encoding="utf-8")


settings = Settings()
