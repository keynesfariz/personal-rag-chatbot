import hashlib

from fastapi import HTTPException, Request
from redis import Redis

from core.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class RateLimitService:
    WEEK_SECONDS = 7 * 24 * 3600  # 7 days; 24 hours, 3600 seconds
    MAX_QUERIES = 30

    def __init__(self):
        self.redis = redis_client

    def generate_fingerprint(self, request: Request) -> str:
        """Generates a guest token fingerprint by hashing standard request headers and IP."""
        user_agent = request.headers.get("user-agent", "")
        accept_lang = request.headers.get("accept-language", "")
        # Look for custom guest token header or cookie if present
        guest_token = request.headers.get(
            "x-guest-token", request.cookies.get("guest_token", "")
        )
        ip = request.client.host if request.client else "unknown"

        raw_fingerprint = f"{ip}|{user_agent}|{accept_lang}|{guest_token}"
        return hashlib.sha256(raw_fingerprint.encode()).hexdigest()

    def check_rate_limit(self, request: Request):
        """
        Enforces a strict threshold of 30 queries per week.
        Raises HTTPException 429 if exceeded.
        """
        fingerprint = self.generate_fingerprint(request)
        key = f"rate_limit:week:{fingerprint}"

        current = self.redis.get(key)
        if current and int(current) >= self.MAX_QUERIES:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Maximum 30 queries per week.",
            )

        pipe = self.redis.pipeline()
        pipe.incr(key)
        if not current:
            pipe.expire(key, self.WEEK_SECONDS)
        pipe.execute()

        return fingerprint


rate_limit = RateLimitService()
