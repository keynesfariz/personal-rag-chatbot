import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from core.config import settings
from services.db import db
from services.llm_factory import LLMFactory
from services.rag import rag
from services.rate_limit import rate_limit

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


@router.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequest):
    # 1. Rate Limiting (Raises 429 if exceeded)
    fingerprint = rate_limit.check_rate_limit(request)

    # 2. Conversation management
    conversation_id = body.conversation_id
    if not conversation_id:
        try:
            conversation_id = db.create_conversation(
                ip_address=request.client.host if request.client else "unknown",
                device_fingerprint=fingerprint,
                topic=body.message[:50],
            )
        except Exception:
            # Fallback if DB is not configured yet
            import uuid

            conversation_id = str(uuid.uuid4())

    # 3. Retrieve Context
    context = rag.get_context(body.message, conversation_id)
    print(context)

    # 4. Formulate Prompt
    try:
        llm = LLMFactory.get_llm(provider="gemini")
    except Exception:
        # Fallback to groq if gemini is not configured
        llm = LLMFactory.get_llm(provider="groq")

    system_prompt = (
        f"You are {settings.bot_name}, an AI chatbot answering questions about {settings.owner_name}. "
        "Use the following context to answer the user's question accurately. "
        "If you don't know the answer based on the context, say so gracefully.\n\n"
        f"Context:\n{context}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=body.message),
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

                text_content = ""
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            text_content += block["text"]
                        elif isinstance(block, str):
                            text_content += block
                elif isinstance(content, str):
                    text_content = content

                if text_content:
                    full_response += text_content
                    yield f"data: {json.dumps({'text': text_content, 'conversation_id': conversation_id})}\n\n"
                    await asyncio.sleep(0.01)

            # Log Assistant Message after completion
            try:
                db.log_message(conversation_id, "assistant", full_response)
            except Exception:
                pass

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
