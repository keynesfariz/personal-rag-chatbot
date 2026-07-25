from pinecone import Pinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from services.cache import cache
from core.config import settings

# Initialize Pinecone
try:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)
except Exception as e:
    # Handle cases where API keys are not set yet during development
    index = None

# Initialize Embeddings
try:
    embedding_model = "gemini-embedding-2"
    embeddings = GoogleGenerativeAIEmbeddings(
        google_api_key=settings.gemini_api_key,
        model=embedding_model
    )
    from services.cache import redis_client
    redis_client.set("cached_embedding_model", f"Gemini ({embedding_model})")
except Exception:
    embeddings = None

class RAGService:
    def get_context(self, query: str, conversation_id: str) -> str:
        """Retrieves relevant context from Pinecone and caches it via Redis."""
        if not index or not embeddings:
            return "Knowledge base is currently unavailable."

        # 1. Embed query
        query_embedding = embeddings.embed_query(query)
        
        # 2. Query Pinecone
        response = index.query(
            vector=query_embedding,
            top_k=5,
            include_metadata=True
        )
        
        new_chunks = []
        for match in response.matches:
            if match.metadata and "text" in match.metadata:
                new_chunks.append(match.metadata["text"])
                
        # 3. Cache new chunks for this conversation
        if new_chunks:
            cache.cache_chunks(conversation_id, new_chunks)
            
        # 4. Retrieve all aggregated context for this conversation (includes past queries' context)
        all_chunks = cache.get_cached_chunks(conversation_id)
        
        # Format context
        return "\n\n".join(all_chunks)

rag = RAGService()
