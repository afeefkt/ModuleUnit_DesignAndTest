"""SQLite database layer using aiosqlite"""

import aiosqlite
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Global database instance
_db_path: Path = None


async def init_db(db_path: Path):
    """Initialize database with schema"""
    global _db_path
    _db_path = db_path

    async with aiosqlite.connect(str(_db_path)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                total_files INTEGER NOT NULL,
                total_functions INTEGER NOT NULL,
                functions_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER,
                project_id INTEGER NOT NULL,
                functions_analyzed INTEGER NOT NULL,
                tests_generated INTEGER NOT NULL,
                failed_functions TEXT DEFAULT '[]',
                output_dir TEXT NOT NULL,
                elapsed_seconds REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS test_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
        logger.info(f"Database initialized at {_db_path}")


async def get_db():
    """FastAPI dependency for getting a database connection"""
    async with aiosqlite.connect(str(_db_path)) as db:
        db.row_factory = aiosqlite.Row
        yield db
