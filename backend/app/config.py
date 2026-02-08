"""Application configuration"""

from pydantic import BaseModel, validator
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)


class Config(BaseModel):
    # Ollama Configuration
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "all-minilm:latest")
    GEN_MODEL: str = os.getenv("GEN_MODEL", "codellama:latest")

    # Directories
    C_PROJECT_DIR: Path = Path(os.getenv("C_PROJECT_DIR", "./c_projects"))
    TEST_EXAMPLES_DIR: Path = Path(os.getenv("TEST_EXAMPLES_DIR", "./test_examples"))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./generated_tests"))

    # Database
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", "./data/cpputest.db"))

    # Chunk settings for large projects
    MAX_FUNCTIONS_PER_CHUNK: int = int(os.getenv("MAX_FUNCTIONS_PER_CHUNK", "10"))

    # Retrieval settings
    TOP_K: int = int(os.getenv("TOP_K", "3"))

    # Index files
    INDEX_FILE: str = "test_examples.index"
    META_FILE: str = "test_examples_meta.pkl"
    HASH_FILE: str = "examples_hash.json"

    # Performance settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "5"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "180"))

    @validator('C_PROJECT_DIR', 'TEST_EXAMPLES_DIR', 'OUTPUT_DIR')
    def ensure_dirs_exist(cls, v):
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {v}")
        return v

    @validator('DATABASE_PATH')
    def ensure_db_dir_exists(cls, v):
        if not v.parent.exists():
            v.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {v.parent}")
        return v


config = Config()
