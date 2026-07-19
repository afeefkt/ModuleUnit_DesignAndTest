"""Dependency injection for FastAPI - singleton service instances."""

from __future__ import annotations

from functools import lru_cache

from mudtool.ai.orchestrator import AIOrchestrator
from mudtool.config.settings import Settings, get_settings
from mudtool.generator.autosar_mapper import AUTOSARMapper
from mudtool.generator.render_service import RenderService
from mudtool.traceability.store import TraceabilityStore
from mudtool.validation.engine import ValidationEngine

_orchestrator: AIOrchestrator | None = None
_mapper: AUTOSARMapper | None = None
_validator: ValidationEngine | None = None
_trace_store: TraceabilityStore | None = None
_render_service: RenderService | None = None


def get_orchestrator() -> AIOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator(get_settings())
    return _orchestrator


def get_mapper() -> AUTOSARMapper:
    global _mapper
    if _mapper is None:
        _mapper = AUTOSARMapper(get_settings())
    return _mapper


def get_validator() -> ValidationEngine:
    global _validator
    if _validator is None:
        _validator = ValidationEngine(get_settings())
    return _validator


def get_trace_store() -> TraceabilityStore:
    global _trace_store
    if _trace_store is None:
        _trace_store = TraceabilityStore(get_settings())
        _trace_store.initialize()
    return _trace_store


def get_render_service() -> RenderService:
    global _render_service
    if _render_service is None:
        _render_service = RenderService(get_settings())
    return _render_service


def reset_orchestrator() -> None:
    """Reset the AI orchestrator so it picks up new settings on next use.

    Called by POST /api/v1/config/update after writing new env vars.
    The next call to get_orchestrator() will create a fresh instance
    with the updated Settings.
    """
    global _orchestrator, _render_service
    _orchestrator = None
    _render_service = None


def shutdown_services() -> None:
    """Clean shutdown of all services."""
    global _trace_store
    if _trace_store:
        _trace_store.close()
        _trace_store = None
