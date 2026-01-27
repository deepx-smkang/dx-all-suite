"""
Local Install Test Suite for dx-all-suite

This test suite validates local installation for:
- dx-compiler (Ubuntu 24.04, 22.04, 20.04)
- dx-modelzoo (Ubuntu 24.04, 22.04, 20.04, Debian 12, 13)
- dx-runtime (Ubuntu 24.04, 22.04, 20.04, Debian 12, 13)

Test workflow:
1. Build docker image (session fixture)
2. Start container (session fixture)
3. Install component in container
4. (Optional) Install driver/runtime on host
"""

import os
import pytest
import subprocess
import sys
from pathlib import Path

pytestmark = pytest.mark.local_install

# Get project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Import from conftest
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import (
    run_in_container,
    ensure_repo_in_container,
    check_docker_image_exists,
    container_name,
    is_container_running,
)

# Test configuration
INSTALL_TIMEOUT = 7200  # 2 hours for installs


# ============================================================================
# Helper Functions
# ============================================================================

def _run_host_install(cmd, label, timeout=1800):
    """Run installation command on host with live output."""
    banner = (
        f"\n{'=' * 80}\n"
        f"🚀 {label}\n"
        f"{'=' * 80}\n"
    )
    print(banner, file=sys.stdout, flush=True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=PROJECT_ROOT,
    )

    output_lines = []
    for line in process.stdout:
        print(line, end="", file=sys.stdout, flush=True)
        output_lines.append(line.rstrip())

    process.wait(timeout=timeout)

    summary = f"\n{'=' * 80}\n"
    if process.returncode == 0:
        summary += f"✅ {label} succeeded\n"
    else:
        summary += f"❌ {label} failed (exit code: {process.returncode})\n"
    summary += f"{'=' * 80}\n"
    print(summary, file=sys.stdout, flush=True)

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=process.returncode,
        stdout="\n".join(output_lines),
        stderr=None,
    )


# ============================================================================
# Test Configuration Data
# ============================================================================

# Component configurations
COMPONENT_CONFIGS = {
    "dx-compiler": {
        "os_versions": [
            ("ubuntu", "24.04"),
            ("ubuntu", "22.04"),
            ("ubuntu", "20.04"),
        ],
    },
    "dx-modelzoo": {
        "os_versions": [
            ("ubuntu", "24.04"),
            ("ubuntu", "22.04"),
            ("ubuntu", "20.04"),
            ("debian", "12"),
            ("debian", "13"),
        ],
    },
    "dx-runtime": {
        "os_versions": [
            ("ubuntu", "24.04"),
            ("ubuntu", "22.04"),
            ("ubuntu", "20.04"),
            ("debian", "12"),
            ("debian", "13"),
        ],
    },
}

# Generate all test parameters
def generate_test_params():
    """Generate (component, os_type, version) tuples for all configurations."""
    params = []
    for component, config in COMPONENT_CONFIGS.items():
        for os_type, version in config["os_versions"]:
            params.append((component, os_type, version))
    return params


# ============================================================================
# Sanity Tests
# ============================================================================

class TestLocalInstallSanity:
    """Sanity checks before running actual installations"""

    @pytest.mark.sanity
    def test_docker_command_available(self):
        """Verify docker command is available"""
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "docker command not found"
    
    @pytest.mark.sanity
    def test_docker_compose_command_available(self):
        """Verify docker compose command is available"""
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "docker compose command not found"
    
    @pytest.mark.sanity
    def test_project_structure(self):
        """Verify essential project directories exist"""
        essential_dirs = [
            PROJECT_ROOT / "dx-compiler",
            PROJECT_ROOT / "dx-runtime",
            PROJECT_ROOT / "dx-modelzoo",
            PROJECT_ROOT / "docker",
        ]
        
        for dir_path in essential_dirs:
            assert dir_path.exists(), f"Essential directory not found: {dir_path}"


# ============================================================================
# Docker Image Build Tests
# ============================================================================

class TestLocalInstallDockerBuild:
    """Test docker image builds for local install"""

    @pytest.mark.parametrize(
        "ensure_local_install_image",
        [
            ("dx-compiler", "ubuntu", "24.04"),
            ("dx-compiler", "ubuntu", "22.04"),
            ("dx-compiler", "ubuntu", "20.04"),
            ("dx-modelzoo", "ubuntu", "24.04"),
            ("dx-modelzoo", "ubuntu", "22.04"),
            ("dx-modelzoo", "ubuntu", "20.04"),
            ("dx-modelzoo", "debian", "12"),
            ("dx-modelzoo", "debian", "13"),
            ("dx-runtime", "ubuntu", "24.04"),
            ("dx-runtime", "ubuntu", "22.04"),
            ("dx-runtime", "ubuntu", "20.04"),
            ("dx-runtime", "debian", "12"),
            ("dx-runtime", "debian", "13"),
        ],
        indirect=["ensure_local_install_image"],
        ids=lambda p: f"{p[0]}-{p[1]}-{p[2]}",
    )
    def test_docker_build(self, ensure_local_install_image):
        """
        Test Docker image build for local install.
        
        The fixture builds the image if it doesn't exist. This test just verifies.
        """
        component, os_type, version = ensure_local_install_image
        assert check_docker_image_exists(component, os_type, version), \
            f"Docker image not found for {component} on {os_type}:{version}"


# ============================================================================
# Docker Container Run Tests
# ============================================================================

class TestLocalInstallDockerRun:
    """Test docker container startup for local install"""

    @pytest.mark.parametrize(
        "ensure_local_install_container",
        [
            ("dx-compiler", "ubuntu", "24.04"),
            ("dx-compiler", "ubuntu", "22.04"),
            ("dx-compiler", "ubuntu", "20.04"),
            ("dx-modelzoo", "ubuntu", "24.04"),
            ("dx-modelzoo", "ubuntu", "22.04"),
            ("dx-modelzoo", "ubuntu", "20.04"),
            ("dx-modelzoo", "debian", "12"),
            ("dx-modelzoo", "debian", "13"),
            ("dx-runtime", "ubuntu", "24.04"),
            ("dx-runtime", "ubuntu", "22.04"),
            ("dx-runtime", "ubuntu", "20.04"),
            ("dx-runtime", "debian", "12"),
            ("dx-runtime", "debian", "13"),
        ],
        indirect=["ensure_local_install_container"],
        ids=lambda p: f"{p[0]}-{p[1]}-{p[2]}",
    )
    def test_docker_run(self, ensure_local_install_container):
        """
        Test Docker container is running.
        
        The fixture starts the container if it's not running. This test just verifies.
        """
        component, os_type, version = ensure_local_install_container
        container_name_str = container_name(component, version)
        assert is_container_running(container_name_str), \
            f"Container {container_name_str} is not running"


# ============================================================================
# Component Installation Tests
# ============================================================================

class TestLocalInstallComponents:
    """Test component installations in container"""

    @pytest.mark.parametrize(
        "ensure_local_install_container",
        [
            (comp, os_ver[0], os_ver[1]) 
            for comp, config in COMPONENT_CONFIGS.items()
            for os_ver in config["os_versions"]
        ],
        indirect=["ensure_local_install_container"],
        ids=lambda p: f"{p[0]}-{p[1]}-{p[2]}",
    )
    def test_install_component(self, ensure_local_install_container, capsys):
        """
        Test component installation in container.
        
        Args:
            ensure_local_install_container: Fixture that ensures container is running
        """
        component, os_type, version = ensure_local_install_container
        container_name_str = container_name(component, version)
        
        # Ensure repository is mounted
        try:
            ensure_repo_in_container(container_name_str, component)
        except Exception as exc:
            pytest.fail(str(exc))

        # Build install command based on component
        if component == "dx-runtime":
            # dx-runtime has special --exclude-fw flag support
            exclude_fw_flag = ""
            if os.getenv("DX_EXCLUDE_FW", "0") == "1":
                exclude_fw_flag = " --exclude-fw"
            
            install_cmd = (
                "set -e; "
                "if [ -f /deepx/workspace/dx-runtime/install.sh ]; then "
                "cd /deepx/workspace; "
                "elif [ -f /deepx/workspace/dx-all-suite/dx-runtime/install.sh ]; then "
                "cd /deepx/workspace/dx-all-suite; "
                "elif [ -f /deepx/dx-runtime/install.sh ]; then "
                "cd /deepx; "
                "else echo 'dx-runtime install.sh not found in container'; exit 2; fi; "
                f"./dx-runtime/install.sh --all --exclude-driver{exclude_fw_flag}"
            )
        else:
            # dx-compiler and dx-modelzoo use standard install
            install_cmd = (
                "set -e; "
                f"if [ -f /deepx/workspace/{component}/install.sh ]; then "
                "cd /deepx/workspace; "
                f"elif [ -f /deepx/workspace/dx-all-suite/{component}/install.sh ]; then "
                "cd /deepx/workspace/dx-all-suite; "
                f"elif [ -f /deepx/{component}/install.sh ]; then "
                "cd /deepx; "
                f"else echo '{component} install.sh not found in container'; exit 2; fi; "
                f"./{component}/install.sh"
            )

        # Run installation
        result = run_in_container(
            container_name_str,
            install_cmd,
            f"Installing {component}",
            timeout=INSTALL_TIMEOUT,
            capsys=capsys,
        )

        # Check result
        if result.returncode != 0:
            error_msg = [
                "",
                "=" * 80,
                f"{component.upper()} INSTALL FAILED",
                "=" * 80,
                f"Exit Code: {result.returncode}",
                f"Container: {container_name_str}",
                "",
                "STDOUT:",
                "-" * 80,
                result.stdout or "(no stdout)",
                "-" * 80,
                "",
                "STDERR:",
                "-" * 80,
                result.stderr or "(no stderr)",
                "-" * 80,
                "",
            ]
            pytest.fail("\n".join(error_msg))


# ============================================================================
# Host Installation Tests (dx-runtime only)
# ============================================================================

class TestLocalInstallHostUpdates:
    """Install dx-runtime driver/runtime on host after build"""

    def test_install_dx_rt_npu_linux_driver(self):
        """Install NPU Linux driver on host"""
        cmd = ["./dx-runtime/install.sh", "--target=dx_rt_npu_linux_driver"]
        result = _run_host_install(cmd, "Installing dx_rt_npu_linux_driver")
        
        if result.returncode != 0:
            pytest.fail(
                "\n".join([
                    "",
                    "=" * 80,
                    "DX-RT DRIVER INSTALL FAILED",
                    "=" * 80,
                    f"Exit Code: {result.returncode}",
                    f"Command: {' '.join(cmd)}",
                    "",
                    "STDOUT:",
                    "-" * 80,
                    result.stdout or "(no stdout)",
                    "-" * 80,
                    "",
                ])
            )

    def test_install_dx_rt(self):
        """Install dx-runtime on host"""
        cmd = ["./dx-runtime/install.sh", "--target=dx_rt"]
        result = _run_host_install(cmd, "Installing dx_rt")
        
        if result.returncode != 0:
            pytest.fail(
                "\n".join([
                    "",
                    "=" * 80,
                    "DX-RT INSTALL FAILED",
                    "=" * 80,
                    f"Exit Code: {result.returncode}",
                    f"Command: {' '.join(cmd)}",
                    "",
                    "STDOUT:",
                    "-" * 80,
                    result.stdout or "(no stdout)",
                    "-" * 80,
                    "",
                ])
            )
