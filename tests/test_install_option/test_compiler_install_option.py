"""
dx-compiler install.sh option coverage test suite (kcov).

Goal: exercise as many install.sh option branches as possible on a single OS
(Ubuntu 24.04) inside a container, measuring bash line coverage with kcov.

Excluded options (being removed): --venv_symlink_target_path, --docker_volume_path.

Coverage output is written under the mounted workspace at
tests/_coverage/compiler/ so it is collectable on the host, then merged.
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

pytestmark = [pytest.mark.install_option, pytest.mark.compiler]

OS_TYPE = "ubuntu"
VERSION = "24.04"
COMPONENT = "optcov-compiler"

# Paths inside the container (workspace mounted at /deepx/workspace).
WS = "/deepx/workspace"
INCLUDE_PATH = f"{WS}/dx-compiler"
COV_ROOT = f"{WS}/tests/_coverage/compiler"
MERGED_DIR = f"{COV_ROOT}/merged"

INSTALL_TIMEOUT = 10800

# Make sure apt keyboard-configuration is present so install.sh never prompts.
_APT_PREP = (
    "sudo apt-get update && "
    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y keyboard-configuration kcov"
)

# combo_id, install.sh args, expect_success, heavy(performs real download/install)
COMBOS = [
    ("help", "--help", True, False),
    ("error-unknown", "--unknown-option-xyz", False, False),
    ("default-all", "", True, True),
    ("target-dx_com", "--target=dx_com", True, True),
    ("target-dx_tron", "--target=dx_tron", True, True),
    ("archive-mode", "--target=dx_com --archive_mode=y", True, True),
    ("python-version", "--target=dx_com --python_version=3.12", True, True),
    ("force-false", "--target=dx_com --force=false", True, True),
    ("verbose", "--target=dx_com --verbose", True, True),
    ("venv-path", "--target=dx_com --venv_path=./venv-dx-compiler-alt", True, True),
    ("venv-reuse", "--target=dx_com --venv_path=./venv-dx-compiler-alt --venv-reuse", True, True),
    ("venv-force-remove", "--target=dx_com --venv-force-remove", True, True),
    ("system-site-packages", "--target=dx_com --system-site-packages", True, True),
]


@pytest.fixture(scope="module")
def compiler_cov_container():
    """Build image + start container, prepare kcov, and merge coverage on teardown."""
    build_local_install_image(COMPONENT, OS_TYPE, VERSION)
    name = start_local_install_container(COMPONENT, OS_TYPE, VERSION)
    if not is_container_running(name):
        remove_container(name)
        pytest.fail(f"Container {name} failed to start")

    prep = run_in_container(
        name,
        f"set -e; cd {WS}; rm -rf {COV_ROOT}; mkdir -p {COV_ROOT}; {_APT_PREP}",
        banner_msg="Preparing kcov + apt (dx-compiler)",
        timeout=1800,
    )
    if prep.returncode != 0:
        remove_container(name)
        pytest.fail(f"kcov/apt preparation failed in {name}\n{prep.stdout}")

    yield name

    # Merge all per-combo coverage runs, then drop the container.
    run_in_container(
        name,
        kcov_merge_cmd(MERGED_DIR, f"{COV_ROOT}/run-*"),
        banner_msg="Merging dx-compiler coverage",
        timeout=600,
    )
    remove_container(name)


@pytest.mark.parametrize(
    "combo_id,args,expect_success,heavy",
    COMBOS,
    ids=[c[0] for c in COMBOS],
)
def test_compiler_install_option_coverage(
    compiler_cov_container, combo_id, args, expect_success, heavy, capsys
):
    """Run dx-compiler/install.sh under kcov for one option combo."""
    if heavy and os.getenv("DX_INSTALL_OPTION_HEAVY", "1") == "0":
        pytest.skip("heavy install combos disabled (DX_INSTALL_OPTION_HEAVY=0)")

    name = compiler_cov_container
    out_dir = f"{COV_ROOT}/run-{combo_id}"
    script = f"./dx-compiler/install.sh {args}".strip()
    cmd = f"cd {WS} && " + kcov_run_cmd(out_dir, INCLUDE_PATH, script)

    result = run_in_container(
        name,
        cmd,
        banner_msg=f"kcov dx-compiler install.sh [{combo_id}]",
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
