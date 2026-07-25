import json
import hmac
import hashlib
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from core.config import settings
from services.rate_limit import rate_limit
from services.rag import rag
from services.llm_factory import LLMFactory
from services.db import db
from services.ingest import ingestor
from services.cache import redis_client
from langchain_core.messages import HumanMessage, SystemMessage

app = FastAPI(title="Keynesfariz RAG QA (Farsisstant)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

@app.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequest):
    # 1. Rate Limiting (Raises 429 if exceeded)
    fingerprint = rate_limit.check_rate_limit(request)
    
    # 2. Conversation management
    conversation_id = body.conversation_id
    if not conversation_id:
        try:
            conversation_id = db.create_conversation(
                guest_token=request.headers.get("x-guest-token", ""),
                ip_address=request.client.host if request.client else "unknown",
                device_fingerprint=fingerprint,
                topic=body.message[:50]
            )
        except Exception:
            # Fallback if DB is not configured yet
            import uuid
            conversation_id = str(uuid.uuid4())
            
    # 3. Retrieve Context
    context = rag.get_context(body.message, conversation_id)
    
    # 4. Formulate Prompt
    try:
        llm = LLMFactory.get_llm(provider="groq")
    except Exception:
        # Fallback to gemini if groq is not configured
        llm = LLMFactory.get_llm(provider="gemini")
    
    system_prompt = (
        "You are Farsisstant, an AI chatbot answering questions about Fariz (or Faris). "
        "Use the following context to answer the user's question accurately. "
        "If you don't know the answer based on the context, say so gracefully.\n\n"
        f"Context:\n{context}"
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=body.message)
    ]
    
    # 5. Log User Message
    try:
        db.log_message(conversation_id, "user", body.message)
    except Exception:
        pass
    
    # 6. Stream Response via SSE
    async def generate():
        full_response = ""
        try:
            async for chunk in llm.astream(messages):
                content = chunk.content
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'text': content, 'conversation_id': conversation_id})}\n\n"
                    
            # Log Assistant Message after completion
            try:
                db.log_message(conversation_id, "assistant", full_response)
            except Exception:
                pass
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/webhooks/github")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")
        
    payload_body = await request.body()
    
    # Verify signature
    signature = hmac.new(
        settings.github_webhook_secret.encode(),
        payload_body,
        hashlib.sha256
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
    redis_client.set("latest_ingestion_date", now)
    
    return {"status": "success"}

@app.get("/ingestion/latest")
async def get_latest_ingestion():
    try:
        date = redis_client.get("latest_ingestion_date")
        return {"latest_ingestion_date": date or "Never"}
    except Exception:
        return {"latest_ingestion_date": "Never"}

@app.get("/system/info")
async def get_system_info():
    try:
        llm_model = redis_client.get("cached_llm_model") or "Unknown"
        embedding_model = redis_client.get("cached_embedding_model") or "Unknown"
        return {
            "llm_model": llm_model,
            "embedding_model": embedding_model
        }
    except Exception:
        return {"llm_model": "Unknown", "embedding_model": "Unknown"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
