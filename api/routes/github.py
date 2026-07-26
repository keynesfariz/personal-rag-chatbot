import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from core.config import settings
from core.constants import RedisKeys
from services.cache import redis_client
from services.ingest import ingestor

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/github")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")

    payload_body = await request.body()

    # Verify signature
    signature = hmac.new(
        settings.github_webhook_secret.encode(), payload_body, hashlib.sha256
    ).hexdigest()

    expected_signature = f"sha256={signature}"
    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Process asynchronously
    if "zen" in payload:
        # GitHub ping event (sent on webhook creation)
        repo_full_name = payload["repository"]["full_name"]
        branch = payload.get("repository", {}).get("default_branch", "main")
        await ingestor.process_initial_ingestion(repo_full_name, branch)
    else:
        await ingestor.process_webhook_payload(payload)

    # Record latest ingestion date in Redis
    now = datetime.now(timezone.utc).isoformat()
    redis_client.set(RedisKeys.LATEST_INGESTION_DATE, now)

    return {"status": "success"}
