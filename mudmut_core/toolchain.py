"""Toolchain detection and native/WSL ``make`` execution.

Detects a native Linux ``make`` or a Windows ``wsl.exe`` and reports the
presence/version of every tool the C/C++ build needs (gcc, g++, make, gcov,
CppUTest, lcov), with the exact install command when something is missing.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_IS_WINDOWS = platform.system() == "Windows"

APT_INSTALL_CPPUTEST_LCOV = "wsl -u root -e apt-get install -y cpputest lcov"


def _which(*names: str) -> Optional[str]:
    for name in names:
        p = shutil.which(name)
        if p:
            return p
    return None


def wsl_path(path: Path | str) -> str:
    """Convert a Windows path (``D:\\x\\y``) to its WSL form (``/mnt/d/x/y``)."""
    s = str(path).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        s = f"/mnt/{s[0].lower()}" + s[2:]
    return s


def detect_make_prefix() -> list[str]:
    """Return the command prefix to run ``make`` (empty for native Linux, ``wsl.exe`` on Windows)."""
    if _IS_WINDOWS:
        wsl = _which("wsl.exe", "wsl")
        if wsl:
            return [wsl]
    return []


def _shell(script: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a bash snippet natively (Linux) or inside WSL (Windows), in the C locale.

    ``LC_ALL=C`` keeps compiler diagnostics in plain ASCII quotes; output is
    decoded as UTF-8 because wsl.exe forwards the Linux bytes unchanged.
    """
    # The script goes over stdin: multi-line arguments do not survive the
    # Windows command line that wsl.exe re-parses.
    # Bytes, not text: text-mode stdin on Windows would turn \n into \r\n.
    cmd = detect_make_prefix() + ["env", "LC_ALL=C", "bash", "-s"]
    proc = subprocess.run(
        cmd, input=script.encode("utf-8"), capture_output=True, timeout=timeout,
    )
    return subprocess.CompletedProcess(
        proc.args, proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


# One probe for every tool, run where the build runs (natively or in WSL).
_PROBE = r"""
v() { command -v "$1" >/dev/null 2>&1 && "$1" --version 2>/dev/null | head -n1 || echo MISSING; }
echo "gcc=$(v gcc)"
echo "g++=$(v g++)"
echo "make=$(v make)"
echo "gcov=$(command -v gcov >/dev/null 2>&1 && echo present || echo MISSING)"
echo "lcov=$(v lcov)"
h=MISSING; for d in /usr/include /usr/local/include; do [ -f "$d/CppUTest/TestHarness.h" ] && h="$d/CppUTest/TestHarness.h" && break; done
l=MISSING; for d in /usr/lib/x86_64-linux-gnu /usr/lib /usr/local/lib; do for n in libCppUTest.a libCppUTest.so; do [ -f "$d/$n" ] && l="$d/$n" && break 2; done; done
echo "cpputest_header=$h"
echo "cpputest_lib=$l"
"""


@dataclass
class ToolStatus:
    name: str
    available: bool
    detail: str = ""
    install_hint: str = ""


@dataclass
class ToolchainReport:
    tools: list[ToolStatus] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return all(t.available for t in self.tools)

    def missing(self) -> list[ToolStatus]:
        return [t for t in self.tools if not t.available]


def check_toolchain() -> ToolchainReport:
    """Report the presence/version of every tool the C/C++ build needs.

    Probes run where the build runs: natively on Linux, inside WSL on Windows
    (probing the Windows PATH would always report the Linux tools missing).
    """
    report = ToolchainReport()
    try:
        proc = _shell(_PROBE)
        found = dict(
            line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line
        )
    except Exception as exc:  # noqa: BLE001 - e.g. no WSL installed
        found = {}
        report.error = f"could not run the toolchain probe: {exc}"

    def add(name: str, key: str, hint: str) -> None:
        val = found.get(key, "").strip() or "MISSING"
        report.tools.append(ToolStatus(name, val != "MISSING", val if val != "MISSING" else "not found", hint))

    add("gcc", "gcc", "apt-get install -y gcc")
    add("g++", "g++", "apt-get install -y g++")
    add("make", "make", "apt-get install -y make")
    add("gcov", "gcov", "apt-get install -y gcc")
    hdr = found.get("cpputest_header", "").strip() or "MISSING"
    lib = found.get("cpputest_lib", "").strip() or "MISSING"
    report.tools.append(ToolStatus(
        "CppUTest", hdr != "MISSING" and lib != "MISSING",
        f"{hdr if hdr != 'MISSING' else 'headers missing'} + {lib if lib != 'MISSING' else 'lib missing'}",
        APT_INSTALL_CPPUTEST_LCOV,
    ))
    add("lcov", "lcov", APT_INSTALL_CPPUTEST_LCOV)
    return report


@dataclass
class MakeResult:
    targets: list[str]
    returncode: int
    stdout: str
    stderr: str
    command: list[str]

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_make(
    test_dir: Path | str,
    targets: tuple[str, ...] = ("clean", "all"),
    timeout: int = 300,
) -> MakeResult:
    """Run ``make <targets>`` in ``test_dir`` (natively, or via WSL on Windows)."""
    directory = wsl_path(test_dir) if _IS_WINDOWS else str(test_dir)
    cmd = detect_make_prefix() + ["env", "LC_ALL=C", "make", "-C", directory] + list(targets)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return MakeResult(
        targets=list(targets),
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        command=cmd,
    )


def run_c(
    args: list[str],
    *,
    cwd: Optional[Path | str] = None,
    timeout: int = 120,
) -> MakeResult:
    """Run a native C toolchain command (e.g. gcc) — via WSL on Windows.

    Windows paths in ``args`` are auto-converted to WSL form.
    """
    converted = []
    for a in map(str, args):
        if _IS_WINDOWS:
            if a.startswith("-I"):
                a = "-I" + wsl_path(a[2:])
            elif not a.startswith("-"):
                a = wsl_path(a)
        converted.append(a)
    cmd = detect_make_prefix() + ["env", "LC_ALL=C"] + converted
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, cwd=cwd,
    )
    return MakeResult(
        targets=list(args),
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        command=cmd,
    )
