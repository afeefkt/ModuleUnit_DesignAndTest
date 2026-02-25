"""Diagram render service — converts PlantUML text to SVG/PNG images.

Two rendering backends:
1. Kroki.io (default) — free public API, no install required
2. Local plantuml.jar (optional) — fully offline, set MUD_PLANTUML_JAR_PATH

Output files can be opened in any image viewer, embedded in docs, or
included in CI pipelines for visual regression testing.
"""

from __future__ import annotations

import base64
import logging
import subprocess
import zlib
from pathlib import Path

import httpx

from mudtool.config.settings import Settings, get_settings
from mudtool.generator.plantuml_exporter import PlantUMLExporter
from mudtool.models.json_uml import AnyDiagram, GenerationResult

logger = logging.getLogger(__name__)

# Kroki.io alphabet for PlantUML encoding
_KROKI_ALPHABET = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
)
_ENCODING_MAP = dict(zip(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    _KROKI_ALPHABET
))


def _encode_plantuml(puml_text: str) -> str:
    """Encode PlantUML text for Kroki.io URL/body (deflate + base64 variant)."""
    compressed = zlib.compress(puml_text.encode("utf-8"), level=9)[2:-4]
    b64 = base64.b64encode(compressed).decode("ascii")
    return "".join(_ENCODING_MAP.get(c, c) for c in b64)


class RenderService:
    """Render PlantUML diagrams to SVG or PNG images."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._exporter = PlantUMLExporter()

    async def render_plantuml_to_svg(self, puml_text: str) -> bytes:
        """Render PlantUML text to SVG bytes.

        Uses local plantuml.jar if configured, otherwise Kroki.io.
        """
        if self._settings.plantuml_jar_path:
            return await self._render_local(puml_text, "svg")

        if self._settings.use_kroki:
            return await self._render_kroki(puml_text, "svg")

        raise RuntimeError(
            "No render backend available. Set MUD_USE_KROKI=true "
            "or MUD_PLANTUML_JAR_PATH=/path/to/plantuml.jar"
        )

    async def render_plantuml_to_png(self, puml_text: str) -> bytes:
        """Render PlantUML text to PNG bytes."""
        if self._settings.plantuml_jar_path:
            return await self._render_local(puml_text, "png")

        if self._settings.use_kroki:
            return await self._render_kroki(puml_text, "png")

        raise RuntimeError(
            "No render backend available. Set MUD_USE_KROKI=true "
            "or MUD_PLANTUML_JAR_PATH=/path/to/plantuml.jar"
        )

    async def render_all(
        self,
        result: GenerationResult,
        output_dir: Path,
        fmt: str = "svg",
    ) -> list[Path]:
        """Render all diagrams in a generation result to image files.

        Args:
            result: Generation result with diagrams to render.
            output_dir: Directory to write output images.
            fmt: Output format — 'svg' or 'png'.

        Returns:
            List of written image file paths.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, diagram in enumerate(result.diagrams):
            try:
                name = getattr(diagram, "name", "") or f"diagram_{i}"
                name = name.replace(" ", "_").replace("/", "_")
                suffix = diagram.diagram_type.value
                path = output_dir / f"{suffix}_{name}.{fmt}"

                puml_text = self._exporter.export_diagram(diagram)

                if fmt == "svg":
                    image_bytes = await self.render_plantuml_to_svg(puml_text)
                else:
                    image_bytes = await self.render_plantuml_to_png(puml_text)

                path.write_bytes(image_bytes)
                paths.append(path)
                logger.info(f"Rendered {path.name} ({len(image_bytes)} bytes)")

            except Exception as e:
                logger.error(f"Failed to render diagram {i} to {fmt}: {e}")

        return paths

    async def _render_kroki(self, puml_text: str, fmt: str) -> bytes:
        """Render via Kroki.io REST API (POST method with JSON body)."""
        base_url = self._settings.kroki_base_url.rstrip("/")
        url = f"{base_url}/plantuml/{fmt}"

        payload = {"diagram_source": puml_text}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Accept": f"image/{fmt}"},
            )
            response.raise_for_status()
            return response.content

    async def _render_local(self, puml_text: str, fmt: str) -> bytes:
        """Render using a local plantuml.jar subprocess."""
        import asyncio
        import tempfile

        jar_path = self._settings.plantuml_jar_path
        if not jar_path or not jar_path.exists():
            raise FileNotFoundError(
                f"plantuml.jar not found at {jar_path}. "
                "Set MUD_PLANTUML_JAR_PATH to the correct path."
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dir = Path(tmpdir)
            puml_file = tmp_dir / "diagram.puml"
            puml_file.write_text(puml_text, encoding="utf-8")

            flag = "-tsvg" if fmt == "svg" else "-tpng"
            cmd = [
                "java", "-jar", str(jar_path),
                flag, "-quiet",
                "-o", str(tmp_dir),
                str(puml_file),
            ]

            loop = asyncio.get_event_loop()
            proc = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, timeout=60),
            )

            if proc.returncode != 0:
                raise RuntimeError(
                    f"plantuml.jar failed: {proc.stderr.decode('utf-8', errors='replace')}"
                )

            ext = "svg" if fmt == "svg" else "png"
            output_file = tmp_dir / f"diagram.{ext}"
            if not output_file.exists():
                raise FileNotFoundError(
                    f"plantuml.jar did not produce expected output: {output_file}"
                )

            return output_file.read_bytes()
