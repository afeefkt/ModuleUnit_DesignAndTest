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

from dataclasses import dataclass
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
_STYLE_ACT_CALL       = "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;fillColor=#dae8fc;strokeColor=#6c8ebf;"
_STYLE_ACT_DECISION   = "rhombus;whiteSpace=wrap;fillColor=#fff2cc;strokeColor=#d6b656;"
_STYLE_ACT_FORK_JOIN  = "shape=mxgraph.flowchart.annotation_2;fillColor=#000000;strokeColor=#000000;"
_STYLE_ACT_MERGE      = "rhombus;whiteSpace=wrap;fillColor=#ffffff;strokeColor=#d6b656;fontSize=9;"
_STYLE_ACT_EXCEPTION  = "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;fillColor=#f8cecc;strokeColor=#b85450;"
_STYLE_ACT_FUNC_CALL  = "rounded=1;whiteSpace=wrap;arcSize=15;fillColor=#d5e8d4;strokeColor=#82b366;double=1;"
_STYLE_ACT_EDGE       = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"


@dataclass
class _ActivityLayoutBox:
    node_id: str
    label: str
    style: str
    width: int
    height: int
    rank: int = 0
    x: float = 0.0
    y: float = 0.0
    desired_x: float = 0.0


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
        layout_boxes = self._compute_activity_layout(diagram)

        for node in diagram.nodes:
            cell_id = _uid()
            node_cell_ids[node.id] = cell_id
            box = layout_boxes[node.id]

            cell = SubElement(root, "mxCell")
            cell.set("id", cell_id)
            cell.set("value", box.label)
            cell.set("style", box.style)
            cell.set("vertex", "1")
            cell.set("parent", "1")
            geo = SubElement(cell, "mxGeometry")
            geo.set("x", str(int(box.x)))
            geo.set("y", str(int(box.y)))
            geo.set("width", str(int(box.width)))
            geo.set("height", str(int(box.height)))
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

    def _compute_activity_layout(self, diagram: ActivityDiagram) -> dict[str, _ActivityLayoutBox]:
        if not diagram.nodes:
            return {}

        node_index = {node.id: idx for idx, node in enumerate(diagram.nodes)}
        boxes: dict[str, _ActivityLayoutBox] = {
            node.id: self._make_activity_layout_box(node)
            for node in diagram.nodes
        }

        incoming_forward: dict[str, list[tuple[str, object]]] = {node.id: [] for node in diagram.nodes}
        outgoing_forward: dict[str, list[tuple[str, object]]] = {node.id: [] for node in diagram.nodes}
        outgoing_all: dict[str, list[tuple[str, object]]] = {node.id: [] for node in diagram.nodes}
        back_edge_sources: set[str] = set()

        for edge in diagram.edges:
            if edge.source not in boxes or edge.target not in boxes:
                continue
            outgoing_all[edge.source].append((edge.target, edge))
            if node_index[edge.target] > node_index[edge.source]:
                outgoing_forward[edge.source].append((edge.target, edge))
                incoming_forward[edge.target].append((edge.source, edge))
            else:
                back_edge_sources.add(edge.source)

        # Rank assignment on forward graph.
        for node in diagram.nodes:
            preds = incoming_forward.get(node.id, [])
            if preds:
                boxes[node.id].rank = max(boxes[src].rank + 1 for src, _ in preds)
            else:
                boxes[node.id].rank = 0

        rank_nodes: dict[int, list[str]] = {}
        for node in diagram.nodes:
            rank_nodes.setdefault(boxes[node.id].rank, []).append(node.id)

        branch_children_map: dict[str, dict[str, int]] = {}
        for source, children in outgoing_forward.items():
            if len(children) <= 1:
                continue
            ordered = sorted(children, key=lambda item: self._branch_sort_key(item[1], boxes[item[0]]))
            n = len(ordered)
            offsets: list[int] = []
            if n % 2 == 1:
                start = -(n // 2)
                offsets = list(range(start, start + n))
            else:
                half = n // 2
                offsets = list(range(-half, 0)) + list(range(1, half + 1))
            branch_children_map[source] = {target: offsets[idx] for idx, (target, _edge) in enumerate(ordered)}

        horiz_gap = 80
        base_x = 140.0
        min_vertical_gap = 56
        rank_max_heights: dict[int, int] = {}

        for rank in sorted(rank_nodes):
            ids = rank_nodes[rank]
            desired: list[tuple[float, str]] = []
            for node_id in ids:
                preds = incoming_forward.get(node_id, [])
                if not preds:
                    hint = 0.0
                else:
                    suggestions: list[float] = []
                    for source, edge in preds:
                        source_box = boxes[source]
                        suggestion = source_box.x + source_box.width / 2.0
                        branch_offsets = branch_children_map.get(source)
                        if branch_offsets and node_id in branch_offsets:
                            stride = max(boxes[node_id].width + horiz_gap, 220)
                            suggestion += branch_offsets[node_id] * stride
                        if boxes[node_id].style == _STYLE_ACT_EXCEPTION:
                            suggestion += 0.5 * max(boxes[node_id].width + horiz_gap, 180)
                        suggestions.append(suggestion)
                    hint = sum(suggestions) / max(1, len(suggestions))
                if node_id in back_edge_sources:
                    hint += max(boxes[node_id].width * 0.35, 60)
                boxes[node_id].desired_x = hint
                desired.append((hint, node_id))

            desired.sort(key=lambda item: (item[0], node_index[item[1]]))
            placed: list[str] = []
            for hint, node_id in desired:
                box = boxes[node_id]
                center = hint if placed else max(hint, base_x + box.width / 2.0)
                left = center - box.width / 2.0
                if placed:
                    prev = boxes[placed[-1]]
                    prev_right = prev.x + prev.width
                    left = max(left, prev_right + horiz_gap)
                left = max(left, 60.0)
                box.x = left
                placed.append(node_id)

            if placed:
                min_left = min(boxes[node_id].x for node_id in placed)
                max_right = max(boxes[node_id].x + boxes[node_id].width for node_id in placed)
                rank_width = max_right - min_left
                desired_center = base_x + rank_width / 2.0
                actual_center = min_left + rank_width / 2.0
                shift = desired_center - actual_center
                if shift > 0:
                    for node_id in placed:
                        boxes[node_id].x += shift

            rank_max_heights[rank] = max(boxes[node_id].height for node_id in ids)

        current_y = 60.0
        for rank in sorted(rank_nodes):
            ids = rank_nodes[rank]
            for node_id in ids:
                boxes[node_id].y = current_y + (rank_max_heights[rank] - boxes[node_id].height) / 2.0
            current_y += rank_max_heights[rank] + min_vertical_gap

        self._resolve_activity_layout_collisions(boxes, margin_x=32.0, margin_y=20.0)
        return boxes

    def _resolve_activity_layout_collisions(
        self,
        boxes: dict[str, _ActivityLayoutBox],
        *,
        margin_x: float,
        margin_y: float,
    ) -> None:
        ordered = sorted(boxes.values(), key=lambda box: (box.y, box.x))
        for idx, box in enumerate(ordered):
            changed = True
            while changed:
                changed = False
                for prev in ordered[:idx]:
                    if not self._boxes_overlap(prev, box, margin_x=margin_x, margin_y=margin_y):
                        continue
                    box.y = prev.y + prev.height + margin_y
                    changed = True

    @staticmethod
    def _boxes_overlap(
        left: _ActivityLayoutBox,
        right: _ActivityLayoutBox,
        *,
        margin_x: float,
        margin_y: float,
    ) -> bool:
        return not (
            left.x + left.width + margin_x <= right.x
            or right.x + right.width + margin_x <= left.x
            or left.y + left.height + margin_y <= right.y
            or right.y + right.height + margin_y <= left.y
        )

    def _make_activity_layout_box(self, node) -> _ActivityLayoutBox:
        label = self._activity_node_label(node)
        style = self._activity_node_style(node.node_type)
        width, height = self._estimate_activity_node_size(node, label)
        return _ActivityLayoutBox(
            node_id=node.id,
            label=label,
            style=style,
            width=width,
            height=height,
        )

    @staticmethod
    def _activity_node_style(node_type: ActivityNodeType) -> str:
        style_map = {
            ActivityNodeType.INITIAL: _STYLE_ACT_INITIAL,
            ActivityNodeType.FINAL: _STYLE_ACT_FINAL,
            ActivityNodeType.ACTION: _STYLE_ACT_ACTION,
            ActivityNodeType.CALL: _STYLE_ACT_CALL,
            ActivityNodeType.FUNCTION_CALL: _STYLE_ACT_FUNC_CALL,
            ActivityNodeType.DECISION: _STYLE_ACT_DECISION,
            ActivityNodeType.FORK: _STYLE_ACT_FORK_JOIN,
            ActivityNodeType.JOIN: _STYLE_ACT_FORK_JOIN,
            ActivityNodeType.MERGE: _STYLE_ACT_MERGE,
            ActivityNodeType.EXCEPTION: _STYLE_ACT_EXCEPTION,
        }
        return style_map.get(node_type, _STYLE_ACT_ACTION)

    @staticmethod
    def _activity_node_label(node) -> str:
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
        return "\n".join(str(part or "") for part in label_parts if part is not None)

    @staticmethod
    def _estimate_activity_node_size(node, label: str) -> tuple[int, int]:
        lines = [line.strip() for line in label.splitlines()] or [""]
        line_count = max(1, len(lines))
        longest = max((len(line) for line in lines), default=0)

        if node.node_type in (ActivityNodeType.INITIAL, ActivityNodeType.FINAL):
            return 30, 30
        if node.node_type in (ActivityNodeType.FORK, ActivityNodeType.JOIN):
            return 180, 12
        if node.node_type == ActivityNodeType.MERGE:
            return 40, 40

        if node.node_type == ActivityNodeType.DECISION:
            width = max(160, min(280, 110 + longest * 7))
            height = max(90, min(180, 70 + line_count * 22))
            return width, height

        base_width = 220
        if node.node_type == ActivityNodeType.CALL:
            base_width = 260
        elif node.node_type == ActivityNodeType.FUNCTION_CALL:
            base_width = 230
        elif node.node_type == ActivityNodeType.EXCEPTION:
            base_width = 240

        width = max(base_width, min(420, base_width + max(0, longest - 20) * 6))
        height = max(64, min(220, 28 + line_count * 20))
        if node.node_type == ActivityNodeType.EXCEPTION:
            height += 8
        return width, height

    @staticmethod
    def _branch_sort_key(edge, target_box: _ActivityLayoutBox) -> tuple[int, int, str]:
        text = (getattr(edge, "guard", None) or getattr(edge, "label", None) or "").strip().lower()
        if text in {"[true]", "true", "[yes]", "yes"}:
            priority = 0
        elif text in {"[false]", "false", "[no]", "no", "[else]", "else"}:
            priority = 2
        elif text in {"[default]", "default"}:
            priority = 3
        else:
            priority = 1
        type_priority = 1 if target_box.style == _STYLE_ACT_EXCEPTION else 0
        return (priority, type_priority, target_box.node_id)
