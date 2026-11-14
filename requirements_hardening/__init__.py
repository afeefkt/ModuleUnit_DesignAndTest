"""Agentic Requirements Hardening System (ARHS).

Deterministic core + role-based agents that turn architecture-style requirement
exports into an L2-oriented, reviewable requirements baseline.

The system never edits the original input. It writes a new baseline and an
evidence/review packet under ``outputs/req_hardening/<run>/`` and
``inputs/requirements_hardened/<set>/``.
"""

__version__ = "0.1.0"
