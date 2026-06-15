"""
dx-runtime install.sh option coverage test suite (kcov).

Goal: exercise as many install.sh option branches as possible on a single OS
(Ubuntu 26.04) inside a container, measuring bash line coverage with kcov.

Because the script runs inside docker (no physical NPU access), every real combo
ALWAYS appends --exclude-fw --exclude-driver so firmware/driver are never touched.

Coverage output is written under the mounted workspace at
tests/_coverage/runtime/ so it is collectable on the host, then merged.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import (  # noqa: E402
    build_local_install_image,
    start_local_install_container,
    remove_container,
    is_container_running,
    run_in_container,
    kcov_run_cmd,
    kcov_merge_cmd,
)

pytestmark = [pytest.mark.install_option, pytest.mark.runtime]

OS_TYPE = "ubuntu"
VERSION = "26.04"
COMPONENT = "optcov-runtime"

WS = "/deepx/workspace"
INCLUDE_PATH = f"{WS}/dx-runtime"
COV_ROOT = f"{WS}/tests/_coverage/runtime"
MERGED_DIR = f"{COV_ROOT}/merged"

INSTALL_TIMEOUT = 10800

# Mandatory flags for every real combo (docker has no NPU hardware).
EXCLUDE = "--exclude-fw --exclude-driver"

_APT_PREP = (
    "sudo apt-get update && "
    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y kcov"
)

# combo_id, install.sh args (EXCLUDE auto-appended unless light), expect_success, heavy
COMBOS = [
    ("help", "--help", True, False),
    ("error-unknown", "--unknown-option-xyz", False, False),
    ("all", f"--all {EXCLUDE} --sanity-check=n", True, True),
    ("target-dx_rt", f"--target=dx_rt {EXCLUDE} --sanity-check=n", True, True),
    ("target-dx_app", f"--target=dx_app {EXCLUDE}", True, True),
    ("target-dx_stream", f"--target=dx_stream {EXCLUDE}", True, True),
    ("use-ort-n", f"--all {EXCLUDE} --use-ort=n --sanity-check=n", True, True),
    ("use-ort-y", f"--all {EXCLUDE} --use-ort=y --sanity-check=n", True, True),
    ("skip-uninstall-reuse", f"--target=dx_rt {EXCLUDE} --skip-uninstall --venv-reuse --sanity-check=n", True, True),
    ("skip-uninstall-force", f"--target=dx_rt {EXCLUDE} --skip-uninstall --venv-force-remove --sanity-check=n", True, True),
    ("venv-path", f"--target=dx_rt {EXCLUDE} --skip-uninstall --venv_path={WS}/dx-runtime/venv-alt --sanity-check=n", True, True),
    ("driver-source-build", f"--all {EXCLUDE} --driver-source-build --sanity-check=n", True, True),
    ("verbose", f"--all {EXCLUDE} --verbose --sanity-check=n", True, True),
]


@pytest.fixture(scope="module")
def runtime_cov_container():
    """Build image + start container, prepare kcov, and merge coverage on teardown."""
    build_local_install_image(COMPONENT, OS_TYPE, VERSION)
    name = start_local_install_container(COMPONENT, OS_TYPE, VERSION)
    if not is_container_running(name):
        remove_container(name)
        pytest.fail(f"Container {name} failed to start")

    prep = run_in_container(
        name,
        f"set -e; cd {WS}; rm -rf {COV_ROOT}; mkdir -p {COV_ROOT}; {_APT_PREP}",
        banner_msg="Preparing kcov + apt (dx-runtime)",
        timeout=1800,
    )
    if prep.returncode != 0:
        remove_container(name)
        pytest.fail(f"kcov/apt preparation failed in {name}\n{prep.stdout}")

    yield name

    run_in_container(
        name,
        kcov_merge_cmd(MERGED_DIR, f"{COV_ROOT}/run-*"),
        banner_msg="Merging dx-runtime coverage",
        timeout=600,
    )
    remove_container(name)


@pytest.mark.parametrize(
    "combo_id,args,expect_success,heavy",
    COMBOS,
    ids=[c[0] for c in COMBOS],
)
def test_runtime_install_option_coverage(
    runtime_cov_container, combo_id, args, expect_success, heavy, capsys
):
    """Run dx-runtime/install.sh under kcov for one option combo (always exclude fw/driver)."""
    if heavy and os.getenv("DX_INSTALL_OPTION_HEAVY", "1") == "0":
        pytest.skip("heavy install combos disabled (DX_INSTALL_OPTION_HEAVY=0)")

    name = runtime_cov_container
    out_dir = f"{COV_ROOT}/run-{combo_id}"
    script = f"./dx-runtime/install.sh {args}".strip()
    cmd = f"cd {WS} && " + kcov_run_cmd(out_dir, INCLUDE_PATH, script)

    result = run_in_container(
        name,
        cmd,
        banner_msg=f"kcov dx-runtime install.sh [{combo_id}]",
        timeout=INSTALL_TIMEOUT,
        capsys=capsys,
    )

    if expect_success:
        assert result.returncode == 0, (
            f"[{combo_id}] expected success but exit={result.returncode}\n{result.stdout}"
        )
    else:
        assert result.returncode != 0, (
            f"[{combo_id}] expected failure but succeeded\n{result.stdout}"
        )
