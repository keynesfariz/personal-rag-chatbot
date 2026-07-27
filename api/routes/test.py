import logging

from fastapi import APIRouter, HTTPException
from pinecone import Pinecone
from pydantic import BaseModel

from core.config import settings

router = APIRouter(prefix="/test", tags=["test"])
logger = logging.getLogger("uvicorn.error")


class TestUpsertRequest(BaseModel):
    id: str
    text: str


@router.post("/upsert")
async def test_upsert(body: TestUpsertRequest):
    if settings.environment != "development":
        raise HTTPException(status_code=403, detail="Not allowed")

    try:
        logger.info("Initializing Pinecone for test upsert...")
        pc = Pinecone(api_key=settings.pinecone_api_key)
        test_index = pc.Index(settings.pinecone_index_name)

        logger.info(f"Upserting test record with id: {body.id}")
        test_index.upsert_records(
            namespace=settings.pinecone_namespace,
            records=[{"id": body.id, "text": body.text}],
        )
        return {"status": "success", "message": "Record upserted successfully"}
    except Exception as e:
        logger.error(f"Test upsert failed: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/delete-records")
async def test_delete_records():
    if settings.environment != "development":
        raise HTTPException(status_code=403, detail="Not allowed")

    try:
        logger.info("Initializing Pinecone for test delete...")
        pc = Pinecone(api_key=settings.pinecone_api_key)
        test_index = pc.Index(settings.pinecone_index_name)

        logger.info(f"Deleting test records...")
        test_index.delete(delete_all=True, namespace=settings.pinecone_namespace)
        return {"status": "success", "message": "Records deleted successfully"}
    except Exception as e:
        logger.error(f"Test delete failed: {str(e)}")
        return {"status": "error", "message": str(e)}
