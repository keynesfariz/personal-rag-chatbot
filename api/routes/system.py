from fastapi import APIRouter

from core.config import settings
from core.constants import RedisKeys
from services.cache import redis_client

router = APIRouter(prefix="/system", tags=["system"])

@router.get("/info")
async def get_system_info():
    try:
        llm_model = redis_client.get(RedisKeys.CACHED_LLM_MODEL) or "Unknown"
        embedding_model = redis_client.get(RedisKeys.CACHED_EMBEDDING_MODEL) or "Unknown"
        latest_ingestion = redis_client.get(RedisKeys.LATEST_INGESTION_DATE) or "Never"

        return {
            "llm_model": llm_model,
            "embedding_model": embedding_model,
            "latest_ingestion_date": latest_ingestion,
            "session_ttl": settings.session_ttl_seconds,
            "bot_name": settings.bot_name,
            "owner_name": settings.owner_name,
        }
    except Exception:
        return {
            "llm_model": "Unknown",
            "embedding_model": "Unknown",
            "latest_ingestion_date": "Never",
            "session_ttl": settings.session_ttl_seconds,
            "bot_name": settings.bot_name,
            "owner_name": settings.owner_name,
        }
