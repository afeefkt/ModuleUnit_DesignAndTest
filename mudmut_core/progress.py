"""Percent-complete estimate for a pipeline run.

The percentage is an *estimate*: each stage has a weight (its typical share of the total
time, from real runs) and the stage in progress counts as the fraction of its expected
duration that has elapsed (or an exact fraction when the engine reports one, e.g. tests
generated per function). It never reaches 100 % until the run is marked complete.

Measured stage durations are stored in ``config/stage_timings.json`` (moving average) so the
weights and the "about N min left" figure adapt to this machine and model choice.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT

TIMINGS_FILE = REPO_ROOT / "config" / "stage_timings.json"

ORDER = ("import", "plan", "spec", "review", "activity", "compilable", "generate_tests", "build_run", "trace")

# Typical share of the total time (local 7-8 B models, from the verified quick run:
# plan 110 s, spec 490 s, tests 99 s, build 62 s). Review and AI activity only run in full mode.
_BASE_WEIGHTS = {
    "import": 1, "plan": 14, "spec": 58, "review": 15, "activity": 10,
    "compilable": 2, "generate_tests": 14, "build_run": 9, "trace": 1,
}
_QUICK_WEIGHTS = {**_BASE_WEIGHTS, "activity": 1}
_BASE_TOTAL_SECONDS = 800.0


def stages_for(quick: bool) -> list[str]:
    return [s for s in ORDER if not (quick and s == "review")]


def load_timings() -> dict[str, float]:
    try:
        return json.loads(TIMINGS_FILE.read_text(encoding="utf-8")) if TIMINGS_FILE.is_file() else {}
    except (OSError, ValueError):
        return {}


def record_timings(durations: dict[str, float], *, quick: bool) -> None:
    """Fold a finished run's stage durations into the moving average (best effort)."""
    try:
        data = load_timings()
        key_prefix = "quick" if quick else "full"
        for stage, seconds in durations.items():
            if stage not in ORDER or seconds is None:
                continue
            key = f"{key_prefix}:{stage}"
            old = data.get(key)
            data[key] = round(seconds if old is None else 0.7 * old + 0.3 * seconds, 2)
        TIMINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TIMINGS_FILE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass


def expected_seconds(quick: bool, timings: Optional[dict[str, float]] = None) -> dict[str, float]:
    """Expected duration per stage: measured average if known, else the default share."""
    timings = timings if timings is not None else load_timings()
    weights = _QUICK_WEIGHTS if quick else _BASE_WEIGHTS
    prefix = "quick" if quick else "full"
    out: dict[str, float] = {}
    for stage in stages_for(quick):
        measured = timings.get(f"{prefix}:{stage}")
        out[stage] = max(float(measured), 0.5) if measured else _BASE_TOTAL_SECONDS * weights[stage] / 100.0
    return out


class ProgressTracker:
    """Turn pipeline events into ``percent`` / ``stage`` / ``eta`` for a progress bar."""

    def __init__(self, quick: bool = False, timings: Optional[dict[str, float]] = None):
        self.quick = quick
        self.stages = stages_for(quick)
        self.expected = expected_seconds(quick, timings)
        self._total = sum(self.expected.values())
        self.done: set[str] = set()
        self.durations: dict[str, float] = {}
        self.current: Optional[str] = self.stages[0]
        self._stage_started = time.monotonic()
        self._fraction: Optional[float] = None
        self._complete = False
        self.started = time.monotonic()
        self.message = ""

    # -- events ---------------------------------------------------------------
    def update(self, event: dict[str, Any]) -> None:
        """Feed one chain progress event (``stage``, ``message``, optional ``done`` / ``fraction``)."""
        stage = event.get("stage")
        self.message = event.get("message", self.message)
        if stage not in self.stages:
            return
        if event.get("done"):
            self.finish(stage)
        elif event.get("fraction") is not None and stage == self.current:
            self._fraction = max(0.0, min(0.99, float(event["fraction"])))

    def finish(self, stage: str) -> None:
        if stage in self.done or stage not in self.stages:
            return
        now = time.monotonic()
        if stage == self.current:
            self.durations[stage] = now - self._stage_started
        self.done.add(stage)
        remaining = [s for s in self.stages if s not in self.done]
        self.current = remaining[0] if remaining else None
        self._stage_started = now
        self._fraction = None

    def complete(self) -> None:
        for stage in self.stages:
            self.finish(stage)
        self._complete = True

    # -- readings -------------------------------------------------------------
    @property
    def percent(self) -> int:
        if self._complete:
            return 100
        finished = sum(self.expected[s] for s in self.done)
        partial = 0.0
        if self.current:
            frac = self._fraction
            if frac is None:
                elapsed = time.monotonic() - self._stage_started
                frac = min(0.95, elapsed / max(self.expected[self.current], 0.5))
            partial = self.expected[self.current] * frac
        return min(99, int(100 * (finished + partial) / self._total)) if self._total else 0

    @property
    def stage_label(self) -> str:
        return self.current or "finishing"

    @property
    def step(self) -> tuple[int, int]:
        """(1-based index of the running stage, number of stages)."""
        if self.current is None:
            return len(self.stages), len(self.stages)
        return self.stages.index(self.current) + 1, len(self.stages)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    @property
    def eta_seconds(self) -> Optional[float]:
        if self._complete:
            return 0.0
        p = self.percent
        if p < 3:
            return None
        return max(0.0, self.elapsed * (100 - p) / p)


def fmt_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "estimating…"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"
