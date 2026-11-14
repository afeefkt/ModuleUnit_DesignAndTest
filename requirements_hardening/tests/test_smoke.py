"""Smoke tests for the AEB requirements hardening MVP."""

from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from requirements_hardening.cli import run
from requirements_hardening.parser import parse_any

ROOT = Path(__file__).resolve().parents[2]
AEB = ROOT / "inputs" / "requirements" / "aeb" / "aeb_requirements.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestAebHardening(unittest.TestCase):
    def test_parse_66_rows(self) -> None:
        reqs = parse_any(AEB)
        self.assertEqual(len(reqs), 66)
        self.assertEqual(len({r["id"] for r in reqs}), 66)

    def test_end_to_end(self) -> None:
        before = sha256(AEB)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = run(
                input_path=str(AEB),
                set_name="aeb",
                out_root=str(tmp_path / "outputs"),
                hardened_root=str(tmp_path / "hardened"),
            )
            self.assertEqual(manifest["requirements"], 66)
            self.assertGreaterEqual(manifest["hardened_requirements"], 120)
            self.assertGreater(manifest["hardened_metrics"]["average_score"], manifest["baseline_metrics"]["average_score"])
            self.assertEqual(manifest["hardened_metrics"]["critical"], 0)
            self.assertEqual(manifest["hardened_metrics"]["major"], 0)
            self.assertEqual(manifest["hardened_metrics"]["compound_candidates"], 0)
            self.assertEqual(sha256(AEB), before)

            hardened_csv = Path(manifest["paths"]["hardened_csv"])
            with open(hardened_csv, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), manifest["hardened_requirements"])

            with open(Path(manifest["paths"]["test_design"]), newline="", encoding="utf-8") as fh:
                tests = list(csv.DictReader(fh))
            self.assertEqual(len(tests), manifest["hardened_requirements"])

            with open(Path(manifest["paths"]["extended_json"]), encoding="utf-8") as fh:
                import json
                hardened = json.load(fh)
            self.assertEqual(len(hardened), manifest["hardened_requirements"])
            for req in hardened:
                self.assertTrue(req["acceptance_criteria"]["then"], req["id"])
                self.assertIn(req["verification_method"], {"test", "analysis", "review", "inspection"})
                self.assertTrue(req["links"]["test"], req["id"])
                self.assertTrue(req["parent_ids"] or req["level"] == "system", req["id"])
            split_ids = {req["id"] for req in hardened if req.get("split_from")}
            self.assertEqual(len(split_ids), 40)

    def test_other_sets(self) -> None:
        cases = {
            "bms": (ROOT / "inputs" / "requirements" / "samples" / "bms_requirements.csv", 62),
            "eps": (ROOT / "inputs" / "requirements" / "samples" / "eps_requirements.csv", 98),
            "foc": (ROOT / "inputs" / "requirements" / "samples" / "Motcontrolcomp.csv", 48),
        }
        for set_name, (path, minimum) in cases.items():
            before = sha256(path)
            with tempfile.TemporaryDirectory() as tmp:
                manifest = run(
                    input_path=str(path),
                    set_name=set_name,
                    out_root=str(Path(tmp) / "outputs"),
                    hardened_root=str(Path(tmp) / "hardened"),
                )
                self.assertGreaterEqual(manifest["hardened_requirements"], minimum)
                self.assertEqual(manifest["hardened_metrics"]["critical"], 0)
                self.assertEqual(manifest["hardened_metrics"]["major"], 0)
                self.assertEqual(manifest["hardened_metrics"]["compound_candidates"], 0)
                self.assertEqual(sha256(path), before)

    def test_idempotent_parse(self) -> None:
        first = parse_any(AEB)
        second = parse_any(AEB)
        self.assertEqual([r["id"] for r in first], [r["id"] for r in second])
        self.assertEqual(first[0]["provenance"]["input_hash"], second[0]["provenance"]["input_hash"])


if __name__ == "__main__":
    unittest.main()
