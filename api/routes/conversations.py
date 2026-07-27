
from fastapi import APIRouter, HTTPException, Request

from core.config import settings
from services.db import db
from services.rate_limit import rate_limit

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def get_conversations(request: Request):
    fingerprint = rate_limit.generate_fingerprint(request)
    try:
        conversations = db.get_conversations(fingerprint, settings.session_ttl_seconds)
        return {"status": "success", "conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}")
async def get_conversation_history(conversation_id: str, request: Request):
    fingerprint = rate_limit.generate_fingerprint(request)

    # Optional security: ensure this conversation belongs to this fingerprint
    try:
        conversations = db.get_conversations(fingerprint, settings.session_ttl_seconds)
        conversation = next((c for c in conversations if c["id"] == conversation_id), None)
        if not conversation:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this conversation"
            )

        messages = db.get_conversation_history(conversation_id)
        
        expires_at = conversation.get("expires_at")
            
        return {"status": "success", "messages": messages, "expires_at": expires_at}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
