"""The reconvergence point of a decision is the NEAREST common merge, not the alphabetically first id."""
from types import SimpleNamespace

from mudtool.generator.c_skeleton_exporter import CSkeletonExporter
from mudtool.models.json_uml import ActivityNodeType


def _node(kind):
    return SimpleNamespace(node_type=kind)


def test_find_join_prefers_nearest_merge_over_lower_sorting_id():
    node_map = {
        "N_21": _node(ActivityNodeType.DECISION), "N_22": _node(ActivityNodeType.ACTION),
        "N_24": _node(ActivityNodeType.MERGE), "N_25": _node(ActivityNodeType.DECISION),
        "N_26": _node(ActivityNodeType.ACTION), "N_100": _node(ActivityNodeType.MERGE),
        "N_101": _node(ActivityNodeType.FINAL),
    }
    outgoing = {"N_21": ["N_22", "N_24"], "N_22": ["N_24"], "N_24": ["N_25"],
                "N_25": ["N_26", "N_100"], "N_26": ["N_100"], "N_100": ["N_101"]}
    exporter = CSkeletonExporter()
    assert exporter._find_join("N_21", node_map, outgoing) == "N_24"      # "N_100" < "N_24" as strings
    assert exporter._find_join("N_25", node_map, outgoing) == "N_100"
