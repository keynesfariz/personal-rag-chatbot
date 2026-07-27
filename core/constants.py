class RedisKeys:
    CACHED_LLM_MODEL = "cached_llm_model"
    CACHED_EMBEDDING_MODEL = "cached_embedding_model"
    LATEST_INGESTION_DATE = "latest_ingestion_date"
    LATEST_INGESTION_STATUS = "latest_ingestion_status"

    @staticmethod
    def rag_chunks(conversation_id: str) -> str:
        return f"rag_chunks:{conversation_id}"

    @staticmethod
    def rate_limit_window(fingerprint: str) -> str:
        return f"rate_limit:window:{fingerprint}"
