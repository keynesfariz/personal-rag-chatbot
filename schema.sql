-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create conversations table
CREATE TABLE public.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_address TEXT,
    device_fingerprint TEXT,
    topic TEXT,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create messages table
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX idx_conversations_device_fingerprint ON public.conversations(device_fingerprint);
CREATE INDEX idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX idx_messages_created_at ON public.messages(created_at);

-- 1. Create indexes to optimize the JOIN and WHERE clauses
CREATE INDEX IF NOT EXISTS idx_conversations_fingerprint 
ON conversations (device_fingerprint);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
ON messages (conversation_id);

-- 2. Create the RPC function to fetch conversations with expires_at
CREATE OR REPLACE FUNCTION get_conversations_summary(
    p_device_fingerprint TEXT,
    p_session_ttl_seconds INT
)
RETURNS TABLE (
    id UUID,
    topic TEXT,
    device_fingerprint TEXT,
    created_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
)
LANGUAGE sql
AS $$
    SELECT 
        c.id,
        c.topic,
        c.device_fingerprint,
        c.created_at,
        COALESCE(MAX(m.created_at), c.created_at) + (p_session_ttl_seconds || ' seconds')::interval AS expires_at
    FROM conversations c
    LEFT JOIN messages m ON c.id = m.conversation_id
    WHERE c.device_fingerprint = p_device_fingerprint
    GROUP BY c.id
    ORDER BY COALESCE(MAX(m.created_at), c.created_at) DESC;
$$;
