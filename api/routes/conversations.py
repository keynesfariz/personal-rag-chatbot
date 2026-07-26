from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from core.config import settings
from services.db import db
from services.rate_limit import rate_limit

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
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
        conversation = next((c for c in conversations if c["id"] == conversation_id), None)
        if not conversation:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this conversation"
            )

        messages = db.get_conversation_history(conversation_id)
        
        # Calculate expires_at
        expires_at = None
        if messages:
            last_msg_time = datetime.fromisoformat(messages[-1]["created_at"].replace("Z", "+00:00"))
            expires_at = (last_msg_time + timedelta(seconds=settings.session_ttl_seconds)).isoformat()
        else:
            conv_time = datetime.fromisoformat(conversation["created_at"].replace("Z", "+00:00"))
            expires_at = (conv_time + timedelta(seconds=settings.session_ttl_seconds)).isoformat()
            
        return {"status": "success", "messages": messages, "expires_at": expires_at}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
