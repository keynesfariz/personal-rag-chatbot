from fastapi import APIRouter, HTTPException, Request

from services.db import db
from services.rate_limit import rate_limit

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/")
async def get_conversations(request: Request):
    fingerprint = rate_limit.generate_fingerprint(request)
    try:
        conversations = db.get_conversations(fingerprint)
        return {"status": "success", "conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}")
async def get_conversation_history(conversation_id: str, request: Request):
    fingerprint = rate_limit.generate_fingerprint(request)

    # Optional security: ensure this conversation belongs to this fingerprint
    try:
        conversations = db.get_conversations(fingerprint)
        if not any(c["id"] == conversation_id for c in conversations):
            raise HTTPException(
                status_code=403, detail="Not authorized to access this conversation"
            )

        messages = db.get_conversation_history(conversation_id)
        return {"status": "success", "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
