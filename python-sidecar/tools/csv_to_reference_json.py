"""Convert EPS_MUD_Enhanced.csv (19-column tabular MUD spec) to a structured
JSON reference file that can be used as few-shot examples in generation prompts.

Usage:
    python tools/csv_to_reference_json.py \
        --csv "C:/Users/afeef/Downloads/EPS_MUD_Enhanced.csv" \
        --out "knowledge/eps_reference.json"

Output format:
    {
        "swc": { ... SUMMARY row ... },
        "input_ports": [ ...IN rows... ],
        "output_ports": [ ...OUT rows... ],
        "internal_vars": [ ...INTERNAL_VAR rows... ],
        "calib_params": [ ...CALIB_PARAM rows... ],
        "runnables": [ ...RUNNABLE rows... ],
        "dem_events": [ ...DEM_EVENT rows... ],
        "fim": [ ...FIM rows... ],
        "wdgm": [ ...WDGM rows... ],
        "few_shot_prompts": {
            "input_port_example": "...",
            "output_port_example": "...",
            "runnable_example": "...",
            "calib_param_example": "...",
        }
    }
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


# ── Column names (order from EPS_MUD_Enhanced.csv header) ────────────────────

COLUMNS = [
    "Section", "ID", "Name", "Description_PseudoCode",
    "Data_Type", "Range", "Unit", "Trigger_Timing",
    "ASIL", "AUTOSAR_Concept", "Runnable_Mapping",
    "Port_Interface", "SW_CalibrationParameter",
    "Error_Handling", "Diagnostic_Event",
    "Memory_Section", "Execution_Order",
    "Trace_Requirement", "Notes",
]

SECTION_MAP = {
    "SUMMARY":       "swc",
    "INPUT_PORT":    "input_ports",
    "OUTPUT_PORT":   "output_ports",
    "INTERNAL_VAR":  "internal_vars",
    "CALIB_PARAM":   "calib_params",
    "RUNNABLE":      "runnables",
    "DEM_EVENT":     "dem_events",
    "FIM":           "fim",
    "WDGM":          "wdgm",
}


def read_csv(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header row
        for raw_row in reader:
            if not any(cell.strip() for cell in raw_row):
                continue  # skip blank lines
            # Pad / trim to expected column count
            padded = (raw_row + [""] * len(COLUMNS))[:len(COLUMNS)]
            row_dict = {col: padded[i].strip() for i, col in enumerate(COLUMNS)}
            rows.append(row_dict)
    return rows


def convert(rows: list[dict]) -> dict:
    result: dict = {
        "swc": {},
        "input_ports": [],
        "output_ports": [],
        "internal_vars": [],
        "calib_params": [],
        "runnables": [],
        "dem_events": [],
        "fim": [],
        "wdgm": [],
    }

    for row in rows:
        section = row.get("Section", "").upper().strip()
        key = SECTION_MAP.get(section)
        if key is None:
            continue

        item = {col: row[col] for col in COLUMNS if row.get(col)}

        if key == "swc":
            result["swc"] = item
        else:
            result[key].append(item)

    # ── Build few-shot prompt snippets ────────────────────────────────────────
    few_shot: dict[str, str] = {}

    # Input port example
    if result["input_ports"]:
        p = result["input_ports"][0]
        few_shot["input_port_example"] = _format_port_example(p, "required")

    # Output port example
    if result["output_ports"]:
        p = result["output_ports"][0]
        few_shot["output_port_example"] = _format_port_example(p, "provided")

    # Runnable example (first runnable with non-trivial pseudo-code)
    for r in result["runnables"]:
        pseudo = r.get("Description_PseudoCode", "")
        if len(pseudo) > 100:
            few_shot["runnable_example"] = _format_runnable_example(r)
            break

    # Calibration parameter example
    if result["calib_params"]:
        cp = result["calib_params"][0]
        few_shot["calib_param_example"] = _format_calib_example(cp)

    result["few_shot_prompts"] = few_shot
    return result


def _format_port_example(p: dict, direction: str) -> str:
    lines = [
        f"Port: {p.get('Name', '')} ({direction})",
        f"  Interface: {p.get('AUTOSAR_Concept', '')}",
        f"  RTE call:  {p.get('Port_Interface', '')}",
        f"  Data Type: {p.get('Data_Type', '')}  Range: {p.get('Range', '')} {p.get('Unit', '')}",
        f"  Trigger:   {p.get('Trigger_Timing', '')}  ASIL: {p.get('ASIL', '')}",
        f"  Error handling: {p.get('Error_Handling', '')}",
        f"  DEM event: {p.get('Diagnostic_Event', '')}",
        f"  Notes: {p.get('Notes', '')}",
    ]
    return "\n".join(l for l in lines if l.strip() and not l.endswith(": "))


def _format_runnable_example(r: dict) -> str:
    pseudo = r.get("Description_PseudoCode", "")
    lines = [
        f"Runnable: {r.get('Name', '')}",
        f"  Trigger: {r.get('Trigger_Timing', '')}  ASIL: {r.get('ASIL', '')}",
        f"  Port Interface: {r.get('Port_Interface', '')}",
        f"  CalPrm: {r.get('SW_CalibrationParameter', '')}",
        f"  Error handling: {r.get('Error_Handling', '')}",
        f"  DEM event: {r.get('Diagnostic_Event', '')}",
        "",
        "  PSEUDO-CODE:",
    ]
    for pseudo_line in pseudo.splitlines():
        lines.append(f"    {pseudo_line}")
    return "\n".join(l for l in lines if l.strip() != "")


def _format_calib_example(cp: dict) -> str:
    lines = [
        f"CalPrm: {cp.get('Name', '')}",
        f"  Port: {cp.get('Port_Interface', '')}",
        f"  Data Type: {cp.get('Data_Type', '')}",
        f"  Range: {cp.get('Range', '')} {cp.get('Unit', '')}",
        f"  Default: {cp.get('SW_CalibrationParameter', '')}",
        f"  Memory: {cp.get('Memory_Section', '')}",
        f"  Notes: {cp.get('Notes', '')}",
    ]
    return "\n".join(l for l in lines if l.strip() and not l.endswith(": "))


def print_summary(result: dict) -> None:
    print(f"  SWC:          {result['swc'].get('Name', '?')}")
    print(f"  Input ports:  {len(result['input_ports'])}")
    print(f"  Output ports: {len(result['output_ports'])}")
    print(f"  Int. vars:    {len(result['internal_vars'])}")
    print(f"  CalPrm:       {len(result['calib_params'])}")
    print(f"  Runnables:    {len(result['runnables'])}")
    print(f"  DEM events:   {len(result['dem_events'])}")
    print(f"  FiM:          {len(result['fim'])}")
    print(f"  WdgM:         {len(result['wdgm'])}")
    print(f"  Few-shot:     {list(result['few_shot_prompts'].keys())}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert EPS MUD CSV to reference JSON")
    parser.add_argument(
        "--csv", required=True,
        help="Path to EPS_MUD_Enhanced.csv (19-column format)",
    )
    parser.add_argument(
        "--out",
        default="knowledge/eps_reference.json",
        help="Output JSON path (default: knowledge/eps_reference.json)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    out_path = Path(args.out)

    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading {csv_path}…")
    rows = read_csv(csv_path)
    print(f"Read {len(rows)} rows")

    result = convert(rows)

    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Written to {out_path}")
    print_summary(result)
    print("\nFew-shot prompt preview:")
    for key, snippet in result["few_shot_prompts"].items():
        print(f"\n  [{key}]")
        for line in snippet.splitlines()[:5]:
            print(f"    {line}")


if __name__ == "__main__":
    main()
