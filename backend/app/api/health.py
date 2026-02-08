"""Health and debug endpoints"""

from fastapi import APIRouter

from app.config import config
from app.services import rag_engine

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "ollama_url": config.OLLAMA_URL,
        "model": config.GEN_MODEL,
        "index_loaded": rag_engine.index is not None,
        "examples_count": len(rag_engine.test_examples_metadata.get("texts", []))
    }
