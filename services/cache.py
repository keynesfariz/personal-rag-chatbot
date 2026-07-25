import json
from redis import Redis
from core.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

class CacheService:
    TTL = 7200  # 2 hours in seconds

    def __init__(self):
        self.redis = redis_client

    def cache_chunks(self, conversation_id: str, chunks: list):
        """Caches retrieved chunks for a conversation with a 2-hour TTL."""
        key = f"rag_chunks:{conversation_id}"
        existing = self.get_cached_chunks(conversation_id)
        
        # Deduplicate and append
        all_chunks = list(set(existing + chunks))
        self.redis.set(key, json.dumps(all_chunks), ex=self.TTL)

    def get_cached_chunks(self, conversation_id: str) -> list:
        """Retrieves cached chunks. Refreshes TTL to 2 hours if accessed."""
        key = f"rag_chunks:{conversation_id}"
        data = self.redis.get(key)
        if data:
            self.redis.expire(key, self.TTL)
            return json.loads(data)
        return []

cache = CacheService()
