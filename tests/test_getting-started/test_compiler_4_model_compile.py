import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_command, GETTING_STARTED_DIR, DEFAULT_TIMEOUT

pytestmark = [pytest.mark.getting_started, pytest.mark.getting_started_skip_install, pytest.mark.compiler]

def test_compiler_4_model_compile():
    result = run_command(["bash", str(GETTING_STARTED_DIR / "compiler-4_model_compile.sh")], banner_msg="Running script: compiler-4_model_compile.sh", timeout=DEFAULT_TIMEOUT, cwd=GETTING_STARTED_DIR)
    if result.returncode != 0:
        pytest.fail(result.stdout or "Script failed: compiler-4_model_compile.sh")
