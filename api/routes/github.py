import hashlib
import hmac


from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks

from core.config import settings
from services.ingest import ingestor

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    folders: str | None = None,
    files: str | None = None,
    read_dependency: bool = False,
    x_hub_signature_256: str = Header(None),
):
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
    folders_list = folders.split(",") if folders else None
    files_list = files.split(",") if files else None

    if "zen" in payload:
        # GitHub ping event (sent on webhook creation)
        repo_full_name = payload["repository"]["full_name"]
        branch = payload.get("repository", {}).get("default_branch", "main")
        background_tasks.add_task(
            ingestor.process_initial_ingestion,
            repo_full_name, branch, folders_list, read_dependency, files_list
        )
    else:
        background_tasks.add_task(
            ingestor.process_webhook_payload,
            payload, folders_list, read_dependency, files_list
        )

    return {"status": "success"}
