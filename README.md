# Keynesfariz RAG QA (Farsisstant Backend)

This is the backend API for **Farsisstant**, a personal AI chatbot integrated with a Retrieval-Augmented Generation (RAG) system. It allows users in the tech community to ask questions about keynesfariz by seamlessly ingesting data directly from GitHub repositories.

## Tech Stack

- **Framework:** FastAPI
- **LLM Orchestration:** LangChain (Support for Groq and Gemini)
- **Vector Database:** Pinecone
- **Relational Database:** Supabase (Conversation & Message History)
- **Cache & Rate Limiting:** Upstash Redis

## Features

- **SSE Streaming:** Real-time text streaming via Server-Sent Events (`/chat`).
- **Automated Ingestion:** Integrates with GitHub Webhooks to automatically embed and upsert new/modified `.md` and `.json` files.
- **Advanced Rate Limiting:** Configurable limits (default 30 queries/week) enforced by hashing `user-agent`, `accept-language`, `ip_address`.
- **Context Caching:** Conversation chunks are temporarily cached in Redis (2-hour TTL) to maintain context for follow-up questions.
- **Provider Interchangeability:** Easily switch between LLM providers using the Factory Method pattern.

## Prerequisites

- Python 3.10+ (minimum requirement for Gemini models)
- [Supabase](https://supabase.com) Project (PostgreSQL)
- [Pinecone](https://pinecone.io) Index
- [Upstash Redis](https://upstash.com) Database
- API Keys for Groq or Gemini

## Setup Instructions

### 1. Environment Setup

Clone the repository, then copy the environment template:

```bash
cp .env.example .env
```

Fill in the `.env` file with your specific database credentials, webhook secrets, and API keys.

#### Key Configuration Variables
- `BOT_NAME`: The name of the assistant (default: `Farsisstant`).
- `OWNER_NAME`: The name of the persona the assistant answers questions about (default: `Fariz`).
- `RATE_LIMIT_WEEK_SECONDS`: The duration for the rate limit window in seconds (default: `604800` for 1 week).
- `RATE_LIMIT_MAX_QUERIES`: The maximum allowed queries within the rate limit window (default: `30`).

### 2. Database Migration

Navigate to your Supabase SQL Editor and execute the SQL script provided in `schema.sql`. This will create the necessary `conversations` and `messages` tables.

### 3. Install Dependencies

Set up the virtual environment and install the required Python packages:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

_(Note: If you use VS Code, ensure `"python.terminal.useEnvFile": true` is set in your workspace settings to auto-inject the `.env`)._

## Running the Server

Start the local FastAPI development server using Uvicorn:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## API Endpoints

- **`POST /chat`**
  Expects `{"message": "string", "conversation_id": "optional-uuid"}`. Streams the AI response back to the client using SSE.
- **`POST /webhooks/github`**
  Endpoint for GitHub push events. Trigger an initial full-repo ingestion by sending a GitHub "ping" event (created when you first configure the webhook in GitHub).
- **`GET /system/info`**
  Returns the currently active LLM and Embedding models fetched from the Redis cache.

- **`GET /ingestion/latest`**
  Returns the timestamp of the last successful knowledge base ingestion.
