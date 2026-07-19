"""MUD Tool Sidecar - FastAPI application entry point.

Runs as a localhost HTTP server, providing AI-driven AUTOSAR MUD generation
services to the Modelio Java plugin or any HTTP client.

Usage:
    mudtool-server                    # Run with defaults (port 8042)
    MUD_PORT=9000 mudtool-server      # Custom port
    python -m mudtool.main            # Direct Python invocation
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mudtool import __version__
from mudtool.api.dependencies import shutdown_services
from mudtool.api.routes import router
from mudtool.config.settings import _find_env_file, get_settings
from mudtool.web.app import router as web_router


def setup_logging(level: str = "info") -> None:
    """Configure application logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from third-party libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    import os
    logger.info(f"MUD Tool Sidecar v{__version__} starting...")
    logger.info(f"CWD: {os.getcwd()}")
    logger.info(f"Config: {_find_env_file()}")
    logger.info(f"AI Backend: {settings.ai_backend.value} / {settings.cloud_provider.value}")
    if settings.cloud_provider.value == "openai_compatible":
        logger.info(f"Endpoint: {settings.openai_base_url}  model={settings.openai_model}")
    logger.info(f"Listening on {settings.host}:{settings.port}")
    logger.info(f"Web UI:  http://{settings.host}:{settings.port}/")
    logger.info(f"API Docs: http://{settings.host}:{settings.port}/docs")

    yield

    logger.info("Shutting down MUD Tool Sidecar...")
    shutdown_services()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MUD Tool - AI-Assisted AUTOSAR Module & Unit Design",
        description=(
            "Python sidecar providing AI-driven requirement analysis, "
            "UML diagram generation, AUTOSAR mapping, and model validation "
            "for the AUTOSAR Module & Unit Design workflow."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS - allow Modelio plugin and local dev access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # localhost only in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routes
    app.include_router(router, prefix="/api/v1", tags=["MUD Tool API"])

    # Built-in Web UI at /
    app.include_router(web_router)

    return app


# Create the application instance
app = create_app()


def main() -> None:
    """CLI entry point for the sidecar server."""
    settings = get_settings()

    uvicorn.run(
        "mudtool.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
