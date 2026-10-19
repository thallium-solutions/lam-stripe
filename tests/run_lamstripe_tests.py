#!/usr/bin/env python3
"""Compile and run the @lam/stripe package tests in an isolated extlibs tree.

Offline tests (``tests/test_*.lam``) run against in-process mock servers and
never see the caller's ``STRIPE_*`` variables. Live tests
(``tests/live_*.lam``) run only with ``--live``, ``LAMSTRIPE_LIVE_TESTS=1``
and a test-mode ``STRIPE_SECRET_KEY`` (``sk_test_...`` or ``rk_test_...``).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


LIB_ROOT = Path(__file__).resolve().parents[1]
COMPILER = "lamc"
MIN_COMPILER_VERSION = (2, 1, 0)
PACKAGE_PATH = Path("@lam") / "stripe"
VERSION_PATTERN = re.compile(r"(?:lamc\s+)?v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?")
LIVE_SWITCH = "LAMSTRIPE_LIVE_TESTS"
TEST_KEY_PREFIXES = ("sk_test_", "rk_test_")


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def _check_compiler() -> bool:
    try:
        proc = _run([COMPILER, "version"], cwd=LIB_ROOT, timeout=10)
    except FileNotFoundError:
        print(f"Error: {COMPILER} is not installed or is not on PATH.", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print(f"Error: {COMPILER} version check timed out.", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"Error: unable to run {COMPILER}: {exc}", file=sys.stderr)
        return False

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit status {proc.returncode}"
        print(f"Error: unable to check {COMPILER} version: {detail}", file=sys.stderr)
        return False

    version_text = proc.stdout.strip()
    match = VERSION_PATTERN.fullmatch(version_text)
    if not match:
        print(f"Error: {COMPILER} returned an invalid version: {version_text!r}.", file=sys.stderr)
        return False

    version = tuple(int(part) for part in match.groups())
    if version < MIN_COMPILER_VERSION:
        required = ".".join(str(part) for part in MIN_COMPILER_VERSION)
        print(
            f"Error: {COMPILER} {version_text} is incompatible; version >= {required} is required.",
            file=sys.stderr,
        )
        return False
    return True


def _expectations(source: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in source.splitlines()
        if (match := re.match(r"^\s*#\s*expect:\s*(.*)$", line))
    ]


def _stage_package(extlibs: Path) -> None:
    destination = extlibs / PACKAGE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        LIB_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            "build",
            "extlibs",
            "tests",
            "*.lamc-cache",
            "__pycache__",
            "*.pyc",
        ),
    )


def _process_failure(label: str, proc: subprocess.CompletedProcess[str]) -> str:
    details = [f"{label} ({proc.returncode})"]
    if proc.stdout.strip():
        details.append("stdout:\n" + proc.stdout.rstrip())
    if proc.stderr.strip():
        details.append("stderr:\n" + proc.stderr.rstrip())
    return "\n".join(details)


def _offline_env() -> dict[str, str]:
    """The caller's environment without Stripe credentials or switches."""
    return {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("STRIPE_") and name != LIVE_SWITCH
    }


def _run_case(path: Path, live: bool) -> tuple[bool, str]:
    expected = _expectations(path.read_text(encoding="utf-8"))
    if not expected:
        return False, "TEST ERROR: no '# expect:' lines found"

    with tempfile.TemporaryDirectory(prefix="lamstripe_test_") as tmp:
        root = Path(tmp)
        extlibs = root / "extlibs"
        _stage_package(extlibs)
        binary = root / "test_binary"
        command = [
            COMPILER,
            str(path),
            "--extlibs",
            str(extlibs),
            "--no-cache",
            "-o",
            str(binary),
        ]
        try:
            compile_proc = _run(command, cwd=root, timeout=300)
        except subprocess.TimeoutExpired:
            return False, "COMPILE FAIL: timed out after 300 seconds"
        except OSError as exc:
            return False, f"COMPILE FAIL: unable to run {COMPILER}: {exc}"
        if compile_proc.returncode != 0:
            return False, _process_failure("COMPILE FAIL", compile_proc)

        env = dict(os.environ) if live else _offline_env()
        try:
            run_proc = _run([str(binary)], cwd=root, timeout=120, env=env)
        except subprocess.TimeoutExpired:
            return False, "RUN FAIL: timed out after 120 seconds"
        except OSError as exc:
            return False, f"RUN FAIL: unable to execute test binary: {exc}"
        if run_proc.returncode != 0:
            return False, _process_failure("RUN FAIL", run_proc)

        actual = run_proc.stdout.rstrip("\n")
        expected_text = "\n".join(expected)
        if actual != expected_text:
            return (
                False,
                "OUTPUT MISMATCH:\n"
                f"  expected: {expected_text!r}\n"
                f"  actual:   {actual!r}"
                + (f"\n  stderr:   {run_proc.stderr.rstrip()!r}" if run_proc.stderr else ""),
            )
        return True, "ok"


def _live_ready() -> tuple[bool, str]:
    if os.environ.get(LIVE_SWITCH, "") != "1":
        return False, f"set {LIVE_SWITCH}=1 to run live Stripe tests"
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith(TEST_KEY_PREFIXES):
        return False, "STRIPE_SECRET_KEY must be a test-mode key (sk_test_... or rk_test_...)"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="@lam/stripe package tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="show full failure details")
    parser.add_argument(
        "--live",
        action="store_true",
        help=f"also run tests/live_*.lam against the Stripe API ({LIVE_SWITCH}=1 and a test-mode STRIPE_SECRET_KEY)",
    )
    parser.add_argument("--jobs", "-j", type=int, default=os.cpu_count() or 2, help="parallel test builds")
    parser.add_argument("filters", nargs="*", help="only run tests whose file name contains one of these")
    args = parser.parse_args()

    if not _check_compiler():
        return 1

    cases = [(case, False) for case in sorted((LIB_ROOT / "tests").glob("test_*.lam"))]
    if args.live:
        ready, reason = _live_ready()
        if not ready:
            print(f"Error: --live refused: {reason}.", file=sys.stderr)
            return 1
        cases += [(case, True) for case in sorted((LIB_ROOT / "tests").glob("live_*.lam"))]
    if args.filters:
        cases = [(case, live) for case, live in cases if any(f in case.name for f in args.filters)]
    if not cases:
        print("Error: no @lam/stripe test cases found.", file=sys.stderr)
        return 1

    print(f"Running {len(cases)} @lam/stripe test(s)...\n")
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(lambda item: _run_case(*item), cases))

    failures: list[tuple[Path, str]] = []
    for (case, _live), (ok, message) in zip(cases, results):
        relative = case.relative_to(LIB_ROOT)
        print(f"  {'PASS' if ok else 'FAIL'}  {relative}")
        if not ok:
            failures.append((relative, message))
            if args.verbose:
                for line in message.splitlines():
                    print(f"        {line}")

    passed = len(cases) - len(failures)
    print(f"\n@lam/stripe results: {passed} passed, {len(failures)} failed, {len(cases)} total")
    if failures and not args.verbose:
        print("Re-run with --verbose for failure details.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
