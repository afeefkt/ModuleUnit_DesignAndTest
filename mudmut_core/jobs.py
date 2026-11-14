"""Run long pipeline actions in a background thread and expose their progress.

A Streamlit script that blocks on a long run cannot show a live bar and loses the run when
you change page. A :class:`Job` runs in a worker thread; pages poll :func:`current` /
:func:`get` (e.g. in an ``st.fragment(run_every=1)``) to draw the bar, and the run keeps going
while you look at other pages.
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from mudmut_core import progress as progress_mod

_lock = threading.Lock()
_jobs: dict[str, "Job"] = {}
_KEEP = 10


class Cancelled(Exception):
    """Raised by work that stopped because the user pressed Cancel."""


@dataclass
class Job:
    id: str
    label: str
    quick: bool = False
    status: str = "running"            # running | done | error | cancelled
    started: float = field(default_factory=time.time)
    finished: Optional[float] = None
    percent: int = 0
    stage: str = ""
    step: tuple[int, int] = (1, 1)
    message: str = ""
    eta: Optional[float] = None
    error: str = ""
    result: Any = None
    log: list[str] = field(default_factory=list)
    tracker: Optional[progress_mod.ProgressTracker] = None
    expected: Optional[float] = None    # seconds, for jobs without a stage tracker
    fraction: Optional[float] = None    # exact progress reported by the work itself (0..1)
    run_folder: str = ""                # set when the work reports its run workspace
    stages_done: list[str] = field(default_factory=list)   # pipeline stages finished (current run folder)
    cancel_flag: threading.Event = field(default_factory=threading.Event)

    @property
    def cancel_requested(self) -> bool:
        return self.cancel_flag.is_set()

    def stage_state(self, stage: str) -> str:
        """``done`` / ``running`` / ``pending`` for one pipeline stage (drives the live stage rail)."""
        if stage in self.stages_done:
            return "done"
        order = [s for s in progress_mod.ORDER if not (self.quick and s == "review")]
        remaining = [s for s in order if s not in self.stages_done]
        if self.running and remaining and remaining[0] == stage:
            return "running"
        return "pending"

    @property
    def running(self) -> bool:
        return self.status == "running"

    @property
    def elapsed(self) -> float:
        return (self.finished or time.time()) - self.started

    def refresh(self) -> None:
        """Recompute percent / stage / eta (the bar also moves between events)."""
        t = self.tracker
        if not self.running:
            return
        if t is None:
            if self.fraction is not None:
                self.percent = min(99, int(100 * self.fraction))
            elif self.expected:
                self.percent = min(95, int(100 * self.elapsed / max(self.expected, 1.0)))
            if self.percent >= 3:
                self.eta = max(0.0, self.elapsed * (100 - self.percent) / self.percent)
            return
        self.percent = t.percent
        self.stage = t.stage_label
        self.step = t.step
        self.eta = t.eta_seconds


def start(label: str, fn: Callable[[Callable[[dict], None]], Any], *, quick: bool = False,
          track: bool = True, expected_seconds: Optional[float] = None) -> Job:
    """Start ``fn(progress)`` in a thread. ``progress(event)`` feeds the bar and the log.

    Only one job of the same label runs at a time: if one is already running it is returned.
    """
    with _lock:
        for job in _jobs.values():
            if job.running and job.label == label:
                return job
        job = Job(id=uuid.uuid4().hex[:8], label=label, quick=quick,
                  tracker=progress_mod.ProgressTracker(quick=quick) if track else None,
                  expected=expected_seconds)
        _jobs[job.id] = job
        for old in sorted(_jobs.values(), key=lambda j: j.started)[:-_KEEP]:
            if not old.running:
                _jobs.pop(old.id, None)

    def on_event(event: dict) -> None:
        if event.get("run_folder"):
            if event["run_folder"] != job.run_folder:
                # a new run workspace (e.g. the next SWC of a multi-SWC job): restart the rail
                job.stages_done = [s for s in job.stages_done if s in ("import", "plan")]
            job.run_folder = event["run_folder"]
        if event.get("done") and event.get("stage") in progress_mod.ORDER and event["stage"] not in job.stages_done:
            job.stages_done.append(event["stage"])
        if job.tracker is not None:
            job.tracker.update(event)
        elif event.get("fraction") is not None:
            job.fraction = max(0.0, min(0.99, float(event["fraction"])))
            job.stage = event.get("stage", job.stage)
        msg = event.get("message")
        if msg:
            job.message = msg
            job.log.append(f"[{event.get('stage', '?')}] {msg}")
            del job.log[:-200]
        job.refresh()

    # The work can poll ``progress.cancelled()`` and stop at a safe point.
    on_event.cancelled = lambda: job.cancel_flag.is_set()  # type: ignore[attr-defined]

    def run() -> None:
        try:
            job.result = fn(on_event)
            if job.tracker is not None:
                job.tracker.complete()
            job.percent, job.eta = 100, 0.0
            job.status = "done"
        except (Cancelled, asyncio.CancelledError) as exc:
            if not isinstance(exc, Cancelled) and not job.cancel_flag.is_set():
                job.status, job.error = "error", "Interrupted"
            else:
                job.status = "cancelled"
                job.error = str(exc) or "Cancelled by you"
                job.log.append(f"[cancel] {job.error}")
            _close_running_calls(job.error or "Cancelled")
        except BaseException as exc:  # noqa: BLE001 - reported to the UI, never raised here
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            job.log.append(traceback.format_exc(limit=4))
        finally:
            job.finished = time.time()

    threading.Thread(target=run, name=f"job-{job.id}", daemon=True).start()
    return job


def _close_running_calls(reason: str) -> None:
    """Mark model calls still shown as running in the AI monitor as stopped."""
    try:
        from mudmut_core.llm import observe
        observe.cancel_running(reason)
    except Exception:  # noqa: BLE001
        pass


def get(job_id: str) -> Optional[Job]:
    job = _jobs.get(job_id)
    if job:
        job.refresh()
    return job


def current(label: Optional[str] = None) -> Optional[Job]:
    """The running job (optionally with ``label``), else the most recent one."""
    with _lock:
        jobs = [j for j in _jobs.values() if label is None or j.label == label]
    if not jobs:
        return None
    running = [j for j in jobs if j.running]
    job = running[-1] if running else max(jobs, key=lambda j: j.started)
    job.refresh()
    return job


def request_cancel(job_id: str) -> bool:
    """Ask a running job to stop at its next safe point. Returns False if it is not running."""
    job = _jobs.get(job_id)
    if job is None or not job.running:
        return False
    job.cancel_flag.set()
    job.message = "Cancelling — stopping the running AI request…"
    # Abort the request that is running now (closes the connection, so the model server stops
    # generating) instead of waiting for the current step to finish.
    try:
        from mudmut_core import aio
        aio.cancel_current()
    except Exception:  # noqa: BLE001
        pass
    return True


def any_running() -> bool:
    with _lock:
        return any(j.running for j in _jobs.values())


def forget(job_id: str) -> bool:
    """Drop one finished job (its result has been shown and saved). Running jobs are kept."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job.running:
            return False
        _jobs.pop(job_id, None)
    return True


def clear_finished() -> int:
    """Forget finished jobs (their run folders stay on disk). Returns how many were removed."""
    with _lock:
        ids = [j.id for j in _jobs.values() if not j.running]
        for jid in ids:
            _jobs.pop(jid, None)
    return len(ids)
