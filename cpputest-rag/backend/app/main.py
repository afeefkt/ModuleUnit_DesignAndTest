"""
CppUTest Generator with RAG — FastAPI Application
Automatic Test Case Generation for C Projects using a local LLM (Ollama)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os

from app.config import config
from app.database import init_db
from app.api import health, analysis, generation, projects, test_runner
from app.services.rag_engine import load_or_build_examples_index
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
    description="Automatic test case generation for C projects using a local LLM",
    version="2.0.0"
)

# Browser origins allowed to call this API: the bundled frontend (:3000) and
# the Streamlit Control Center (:8501). Override with CORS_ORIGINS=a,b,c.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8501,http://127.0.0.1:8501",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_foreign_origin_writes(request: Request, call_next):
    """Block cross-site state-changing requests.

    CORS only hides responses; a "simple" cross-site POST (e.g. /run-tests,
    which drives Docker) would still execute. Browsers always send Origin on
    cross-origin POSTs, so refuse any that isn't allow-listed. Non-browser
    clients (bridge, Streamlit server side, curl) send no Origin and pass.
    """
    origin = request.headers.get("origin")
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and origin
        and origin not in ALLOWED_ORIGINS
    ):
        logger.warning(f"Rejected {request.method} {request.url.path} from origin {origin}")
        return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
    return await call_next(request)

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
    await load_or_build_examples_index()

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
