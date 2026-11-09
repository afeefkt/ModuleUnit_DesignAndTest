"""CLI for the Agentic Requirements Hardening System (ARHS)."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from .author import harden_all
from .export import export_all
from .parser import parse_any
from .report import write_reports
from .reviewer import review
from .rules import audit, score


def _prepare_run_dir(out_root: str | Path, set_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(out_root) / f"{stamp}_{set_name}"
    for sub in ["00_input", "01_normalized", "02_findings", "03_proposals", "04_reviews", "05_verified", "06_trace", "07_test_design", "08_evidence"]:
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    return run_dir


def run(input_path: str, set_name: str, out_root: str, hardened_root: str) -> dict:
    input_path_obj = Path(input_path)
    out_root_path = Path(out_root)
    hardened_dir = Path(hardened_root) / set_name
    run_dir = _prepare_run_dir(out_root_path, set_name)

    # Preserve the original read-only copy.
    shutil.copy2(input_path_obj, run_dir / "00_input" / input_path_obj.name)

    original = parse_any(input_path_obj)
    with open(run_dir / "01_normalized" / "requirements_normalized.json", "w", encoding="utf-8") as fh:
        json.dump(original, fh, indent=2, ensure_ascii=False)

    baseline_findings = audit(original, stage="baseline")
    baseline_metrics = score(original, baseline_findings)
    with open(run_dir / "02_findings" / "findings_baseline.json", "w", encoding="utf-8") as fh:
        json.dump(baseline_findings, fh, indent=2, ensure_ascii=False)
    with open(run_dir / "05_verified" / "baseline_metrics.json", "w", encoding="utf-8") as fh:
        json.dump(baseline_metrics, fh, indent=2, ensure_ascii=False)

    hardened = harden_all(original, set_name=set_name)
    with open(run_dir / "03_proposals" / "hardened_requirements.json", "w", encoding="utf-8") as fh:
        json.dump(hardened, fh, indent=2, ensure_ascii=False)

    hardened_findings = audit(hardened, stage="hardened")
    hardened_metrics = score(hardened, hardened_findings)
    review_result = review(hardened)

    with open(run_dir / "02_findings" / "findings.json", "w", encoding="utf-8") as fh:
        json.dump(hardened_findings, fh, indent=2, ensure_ascii=False)
    with open(run_dir / "04_reviews" / "review.json", "w", encoding="utf-8") as fh:
        json.dump(review_result, fh, indent=2, ensure_ascii=False)

    paths = export_all(
        hardened,
        hardened_findings,
        review_result,
        hardened_metrics,
        run_dir,
        hardened_dir,
        set_name=set_name,
    )
    paths.update(write_reports(
        original,
        hardened,
        baseline_metrics,
        hardened_metrics,
        hardened_findings,
        review_result,
        run_dir,
        hardened_dir,
    ))

    # Run manifest
    manifest = {
        "set": set_name,
        "input": str(input_path),
        "input_hash": original[0].get("provenance", {}).get("input_hash") if original else "",
        "run_dir": str(run_dir),
        "hardened_dir": str(hardened_dir),
        "requirements": len(original),
        "hardened_requirements": len(hardened),
        "baseline_metrics": baseline_metrics,
        "hardened_metrics": hardened_metrics,
        "review": {k: v for k, v in review_result.items() if k != "reviews"},
        "paths": paths,
        "status": "L2-oriented draft; human review required; not certified",
    }
    with open(run_dir / "run.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    with open(hardened_dir / "run.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agentic Requirements Hardening System")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the full ingest → audit → author → review → export flow")
    run_p.add_argument("--input", required=True, help="Requirement CSV path")
    run_p.add_argument("--set", default="aeb", help="Requirement set name (default: aeb)")
    run_p.add_argument("--out-root", default="outputs/req_hardening", help="Run artifact root")
    run_p.add_argument("--hardened-root", default="inputs/requirements_hardened", help="Hardened baseline root")

    args = parser.parse_args(argv)
    if args.command == "run":
        manifest = run(args.input, args.set, args.out_root, args.hardened_root)
        print(json.dumps({
            "status": manifest["status"],
            "requirements": manifest["requirements"],
            "hardened_requirements": manifest["hardened_requirements"],
            "baseline_score": manifest["baseline_metrics"]["average_score"],
            "hardened_score": manifest["hardened_metrics"]["average_score"],
            "critical_before": manifest["baseline_metrics"]["critical"],
            "critical_after": manifest["hardened_metrics"]["critical"],
            "review": manifest["review"],
            "run_dir": manifest["run_dir"],
            "hardened_dir": manifest["hardened_dir"],
            "review_packet": manifest["paths"].get("review_packet"),
        }, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
