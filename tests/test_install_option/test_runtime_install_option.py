"""
dx-runtime install.sh option tests.

Runs install.sh directly on the host (no Docker) and verifies that each
option combination succeeds and produces expected output.

Safety defaults appended to every real installation case:
  --exclude-fw --exclude-driver  (no NPU hardware assumed on test host)
  --sanity-check=n               (no physical device to sanity-check against)

The --exclude-* tests additionally assert that the corresponding "SKIP"
line appears in stdout so we know the flag was actually honoured.
"""

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.install_option, pytest.mark.runtime]

RUNTIME_DIR = Path(__file__).resolve().parents[2] / "dx-runtime"
TIMEOUT = 3600

# Safety flags appended to every case that performs a real installation.
_SAFE = ["--exclude-fw", "--exclude-driver", "--sanity-check=n"]

# (case_id, extra_args, expected_skip_pattern_or_None)
CASES = [
    ("runtime-only",         ["--runtime-only",  *_SAFE],                       None),
    ("all",                  ["--all",            *_SAFE],                       None),
    ("all-exclude-app",      ["--all", "--exclude-app",    *_SAFE],  "Skipping dx_app"),
    ("all-exclude-stream",   ["--all", "--exclude-stream", *_SAFE],  "Skipping dx_stream"),
    ("all-exclude-rt",       ["--all", "--exclude-rt",     *_SAFE],  "Skipping dx_rt"),
    ("target-dx_rt-stream",  ["--target=dx_rt,dx_stream",  *_SAFE],              None),
]


@pytest.mark.parametrize(
    "case_id,args,skip_pattern",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_runtime_install_option(case_id, args, skip_pattern):
    """Run dx-runtime/install.sh with the given option and expect success."""
    result = subprocess.run(
        ["./install.sh", *args],
        cwd=str(RUNTIME_DIR),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"install.sh {' '.join(args)} failed (exit {result.returncode})\n{output}"
    )
    if skip_pattern:
        assert skip_pattern in output, (
            f"Expected '{skip_pattern}' in output but not found.\n{output}"
        )
