import json

from redis import Redis

from core.config import settings
from core.constants import RedisKeys

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class CacheService:
    TTL = settings.session_ttl_seconds

    def __init__(self):
        self.redis = redis_client

    def cache_chunks(self, conversation_id: str, chunks: list):
        """Caches retrieved chunks for a conversation using the session TTL."""
        key = RedisKeys.rag_chunks(conversation_id)
        existing = self.get_cached_chunks(conversation_id)

        # Deduplicate and append
        all_chunks = list(set(existing + chunks))
        self.redis.set(key, json.dumps(all_chunks), ex=self.TTL)

    def get_cached_chunks(self, conversation_id: str) -> list:
        """Retrieves cached chunks. Refreshes TTL if accessed."""
        key = RedisKeys.rag_chunks(conversation_id)
        data = self.redis.get(key)
        if data:
            self.redis.expire(key, self.TTL)
            return json.loads(data)
        return []


cache = CacheService()
