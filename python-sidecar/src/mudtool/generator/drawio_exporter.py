"""draw.io XML diagram exporter.

Generates .drawio files (diagrams.net XML) that open in:
- diagrams.net web app (free, no account needed) at https://app.diagrams.net
- VS Code draw.io extension (hediet.vscode-drawio)
- draw.io desktop app (free download)
- Confluence, Jira, Notion (with draw.io integration)

Each diagram type is exported as a separate page within a single .drawio file
(or one file per diagram via export_result which writes one file per diagram).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

from mudtool.models.json_uml import (
    ActivityDiagram,
    ActivityNodeType,
    AnyDiagram,
    ClassDiagram,
    ComponentDiagram,
    GenerationResult,
    SequenceDiagram,
    StateMachineDiagram,
)

logger = logging.getLogger(__name__)

# draw.io cell styles
_STYLE_STATE = (
    "rounded=1;whiteSpace=wrap;html=1;arcSize=30;"
    "fillColor=#dae8fc;strokeColor=#6c8ebf;"
)
_STYLE_INITIAL = (
    "ellipse;aspect=fixed;fillColor=#000000;strokeColor=#000000;"
)
_STYLE_FINAL = (
    "ellipse;aspect=fixed;fillColor=#000000;strokeColor=#000000;"
    "double=1;"
)
_STYLE_TRANSITION = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
_STYLE_CLASS_HEADER = (
    "swimlane;startSize=30;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    "fontStyle=1;fontSize=11;"
)
_STYLE_CLASS_ATTR = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=4;"
_STYLE_CLASS_OP = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=4;fontStyle=2;"
_STYLE_COMPONENT = (
    "shape=mxgraph.archimate3.component;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    "whiteSpace=wrap;html=1;"
)
_STYLE_CONNECTOR = "edgeStyle=orthogonalEdgeStyle;rounded=0;"
_STYLE_LIFELINE = (
    "shape=mxgraph.uml.lifeline;perimeter=mxPerimeter.rectanglePerimeter;"
    "fillColor=#dae8fc;strokeColor=#6c8ebf;whiteSpace=wrap;html=1;"
)
_STYLE_MESSAGE = "edgeStyle=orthogonalEdgeStyle;rounded=0;"
# Activity diagram node styles
_STYLE_ACT_INITIAL    = "ellipse;aspect=fixed;fillColor=#000000;strokeColor=#000000;fontColor=#ffffff;"
_STYLE_ACT_FINAL      = "ellipse;aspect=fixed;fillColor=#000000;strokeColor=#000000;fontColor=#ffffff;double=1;"
_STYLE_ACT_ACTION     = "rounded=1;whiteSpace=wrap;arcSize=15;fillColor=#f5f5f5;strokeColor=#666666;"
_STYLE_ACT_CALL       = "rounded=1;whiteSpace=wrap;arcSize=15;fillColor=#dae8fc;strokeColor=#6c8ebf;"
_STYLE_ACT_DECISION   = "rhombus;whiteSpace=wrap;fillColor=#fff2cc;strokeColor=#d6b656;"
_STYLE_ACT_FORK_JOIN  = "shape=mxgraph.flowchart.annotation_2;fillColor=#000000;strokeColor=#000000;"
_STYLE_ACT_MERGE      = "rounded=1;whiteSpace=wrap;fillColor=#fff2cc;strokeColor=#d6b656;arcSize=50;"
_STYLE_ACT_EXCEPTION  = "shape=parallelogram;whiteSpace=wrap;fillColor=#f8cecc;strokeColor=#b85450;"
_STYLE_ACT_FUNC_CALL  = "rounded=1;whiteSpace=wrap;arcSize=15;fillColor=#d5e8d4;strokeColor=#82b366;double=1;"
_STYLE_ACT_EDGE       = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"


def _uid() -> str:
    return f"mud_{uuid.uuid4().hex[:10]}"


class DrawIOExporter:
    """Export JSON-UML diagrams to draw.io XML format."""

    def export_result(
        self,
        result: GenerationResult,
        output_dir: Path,
    ) -> list[Path]:
        """Export all diagrams, one .drawio file per diagram.

        Returns list of written file paths.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, diagram in enumerate(result.diagrams):
            try:
                name = getattr(diagram, "name", "") or f"diagram_{i}"
                name = name.replace(" ", "_").replace("/", "_")
                suffix = diagram.diagram_type.value
                path = output_dir / f"{suffix}_{name}.drawio"

                content = self.export_diagram(diagram)
                path.write_text(content, encoding="utf-8")
                paths.append(path)

            except Exception as e:
                logger.error(f"Failed to export diagram {i} to draw.io: {e}")

        return paths

    def export_all_as_single_file(
        self,
        result: GenerationResult,
        output_path: Path,
    ) -> Path:
        """Export all diagrams as pages in a single .drawio file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        mxfile = Element("mxfile")
        mxfile.set("host", "mud-tool")
        mxfile.set("version", "21.0.0")

        for i, diagram in enumerate(result.diagrams):
            try:
                name = getattr(diagram, "name", "") or f"diagram_{i}"
                page = SubElement(mxfile, "diagram")
                page.set("id", _uid())
                page.set("name", name)

                # Embed the diagram XML as text content
                graph_xml = self._diagram_to_xml_string(diagram)
                page.text = graph_xml
            except Exception as e:
                logger.error(f"Failed to export diagram {i} to draw.io page: {e}")

        tree = ElementTree(mxfile)
        indent(tree.getroot(), space="  ")
        tree.write(str(output_path), encoding="unicode", xml_declaration=True)
        return output_path

    def export_diagram(self, diagram: AnyDiagram) -> str:
        """Export a single diagram to draw.io XML string."""
        mxfile = Element("mxfile")
        mxfile.set("host", "mud-tool")
        mxfile.set("version", "21.0.0")

        page = SubElement(mxfile, "diagram")
        page.set("id", _uid())
        page.set("name", getattr(diagram, "name", "Diagram") or "Diagram")

        graph = SubElement(page, "mxGraphModel")
        graph.set("dx", "1422")
        graph.set("dy", "762")
        graph.set("grid", "1")
        graph.set("gridSize", "10")
        graph.set("guides", "1")
        graph.set("tooltips", "1")
        graph.set("connect", "1")
        graph.set("arrows", "1")
        graph.set("fold", "1")
        graph.set("page", "1")
        graph.set("pageScale", "1")
        graph.set("pageWidth", "1654")
        graph.set("pageHeight", "1169")

        root = SubElement(graph, "root")
        SubElement(root, "mxCell").set("id", "0")
        parent = SubElement(root, "mxCell")
        parent.set("id", "1")
        parent.set("parent", "0")

        if isinstance(diagram, SequenceDiagram):
            self._build_sequence(root, diagram)
        elif isinstance(diagram, StateMachineDiagram):
            self._build_state_machine(root, diagram)
        elif isinstance(diagram, ClassDiagram):
            self._build_class_diagram(root, diagram)
        elif isinstance(diagram, ComponentDiagram):
            self._build_component_diagram(root, diagram)
        elif isinstance(diagram, ActivityDiagram):
            self._build_activity_diagram(root, diagram)

        tree = ElementTree(mxfile)
        indent(tree.getroot(), space="  ")

        import io
        buf = io.StringIO()
        tree.write(buf, encoding="unicode", xml_declaration=True)
        return buf.getvalue()

    def _diagram_to_xml_string(self, diagram: AnyDiagram) -> str:
        """Return just the mxGraphModel XML as a string (for embedding in pages)."""
        graph = Element("mxGraphModel")
        graph.set("grid", "1")
        graph.set("pageWidth", "1654")
        graph.set("pageHeight", "1169")

        root = SubElement(graph, "root")
        SubElement(root, "mxCell").set("id", "0")
        parent = SubElement(root, "mxCell")
        parent.set("id", "1")
        parent.set("parent", "0")

        if isinstance(diagram, SequenceDiagram):
            self._build_sequence(root, diagram)
        elif isinstance(diagram, StateMachineDiagram):
            self._build_state_machine(root, diagram)
        elif isinstance(diagram, ClassDiagram):
            self._build_class_diagram(root, diagram)
        elif isinstance(diagram, ComponentDiagram):
            self._build_component_diagram(root, diagram)
        elif isinstance(diagram, ActivityDiagram):
            self._build_activity_diagram(root, diagram)

        import io
        buf = io.StringIO()
        ElementTree(graph).write(buf, encoding="unicode")
        return buf.getvalue()

    # ── Sequence Diagram ────────────────────────────────────────────

    def _build_sequence(self, root: Element, diagram: SequenceDiagram) -> None:
        ll_width = 160
        ll_height = 400
        ll_spacing = 200
        header_height = 60

        # Lifeline cells (vertical swim lane style)
        lifeline_x: dict[str, int] = {}
        for i, ll in enumerate(diagram.lifelines):
            x = 40 + i * ll_spacing
            lifeline_x[ll.id] = x + ll_width // 2  # center x for messages

            cell = SubElement(root, "mxCell")
            cell.set("id", ll.id)
            cell.set("value", f"{ll.name}\n«{ll.type or 'SWC'}»")
            cell.set("style", _STYLE_LIFELINE)
            cell.set("vertex", "1")
            cell.set("parent", "1")
            geo = SubElement(cell, "mxGeometry")
            geo.set("x", str(x))
            geo.set("y", "40")
            geo.set("width", str(ll_width))
            geo.set("height", str(ll_height))
            geo.set("as", "geometry")

        # Messages as horizontal arrows
        for i, msg in enumerate(diagram.messages):
            y = header_height + 50 + i * 50

            label = msg.label or ""
            if not label and msg.rte_call:
                parts = [msg.rte_call]
                if msg.port:
                    parts.append(msg.port)
                label = f"{parts[0]}({', '.join(parts[1:])})"
            if msg.trace_req:
                label += f" [{msg.trace_req}]"

            edge = SubElement(root, "mxCell")
            edge.set("id", msg.id or _uid())
            edge.set("value", label)
            edge.set("style", _STYLE_MESSAGE)
            edge.set("edge", "1")
            edge.set("source", msg.from_lifeline)
            edge.set("target", msg.to_lifeline)
            edge.set("parent", "1")

            geo = SubElement(edge, "mxGeometry")
            geo.set("relative", "1")
            geo.set("as", "geometry")

            point = SubElement(geo, "Array")
            point.set("as", "points")

    # ── State Machine ────────────────────────────────────────────────

    def _build_state_machine(self, root: Element, diagram: StateMachineDiagram) -> None:
        state_xmi: dict[str, str] = {}
        col_count = 3
        x_base, y_base = 80, 80
        x_step, y_step = 220, 120

        for i, state in enumerate(diagram.states):
            col = i % col_count
            row = i // col_count
            x = x_base + col * x_step
            y = y_base + row * y_step

            cell_id = state.id or _uid()
            state_xmi[state.id] = cell_id

            cell = SubElement(root, "mxCell")
            cell.set("id", cell_id)
            cell.set("value", state.name)
            cell.set("vertex", "1")
            cell.set("parent", "1")

            if state.is_initial:
                cell.set("style", _STYLE_INITIAL)
                geo = SubElement(cell, "mxGeometry")
                geo.set("x", str(x))
                geo.set("y", str(y))
                geo.set("width", "30")
                geo.set("height", "30")
                geo.set("as", "geometry")
            elif state.is_final:
                cell.set("style", _STYLE_FINAL)
                geo = SubElement(cell, "mxGeometry")
                geo.set("x", str(x))
                geo.set("y", str(y))
                geo.set("width", "30")
                geo.set("height", "30")
                geo.set("as", "geometry")
            else:
                label = state.name
                if state.trace_reqs:
                    label += f"\n[{', '.join(state.trace_reqs)}]"
                cell.set("style", _STYLE_STATE)
                cell.set("value", label)
                geo = SubElement(cell, "mxGeometry")
                geo.set("x", str(x))
                geo.set("y", str(y))
                geo.set("width", "160")
                geo.set("height", "60")
                geo.set("as", "geometry")

        for trans in diagram.transitions:
            label_parts = []
            if trans.trigger:
                label_parts.append(trans.trigger)
            if trans.guard:
                label_parts.append(f"[{trans.guard.condition}]")
            label = " ".join(label_parts)

            edge = SubElement(root, "mxCell")
            edge.set("id", trans.id or _uid())
            edge.set("value", label)
            edge.set("style", _STYLE_TRANSITION)
            edge.set("edge", "1")
            edge.set("source", state_xmi.get(trans.source, trans.source))
            edge.set("target", state_xmi.get(trans.target, trans.target))
            edge.set("parent", "1")
            geo = SubElement(edge, "mxGeometry")
            geo.set("relative", "1")
            geo.set("as", "geometry")

    # ── Class Diagram ─────────────────────────────────────────────────

    def _build_class_diagram(self, root: Element, diagram: ClassDiagram) -> None:
        class_ids: dict[str, str] = {}
        x, y = 60, 60

        for cls in diagram.classes:
            cell_id = cls.id or _uid()
            class_ids[cls.id] = cell_id

            row_height = 30
            attr_count = len(cls.attributes)
            op_count = len(cls.operations)
            total_height = row_height + (attr_count + op_count + 1) * 24 + 16

            # Class container (swim lane style)
            container = SubElement(root, "mxCell")
            container.set("id", cell_id)
            container.set("value", f"{cls.name}")
            container.set("style", _STYLE_CLASS_HEADER)
            container.set("vertex", "1")
            container.set("parent", "1")
            container.set("childLayout", "stackLayout")
            container.set("horizontalStack", "0")
            container.set("startSize", "30")
            container.set("fillColor", "#dae8fc")
            geo = SubElement(container, "mxGeometry")
            geo.set("x", str(x))
            geo.set("y", str(y))
            geo.set("width", "220")
            geo.set("height", str(total_height))
            geo.set("as", "geometry")

            if cls.stereotype:
                stereo_cell = SubElement(root, "mxCell")
                stereo_cell.set("id", _uid())
                stereo_cell.set("value", f"«{cls.stereotype}»")
                stereo_cell.set("style", _STYLE_CLASS_ATTR)
                stereo_cell.set("vertex", "1")
                stereo_cell.set("parent", cell_id)
                stereo_geo = SubElement(stereo_cell, "mxGeometry")
                stereo_geo.set("x", "0")
                stereo_geo.set("y", "0")
                stereo_geo.set("width", "220")
                stereo_geo.set("height", "24")
                stereo_geo.set("as", "geometry")

            for attr in cls.attributes:
                vis = {
                    "public": "+", "private": "-",
                    "protected": "#", "package": "~"
                }.get(attr.visibility.value, "+")
                attr_cell = SubElement(root, "mxCell")
                attr_cell.set("id", _uid())
                attr_cell.set("value", f"{vis} {attr.name}: {attr.data_type}")
                attr_cell.set("style", _STYLE_CLASS_ATTR)
                attr_cell.set("vertex", "1")
                attr_cell.set("parent", cell_id)
                attr_geo = SubElement(attr_cell, "mxGeometry")
                attr_geo.set("x", "0")
                attr_geo.set("y", "0")
                attr_geo.set("width", "220")
                attr_geo.set("height", "24")
                attr_geo.set("as", "geometry")

            # Separator line before operations
            if cls.operations:
                sep = SubElement(root, "mxCell")
                sep.set("id", _uid())
                sep.set("value", "──────────")
                sep.set("style", _STYLE_CLASS_ATTR + "align=center;")
                sep.set("vertex", "1")
                sep.set("parent", cell_id)
                sep_geo = SubElement(sep, "mxGeometry")
                sep_geo.set("x", "0")
                sep_geo.set("y", "0")
                sep_geo.set("width", "220")
                sep_geo.set("height", "16")
                sep_geo.set("as", "geometry")

            for op in cls.operations:
                vis = {
                    "public": "+", "private": "-",
                    "protected": "#", "package": "~"
                }.get(op.visibility.value, "+")
                trigger = f" [{op.trigger_type}]" if op.trigger_type else ""
                ret = f": {op.return_type}" if op.return_type else ""
                op_cell = SubElement(root, "mxCell")
                op_cell.set("id", _uid())
                op_cell.set("value", f"{vis} {op.name}(){ret}{trigger}")
                op_cell.set("style", _STYLE_CLASS_OP)
                op_cell.set("vertex", "1")
                op_cell.set("parent", cell_id)
                op_geo = SubElement(op_cell, "mxGeometry")
                op_geo.set("x", "0")
                op_geo.set("y", "0")
                op_geo.set("width", "220")
                op_geo.set("height", "24")
                op_geo.set("as", "geometry")

            x += 260

        # Associations
        for assoc in diagram.associations:
            arrow_style = {
                "association": "endArrow=open;endFill=0;",
                "aggregation": "endArrow=open;startArrow=ERmanyToOne;startFill=0;endFill=0;",
                "composition": "endArrow=open;startArrow=ERmanyToOne;startFill=1;endFill=0;",
                "dependency": "endArrow=open;dashed=1;endFill=0;",
                "realization": "endArrow=block;dashed=1;endFill=0;",
            }.get(assoc.association_type.value, "endArrow=open;endFill=0;")

            edge = SubElement(root, "mxCell")
            edge.set("id", _uid())
            edge.set("value", assoc.label or "")
            edge.set("style", f"edgeStyle=orthogonalEdgeStyle;{arrow_style}")
            edge.set("edge", "1")
            edge.set("source", class_ids.get(assoc.source, assoc.source))
            edge.set("target", class_ids.get(assoc.target, assoc.target))
            edge.set("parent", "1")
            geo = SubElement(edge, "mxGeometry")
            geo.set("relative", "1")
            geo.set("as", "geometry")

    # ── Component Diagram ────────────────────────────────────────────

    def _build_component_diagram(self, root: Element, diagram: ComponentDiagram) -> None:
        comp_ids: dict[str, str] = {}
        cols = 3
        x_base, y_base = 80, 80
        x_step, y_step = 280, 200

        for i, comp in enumerate(diagram.components):
            col = i % cols
            row = i // cols
            x = x_base + col * x_step
            y = y_base + row * y_step

            cell_id = comp.id or _uid()
            comp_ids[comp.id] = cell_id

            port_text = ""
            if comp.ports:
                port_list = []
                for p in comp.ports[:6]:
                    direction = "P" if p.direction == "provided" else "R"
                    port_list.append(f"[{direction}] {p.name}")
                port_text = "\n".join(port_list)

            label = comp.name
            if comp.stereotype:
                label = f"«{comp.stereotype}»\n{comp.name}"
            if port_text:
                label += f"\n─────\n{port_text}"

            cell = SubElement(root, "mxCell")
            cell.set("id", cell_id)
            cell.set("value", label)
            cell.set("style", _STYLE_COMPONENT)
            cell.set("vertex", "1")
            cell.set("parent", "1")
            geo = SubElement(cell, "mxGeometry")
            geo.set("x", str(x))
            geo.set("y", str(y))
            geo.set("width", "200")
            geo.set("height", "120")
            geo.set("as", "geometry")

        for conn in diagram.connectors:
            edge = SubElement(root, "mxCell")
            edge.set("id", _uid())
            edge.set("value", conn.label or "")
            edge.set("style", _STYLE_CONNECTOR)
            edge.set("edge", "1")
            edge.set("source", comp_ids.get(conn.source_component, conn.source_component))
            edge.set("target", comp_ids.get(conn.target_component, conn.target_component))
            edge.set("parent", "1")
            geo = SubElement(edge, "mxGeometry")
            geo.set("relative", "1")
            geo.set("as", "geometry")

    # ── Activity / Code-Flow Diagram ─────────────────────────────────

    def _build_activity_diagram(self, root: Element, diagram: ActivityDiagram) -> None:
        """Build draw.io flowchart cells for an activity / code-flow diagram."""
        node_cell_ids: dict[str, str] = {}
        x, y = 80, 60
        y_step = 120

        for i, node in enumerate(diagram.nodes):
            cell_id = _uid()
            node_cell_ids[node.id] = cell_id

            # Build label
            label_parts = [node.name]
            if node.node_type == ActivityNodeType.CALL:
                parts = []
                if node.rte_call:
                    parts.append(node.rte_call)
                if node.port:
                    parts.append(node.port)
                if node.element:
                    parts.append(node.element)
                if parts:
                    call_label = f"{parts[0]}({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]
                    label_parts = [call_label]
            elif node.description:
                label_parts.append(node.description)
            if node.trace_reqs:
                label_parts.append(f"[{', '.join(node.trace_reqs)}]")
            label = "\n".join(label_parts)

            # Select style
            style_map = {
                ActivityNodeType.INITIAL:       _STYLE_ACT_INITIAL,
                ActivityNodeType.FINAL:         _STYLE_ACT_FINAL,
                ActivityNodeType.ACTION:        _STYLE_ACT_ACTION,
                ActivityNodeType.CALL:          _STYLE_ACT_CALL,
                ActivityNodeType.FUNCTION_CALL: _STYLE_ACT_FUNC_CALL,
                ActivityNodeType.DECISION:      _STYLE_ACT_DECISION,
                ActivityNodeType.FORK:          _STYLE_ACT_FORK_JOIN,
                ActivityNodeType.JOIN:          _STYLE_ACT_FORK_JOIN,
                ActivityNodeType.MERGE:         _STYLE_ACT_MERGE,
                ActivityNodeType.EXCEPTION:     _STYLE_ACT_EXCEPTION,
            }
            style = style_map.get(node.node_type, _STYLE_ACT_ACTION)

            # Node dimensions vary by type
            if node.node_type in (ActivityNodeType.INITIAL, ActivityNodeType.FINAL):
                w, h = 30, 30
            elif node.node_type == ActivityNodeType.DECISION:
                w, h = 140, 80
            elif node.node_type in (ActivityNodeType.FORK, ActivityNodeType.JOIN):
                w, h = 160, 10
            else:
                w, h = 200, 60

            # Lay nodes out vertically; alternate x for decisions to show branches
            node_x = x
            node_y = y + i * y_step

            cell = SubElement(root, "mxCell")
            cell.set("id", cell_id)
            cell.set("value", label)
            cell.set("style", style)
            cell.set("vertex", "1")
            cell.set("parent", "1")
            geo = SubElement(cell, "mxGeometry")
            geo.set("x", str(node_x))
            geo.set("y", str(node_y))
            geo.set("width", str(w))
            geo.set("height", str(h))
            geo.set("as", "geometry")

        # Emit edges
        for edge in diagram.edges:
            src_cell = node_cell_ids.get(edge.source, edge.source)
            tgt_cell = node_cell_ids.get(edge.target, edge.target)
            guard_label = edge.guard or edge.label or ""

            ecell = SubElement(root, "mxCell")
            ecell.set("id", edge.id or _uid())
            ecell.set("value", guard_label)
            ecell.set("style", _STYLE_ACT_EDGE)
            ecell.set("edge", "1")
            ecell.set("source", src_cell)
            ecell.set("target", tgt_cell)
            ecell.set("parent", "1")
            geo = SubElement(ecell, "mxGeometry")
            geo.set("relative", "1")
            geo.set("as", "geometry")
