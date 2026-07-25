import uuid
from typing import Optional, List, Dict
from supabase import create_client, Client
from datetime import datetime, timezone
from core.config import settings

class SupabaseDB:
    def __init__(self):
        self.supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

    def create_conversation(
        self,
        guest_token: str,
        ip_address: str,
        device_fingerprint: str,
        topic: Optional[str] = None
    ) -> str:
        """Creates a new conversation and returns its UUID."""
        conversation_id = str(uuid.uuid4())
        data, count = self.supabase.table("conversations").insert({
            "id": conversation_id,
            "guest_token": guest_token,
            "ip_address": ip_address,
            "device_fingerprint": device_fingerprint,
            "topic": topic
        }).execute()
        return conversation_id

    def end_conversation(self, conversation_id: str) -> None:
        """Sets the ended_at timestamp for a conversation."""
        now = datetime.now(timezone.utc).isoformat()
        self.supabase.table("conversations").update({
            "ended_at": now
        }).eq("id", conversation_id).execute()

    def log_message(self, conversation_id: str, role: str, content: str) -> None:
        """Logs a single message into the messages table."""
        self.supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content
        }).execute()

    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Retrieves all messages for a specific conversation in chronological order."""
        response = self.supabase.table("messages") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .order("created_at") \
            .execute()
        return response.data

    def get_conversations(self, guest_token: str) -> List[Dict]:
        """Retrieves a list of conversations for a given guest token."""
        response = self.supabase.table("conversations") \
            .select("*") \
            .eq("guest_token", guest_token) \
            .order("created_at", desc=True) \
            .execute()
        return response.data

db = SupabaseDB()
