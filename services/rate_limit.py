import hashlib

from fastapi import HTTPException, Request
from redis import Redis

from core.config import settings
from core.constants import RedisKeys

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class RateLimitService:
    def __init__(self):
        self.redis = redis_client

    def generate_fingerprint(self, request: Request) -> str:
        """Generates a device fingerprint by hashing standard request headers and IP."""
        user_agent = request.headers.get("user-agent", "")
        accept_lang = request.headers.get("accept-language", "")
        ip = request.client.host if request.client else "unknown"

        raw_fingerprint = f"{ip}|{user_agent}|{accept_lang}"
        return hashlib.sha256(raw_fingerprint.encode()).hexdigest()

    def check_rate_limit(self, request: Request):
        """
        Enforces a strict threshold of queries per window.
        Raises HTTPException 429 if exceeded.
        """
        fingerprint = self.generate_fingerprint(request)
        key = RedisKeys.rate_limit_window(fingerprint)

        current = self.redis.get(key)
        if current and int(current) >= settings.rate_limit_max_queries:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {settings.rate_limit_max_queries} queries allowed.",
            )

        pipe = self.redis.pipeline()
        pipe.incr(key)
        if not current:
            pipe.expire(key, settings.rate_limit_window_seconds)
        pipe.execute()

        return fingerprint


rate_limit = RateLimitService()
