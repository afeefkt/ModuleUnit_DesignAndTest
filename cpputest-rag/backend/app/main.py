"""
CppUTest Generator with RAG — FastAPI Application
Automatic Test Case Generation for C Projects using CodeLlama
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.config import config
from app.database import init_db
from app.api import health, analysis, generation, projects, test_runner
from app.services.rag_engine import build_examples_index
from app.services.example_creator import create_example_cpputest_files

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cpputest_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CppUTest Generator with RAG",
    description="Automatic test case generation for C projects using CodeLlama",
    version="2.0.0"
)

# CORS middleware — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(health.router, tags=["Health"])
app.include_router(analysis.router, tags=["Analysis"])
app.include_router(generation.router, tags=["Generation"])
app.include_router(projects.router, tags=["Projects"])
app.include_router(test_runner.router, tags=["Test Runner"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting CppUTest Generator v2.0...")
    logger.info(f"Ollama URL: {config.OLLAMA_URL}")
    logger.info(f"Code Model: {config.GEN_MODEL}")
    logger.info(f"Database: {config.DATABASE_PATH}")

    # Initialize database
    await init_db(config.DATABASE_PATH)

    # Create example CppUTest files if examples directory is empty
    create_example_cpputest_files()

    # Build FAISS index from examples
    await build_examples_index()

    logger.info("Startup complete")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting CppUTest Generator on {host}:{port}")
    logger.info(f"Project directory: {config.C_PROJECT_DIR}")
    logger.info(f"Examples directory: {config.TEST_EXAMPLES_DIR}")
    logger.info(f"Output directory: {config.OUTPUT_DIR}")

    uvicorn.run(app, host=host, port=port, loop="asyncio")
