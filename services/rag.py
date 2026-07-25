from pinecone import Pinecone
from services.cache import cache
from core.config import settings
from services.cache import redis_client

# Initialize Pinecone
try:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)
except Exception as e:
    # Handle cases where API keys are not set yet during development
    index = None

# Cache the model name for the frontend
try:
    desc = pc.indexes.describe(settings.pinecone_index_name)
    model_name = "Pinecone Integrated Inference"
    if hasattr(desc, "spec") and hasattr(desc.spec, "integrated") and hasattr(desc.spec.integrated, "embed"):
        model_name = f"Pinecone ({desc.spec.integrated.embed.model})"
    redis_client.set("cached_embedding_model", model_name)
except Exception:
    redis_client.set("cached_embedding_model", "Pinecone Integrated Inference")

class RAGService:
    def get_context(self, query: str, conversation_id: str) -> str:
        """Retrieves relevant context from Pinecone and caches it via Redis."""
        if not index:
            return "Knowledge base is currently unavailable."

        # 1. Query Pinecone Integrated Inference directly with text
        response = index.search(
            namespace="",
            top_k=5,
            inputs={"text": query}
        )
        
        # Robustly extract hits based on SDK version
        hits = response.get('hits', []) if isinstance(response, dict) else (response.hits if hasattr(response, 'hits') else response.result.hits)
        
        new_chunks = []
        for hit in hits:
            # Extract fields/metadata robustly
            fields = getattr(hit, 'fields', {}) or getattr(hit, 'metadata', {})
            if isinstance(hit, dict):
                fields = hit.get('fields', hit.get('metadata', {}))
                
            if fields and "text" in fields:
                new_chunks.append(fields["text"])
                
        # 3. Cache new chunks for this conversation
        if new_chunks:
            cache.cache_chunks(conversation_id, new_chunks)
            
        # 4. Retrieve all aggregated context for this conversation (includes past queries' context)
        all_chunks = cache.get_cached_chunks(conversation_id)
        
        # Format context
        return "\n\n".join(all_chunks)

rag = RAGService()
