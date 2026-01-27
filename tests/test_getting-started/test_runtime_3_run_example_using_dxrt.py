import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_command, GETTING_STARTED_DIR, DEFAULT_TIMEOUT

pytestmark = [pytest.mark.getting_started, pytest.mark.getting_started_skip_install, pytest.mark.runtime]

def test_runtime_3_run_example_using_dxrt():
    result = run_command(["bash", str(GETTING_STARTED_DIR / "runtime-3_run_example_using_dxrt.sh")], banner_msg="Running script: runtime-3_run_example_using_dxrt.sh", timeout=DEFAULT_TIMEOUT, cwd=GETTING_STARTED_DIR)
    if result.returncode != 0:
        pytest.fail(result.stdout or "Script failed: runtime-3_run_example_using_dxrt.sh")
