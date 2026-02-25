"""SQLite-backed traceability store.

Maintains bidirectional traceability from requirement IDs to generated
model elements, with full provenance metadata.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from mudtool.config.settings import Settings
from mudtool.models.json_uml import (
    ActivityDiagram,
    ClassDiagram,
    ComponentDiagram,
    GenerationResult,
    SequenceDiagram,
    StateMachineDiagram,
)

logger = logging.getLogger(__name__)


class TraceLink(BaseModel):
    """A single traceability link between a requirement and a model element."""
    id: Optional[int] = None
    requirement_id: str
    element_id: str
    element_name: str
    element_type: str = Field(..., description="lifeline, message, state, class, component, etc.")
    diagram_type: str
    diagram_name: str = ""
    ai_model: str = ""
    confidence: float = 0.0
    prompt_version: str = ""
    xmi_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    accepted: bool = False
    accepted_by: Optional[str] = None
    accepted_at: Optional[datetime] = None


class TraceabilityStore:
    """SQLite-backed store for requirement-to-model traceability.

    Provides:
    - Bidirectional trace queries (req -> elements, element -> reqs)
    - Provenance metadata storage
    - Coverage analysis
    - Human review/acceptance tracking
    """

    def __init__(self, settings: Settings):
        self.db_path = settings.get_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Create the database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Traceability store initialized at {self.db_path}")

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS trace_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requirement_id TEXT NOT NULL,
                element_id TEXT NOT NULL,
                element_name TEXT NOT NULL,
                element_type TEXT NOT NULL,
                diagram_type TEXT NOT NULL,
                diagram_name TEXT DEFAULT '',
                ai_model TEXT DEFAULT '',
                confidence REAL DEFAULT 0.0,
                prompt_version TEXT DEFAULT '',
                xmi_path TEXT,
                created_at TEXT NOT NULL,
                accepted INTEGER DEFAULT 0,
                accepted_by TEXT,
                accepted_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_trace_req ON trace_links(requirement_id);
            CREATE INDEX IF NOT EXISTS idx_trace_elem ON trace_links(element_id);
            CREATE INDEX IF NOT EXISTS idx_trace_diagram ON trace_links(diagram_type);

            CREATE TABLE IF NOT EXISTS requirements (
                req_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                req_type TEXT NOT NULL,
                safety_level TEXT,
                priority TEXT NOT NULL,
                module_hint TEXT,
                source_file TEXT,
                imported_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS generation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_timestamp TEXT NOT NULL,
                diagram_types TEXT NOT NULL,
                requirement_count INTEGER NOT NULL,
                ai_backend TEXT NOT NULL,
                ai_model TEXT NOT NULL,
                total_time_ms INTEGER,
                diagrams_generated INTEGER DEFAULT 0,
                errors TEXT,
                warnings TEXT
            );
        """)
        self._conn.commit()

    def add_trace_link(self, link: TraceLink) -> int:
        """Add a single trace link. Returns the link ID."""
        assert self._conn is not None
        cursor = self._conn.execute(
            """INSERT INTO trace_links
               (requirement_id, element_id, element_name, element_type,
                diagram_type, diagram_name, ai_model, confidence,
                prompt_version, xmi_path, created_at, accepted)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                link.requirement_id, link.element_id, link.element_name,
                link.element_type, link.diagram_type, link.diagram_name,
                link.ai_model, link.confidence, link.prompt_version,
                link.xmi_path, link.created_at.isoformat(), int(link.accepted),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def extract_and_store_traces(self, result: GenerationResult) -> int:
        """Extract trace links from a GenerationResult and store them.

        Returns the number of trace links created.
        """
        count = 0

        for diagram in result.diagrams:
            prov = getattr(diagram, "provenance", None)
            ai_model = prov.ai_model if prov else ""
            confidence = prov.confidence if prov else 0.0
            prompt_v = prov.prompt_version if prov else ""
            diag_type = diagram.diagram_type.value
            diag_name = getattr(diagram, "name", "") or ""

            # Diagram-level fallback: if source_requirements is populated
            # (either by the AI or injected by the orchestrator), create
            # a "diagram" trace link for each requirement so that coverage
            # reporting works even when element-level trace_req fields are empty.
            for req_id in diagram.source_requirements:
                self.add_trace_link(TraceLink(
                    requirement_id=req_id,
                    element_id=f"diagram__{diag_name or diag_type}",
                    element_name=diag_name or diag_type,
                    element_type="diagram",
                    diagram_type=diag_type,
                    diagram_name=diag_name,
                    ai_model=ai_model,
                    confidence=confidence,
                    prompt_version=prompt_v,
                ))
                count += 1

            if isinstance(diagram, SequenceDiagram):
                for ll in diagram.lifelines:
                    for req_id in ll.trace_reqs:
                        self.add_trace_link(TraceLink(
                            requirement_id=req_id,
                            element_id=ll.id,
                            element_name=ll.name,
                            element_type="lifeline",
                            diagram_type=diag_type,
                            diagram_name=diag_name,
                            ai_model=ai_model,
                            confidence=confidence,
                            prompt_version=prompt_v,
                        ))
                        count += 1

                for msg in diagram.messages:
                    if msg.trace_req:
                        self.add_trace_link(TraceLink(
                            requirement_id=msg.trace_req,
                            element_id=msg.id,
                            element_name=msg.label or msg.rte_call or "",
                            element_type="message",
                            diagram_type=diag_type,
                            diagram_name=diag_name,
                            ai_model=ai_model,
                            confidence=msg.confidence or confidence,
                            prompt_version=prompt_v,
                        ))
                        count += 1

            elif isinstance(diagram, StateMachineDiagram):
                for state in diagram.states:
                    for req_id in state.trace_reqs:
                        self.add_trace_link(TraceLink(
                            requirement_id=req_id,
                            element_id=state.id,
                            element_name=state.name,
                            element_type="state",
                            diagram_type=diag_type,
                            diagram_name=diag_name,
                            ai_model=ai_model,
                            confidence=state.confidence or confidence,
                            prompt_version=prompt_v,
                        ))
                        count += 1

            elif isinstance(diagram, ClassDiagram):
                for cls in diagram.classes:
                    for req_id in cls.trace_reqs:
                        self.add_trace_link(TraceLink(
                            requirement_id=req_id,
                            element_id=cls.id,
                            element_name=cls.name,
                            element_type="class",
                            diagram_type=diag_type,
                            diagram_name=diag_name,
                            ai_model=ai_model,
                            confidence=cls.confidence or confidence,
                            prompt_version=prompt_v,
                        ))
                        count += 1

            elif isinstance(diagram, ComponentDiagram):
                for comp in diagram.components:
                    for req_id in comp.trace_reqs:
                        self.add_trace_link(TraceLink(
                            requirement_id=req_id,
                            element_id=comp.id,
                            element_name=comp.name,
                            element_type="component",
                            diagram_type=diag_type,
                            diagram_name=diag_name,
                            ai_model=ai_model,
                            confidence=comp.confidence or confidence,
                            prompt_version=prompt_v,
                        ))
                        count += 1

            elif isinstance(diagram, ActivityDiagram):
                for node in diagram.nodes:
                    for req_id in node.trace_reqs:
                        self.add_trace_link(TraceLink(
                            requirement_id=req_id,
                            element_id=node.id,
                            element_name=node.name,
                            element_type=f"activity_{node.node_type.value}",
                            diagram_type=diag_type,
                            diagram_name=diag_name,
                            ai_model=ai_model,
                            confidence=node.confidence or confidence,
                            prompt_version=prompt_v,
                        ))
                        count += 1
                # Also handle sub_diagrams (hierarchical decomposition)
                for sub in diagram.sub_diagrams:
                    for node in sub.nodes:
                        for req_id in node.trace_reqs:
                            self.add_trace_link(TraceLink(
                                requirement_id=req_id,
                                element_id=node.id,
                                element_name=node.name,
                                element_type=f"activity_{node.node_type.value}",
                                diagram_type=diag_type,
                                diagram_name=sub.name or diag_name,
                                ai_model=ai_model,
                                confidence=node.confidence or confidence,
                                prompt_version=prompt_v,
                            ))
                            count += 1

        logger.info(f"Stored {count} trace links from generation result")
        return count

    def get_traces_for_requirement(self, req_id: str) -> list[TraceLink]:
        """Get all model elements traced to a requirement."""
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM trace_links WHERE requirement_id = ? ORDER BY created_at",
            (req_id,),
        ).fetchall()
        return [self._row_to_link(r) for r in rows]

    def get_traces_for_element(self, element_id: str) -> list[TraceLink]:
        """Get all requirements traced to a model element."""
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM trace_links WHERE element_id = ? ORDER BY created_at",
            (element_id,),
        ).fetchall()
        return [self._row_to_link(r) for r in rows]

    def get_coverage_report(self, requirement_ids: list[str]) -> dict:
        """Generate a traceability coverage report.

        Returns:
            Dict with coverage statistics and uncovered requirements.
        """
        assert self._conn is not None
        covered = set()
        rows = self._conn.execute(
            "SELECT DISTINCT requirement_id FROM trace_links"
        ).fetchall()
        for row in rows:
            covered.add(row[0])

        all_reqs = set(requirement_ids)
        uncovered = all_reqs - covered

        return {
            "total_requirements": len(all_reqs),
            "covered_requirements": len(covered),
            "uncovered_requirements": len(uncovered),
            "coverage_percentage": (
                round(len(covered) / len(all_reqs) * 100, 1) if all_reqs else 0
            ),
            "uncovered_ids": sorted(uncovered),
        }

    def get_traceability_matrix(self) -> list[dict]:
        """Generate a full traceability matrix.

        Returns list of dicts with requirement_id, element mappings.
        """
        assert self._conn is not None
        rows = self._conn.execute("""
            SELECT requirement_id, element_name, element_type,
                   diagram_type, diagram_name, confidence, accepted
            FROM trace_links
            ORDER BY requirement_id, diagram_type
        """).fetchall()

        matrix: dict[str, list[dict]] = {}
        for row in rows:
            req_id = row[0]
            if req_id not in matrix:
                matrix[req_id] = []
            matrix[req_id].append({
                "element_name": row[1],
                "element_type": row[2],
                "diagram_type": row[3],
                "diagram_name": row[4],
                "confidence": row[5],
                "accepted": bool(row[6]),
            })

        return [
            {"requirement_id": req_id, "elements": elements}
            for req_id, elements in sorted(matrix.items())
        ]

    def accept_element(
        self, element_id: str, accepted_by: str = "engineer"
    ) -> int:
        """Mark a model element as accepted by human reviewer.

        Returns number of trace links updated.
        """
        assert self._conn is not None
        now = datetime.utcnow().isoformat()
        cursor = self._conn.execute(
            """UPDATE trace_links
               SET accepted = 1, accepted_by = ?, accepted_at = ?
               WHERE element_id = ?""",
            (accepted_by, now, element_id),
        )
        self._conn.commit()
        return cursor.rowcount

    def _row_to_link(self, row: sqlite3.Row) -> TraceLink:
        return TraceLink(
            id=row["id"],
            requirement_id=row["requirement_id"],
            element_id=row["element_id"],
            element_name=row["element_name"],
            element_type=row["element_type"],
            diagram_type=row["diagram_type"],
            diagram_name=row["diagram_name"],
            ai_model=row["ai_model"],
            confidence=row["confidence"],
            prompt_version=row["prompt_version"],
            xmi_path=row["xmi_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            accepted=bool(row["accepted"]),
            accepted_by=row["accepted_by"],
            accepted_at=(
                datetime.fromisoformat(row["accepted_at"])
                if row["accepted_at"] else None
            ),
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
