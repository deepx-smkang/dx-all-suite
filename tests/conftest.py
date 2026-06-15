"""
Shared utilities and configuration for all test suites.
"""

import os
import re
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT  # Alias for compatibility
GETTING_STARTED_DIR = REPO_ROOT / "getting-started"
DEFAULT_TIMEOUT = int(os.getenv("DX_TEST_GETTING_STARTED_TIMEOUT", "3600"))

# kcov coverage output (written from inside the container onto the bind-mounted
# host workspace) and the directory where ./test.sh writes HTML/JSON reports.
COVERAGE_DIR = REPO_ROOT / "tests" / "_coverage"
REPORTS_DIR = REPO_ROOT / "tests" / "reports"

# install_option components whose install.sh coverage is surfaced in the report.
KCOV_COMPONENTS = (
    ("compiler", "dx-compiler install.sh"),
    ("runtime", "dx-runtime install.sh"),
)

# Expected NPU stack version files (authoritative source of truth).
DRIVER_RELEASE_VER = REPO_ROOT / "dx-runtime" / "dx_rt_npu_linux_driver" / "release.ver"
FW_RELEASE_VER = REPO_ROOT / "dx-runtime" / "dx_fw" / "release.ver"

# Host-level locks. Shared across xdist workers AND separate test sessions so that
# NPU driver install / firmware flash never run concurrently (see plan sections 4-1, 4-2, 5-1).
HOST_NPU_LOCK = os.getenv("DX_HOST_NPU_LOCK", "/tmp/dx-host-npu.lock")
HOST_EXCLUSIVE_LOCK = os.getenv("DX_HOST_EXCLUSIVE_LOCK", "/tmp/dx-host-exclusive.lock")
ARCHIVE_LOCK = os.getenv("DX_ARCHIVE_LOCK", "/tmp/dx-archive.lock")
ARCHIVE_DONE_FLAG = os.getenv("DX_ARCHIVE_DONE_FLAG", "/tmp/dx-archive.done")


def is_verbose() -> bool:
    """Check if verbose/debug mode is enabled."""
    return os.getenv("DX_TEST_VERBOSE", "0").lower() in {"1", "true", "yes", "y"}

def container_name(os_type: str, version: str, component: str = "") -> str:
    """Generate container name from component, os_type and version string."""
    if component:
        return f"dx-local-install-test-{component}-{os_type}-{version.replace('.', '-')}"
    return f"dx-local-install-test-{os_type}-{version.replace('.', '-')}"


def is_container_running(container_name_str: str) -> bool:
    """Check if a docker container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name_str],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def path_exists_in_container(container_name_str: str, path: str) -> bool:
    """Check if a file or directory exists inside a container."""
    result = subprocess.run(
        ["docker", "exec", "-i", container_name_str, "bash", "-lc", f"test -f {path}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

def get_base_image(os_type: str, version: str) -> str:
    """
    Get the base docker image for a given OS type and version.

    Maps os_type/version to the correct registry image path.
    - rhel 9 → redhat/ubi9:latest
    - rhel 10 → redhat/ubi10:latest
    - centos stream9 → quay.io/centos/centos:stream9
    - centos stream10 → quay.io/centos/centos:stream10
    - others → {os_type}:{version}
    """
    if os_type == "rhel":
        return f"redhat/ubi{version}:latest"
    elif os_type == "centos":
        # version is "stream9" or "stream10"
        return f"quay.io/centos/centos:{version}"
    else:
        return f"{os_type}:{version}"

def check_docker_image_exists(os_type: str, version: str) -> bool:
    """
    Check if a local install docker image exists.

    Args:
        os_type: OS type (ubuntu or debian)
        version: OS version (24.04, 22.04, etc.)

    Returns:
        True if image exists, False otherwise
    """
    image_name = f"dx-local-install-test-{os_type}:{version}"
    result = subprocess.run(
        ["docker", "images", "-q", image_name],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())

def run_in_container(
    container_name: str,
    cmd: str,
    banner_msg: str = "",
    timeout: int = 7200,
    capsys=None,
) -> subprocess.CompletedProcess:
    """
    Execute a command inside a container with optional live output streaming.

    When DX_TEST_VERBOSE=1 (set by ./test.sh --debug), this function will stream
    output in real-time, making it easy to debug container commands.

    Args:
        container_name: Name of the container
        cmd: Command to execute
        banner_msg: Optional message to display in banner (e.g., "Installing dx-runtime")
        timeout: Timeout in seconds (default: 7200 = 2 hours)
        capsys: pytest capsys fixture for output control

    Returns:
        CompletedProcess object with the result
    """
    # Use banner_msg if provided, otherwise don't show banner
    if is_verbose():
        if capsys is not None:
            capsys.disabled()

        if banner_msg:
            banner = (
                f"\n{'=' * 80}\n"
                f"🚀 {banner_msg} in container: {container_name}\n"
                f"{'=' * 80}\n"
            )
            print(banner, file=sys.stdout, flush=True)
            print(banner, file=sys.stderr, flush=True)

    # Wrap docker exec -it with script -qec to allocate PTY
    docker_cmd = ["docker", "exec", "-it", container_name, "bash", "-lc", cmd]
    wrapped_cmd = ["script", "-qec", " ".join(shlex.quote(arg) for arg in docker_cmd), "/dev/null"]

    if is_verbose():
        # Live output mode - stream output in real-time
        process = subprocess.Popen(
            wrapped_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT,
        )

        output_lines = []
        for line in process.stdout:
            if capsys is not None:
                with capsys.disabled():
                    print(line, end="", file=sys.stdout, flush=True)
            else:
                print(line, end="", file=sys.stdout, flush=True)
            output_lines.append(line.rstrip())

        process.wait(timeout=timeout)

        # Show summary if banner_msg was provided
        if banner_msg:
            summary = f"\n{'=' * 80}\n"
            if process.returncode == 0:
                summary += f"✅ {banner_msg} succeeded in {container_name}\n"
            else:
                summary += f"❌ {banner_msg} failed in {container_name} (exit code: {process.returncode})\n"
            summary += f"{'=' * 80}\n"
            print(summary, file=sys.stdout, flush=True)

        return subprocess.CompletedProcess(
            args=docker_cmd,
            returncode=process.returncode,
            stdout="\n".join(output_lines),
            stderr=None,
        )
    else:
        # Quiet mode - capture output and return
        return subprocess.run(
            wrapped_cmd,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=timeout,
        )

def run_command(
    cmd: list[str],
    banner_msg: str = "",
    timeout: int = 1800,
    cwd: str | Path | None = None,
    capsys=None,
) -> subprocess.CompletedProcess:
    """
    Execute a command with optional live output streaming.

    When DX_TEST_VERBOSE=1 (set by ./test.sh --debug), this function will stream
    output in real-time. Otherwise, it runs in quiet mode and only shows output on failure.

    Args:
        cmd: Command list to execute
        banner_msg: Optional message to display in banner (e.g., "Building dx-runtime")
        timeout: Timeout in seconds (default: 1800 = 30 minutes)
        cwd: Working directory for command execution (default: PROJECT_ROOT)

    Returns:
        CompletedProcess object with the result
    """
    use_cwd = str(cwd) if cwd is not None else str(PROJECT_ROOT)

    # Prepare environment with DX_USERNAME and DX_PASSWORD
    env = os.environ.copy()
    if os.getenv("DX_USERNAME"):
        env["DX_USERNAME"] = os.getenv("DX_USERNAME")
    if os.getenv("DX_PASSWORD"):
        env["DX_PASSWORD"] = os.getenv("DX_PASSWORD")

    # Show banner when in verbose mode and banner_msg is provided
    if is_verbose() and banner_msg:
        banner = (
            f"\n{'=' * 80}\n"
            f"🚀 {banner_msg}\n"
            f"{'=' * 80}\n"
        )
        print(banner, file=sys.stdout, flush=True)

    # Wrap command with script -qec to allocate PTY
    script_cmd = ["script", "-qec", " ".join(shlex.quote(arg) for arg in cmd), "/dev/null"]

    if is_verbose():
        # Live output mode - stream output in real-time
        process = subprocess.Popen(
            script_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=use_cwd,
            env=env,
        )

        output_lines = []
        for line in process.stdout:
            if capsys is not None:
                with capsys.disabled():
                    print(line, end="", file=sys.stdout, flush=True)
            else:
                print(line, end="", file=sys.stdout, flush=True)
            output_lines.append(line.rstrip())

        process.wait(timeout=timeout)

        # Show summary if banner_msg was provided
        if banner_msg:
            summary = f"\n{'=' * 80}\n"
            if process.returncode == 0:
                summary += f"✅ {banner_msg} succeeded\n"
            else:
                summary += f"❌ {banner_msg} failed (exit code: {process.returncode})\n"
            summary += f"{'=' * 80}\n"
            print(summary, file=sys.stdout, flush=True)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout="\n".join(output_lines),
            stderr=None,
        )
    else:
        # Quiet mode - capture both stdout and stderr separately
        result = subprocess.run(
            script_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=use_cwd,
            timeout=timeout,
            env=env,
        )

        # Combine stdout and stderr for complete output
        combined_output = ""
        if result.stdout:
            combined_output += result.stdout
        if result.stderr:
            if combined_output:
                combined_output += "\n" + "=" * 80 + "\nSTDERR:\n" + "=" * 80 + "\n"
            combined_output += result.stderr

        # Return with combined output in stdout field for consistent access
        return subprocess.CompletedProcess(
            args=result.args,
            returncode=result.returncode,
            stdout=combined_output,
            stderr=result.stderr,
        )


# ============================================================================
# Version parsing helpers (NPU driver / firmware / runtime)
# ============================================================================

def read_first_line(path) -> str | None:
    """Read and return the first non-empty line of a file, or None if missing."""
    try:
        with open(path, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    return stripped
    except (FileNotFoundError, OSError):
        return None
    return None


def normalize_version(value: str | None) -> str | None:
    """Normalize a version string to a canonical 'vX.Y.Z' form for exact comparison."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value if value.startswith("v") else f"v{value}"


def parse_dxrt_cli_versions(output: str) -> dict:
    """
    Parse `dxrt-cli -s` output into a dict of normalized versions.

    Returns keys when present: 'dx-rt', 'dx-fw', 'npu-driver'.
    Expected source lines look like:
        DXRT vX.Y.Z
        * FW version   : vX.Y.Z
        * RT Driver version : vX.Y.Z
    """
    versions: dict = {}
    for line in (output or "").splitlines():
        m = re.search(r"DXRT\s+v?([0-9][0-9.]*)", line)
        if m:
            versions["dx-rt"] = normalize_version(m.group(1))
        m = re.search(r"FW\s*version\s*:\s*v?([0-9][0-9.]*)", line, re.IGNORECASE)
        if m:
            versions["dx-fw"] = normalize_version(m.group(1))
        m = re.search(r"RT\s*Driver\s*version\s*:\s*v?([0-9][0-9.]*)", line, re.IGNORECASE)
        if m:
            versions["npu-driver"] = normalize_version(m.group(1))
    return versions


def get_installed_npu_versions() -> dict:
    """Query installed NPU stack versions via `dxrt-cli -s`. Empty dict if unavailable."""
    if shutil.which("dxrt-cli") is None:
        return {}
    try:
        result = subprocess.run(
            ["dxrt-cli", "-s"], capture_output=True, text=True, timeout=60
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if result.returncode != 0:
        return {}
    return parse_dxrt_cli_versions(result.stdout)


# ============================================================================
# Host NPU stack (driver / firmware) — version-gated, lock-serialized install
# ============================================================================

def _filelock():
    """Import filelock lazily so collection works even before deps are installed."""
    from filelock import FileLock
    return FileLock


def _run_host_install(target: str, banner: str, capsys=None):
    cmd = ["./dx-runtime/install.sh", f"--target={target}"]
    result = run_command(cmd, banner, cwd=PROJECT_ROOT, capsys=capsys)
    if result.returncode != 0:
        pytest.fail(
            f"Host install failed: {' '.join(cmd)}\n{result.stdout or ''}"
        )


def _ensure_host_npu_stack_impl(capsys=None) -> None:
    """
    Ensure the host NPU stack matches the expected release versions, exactly once,
    serialized across xdist workers / sessions via the shared host NPU lock.

    Version source of truth: dx-runtime/.../release.ver. Installed versions are read
    from `dxrt-cli -s` (which ships with dx_rt), so dx_rt is bootstrapped on the host
    first if `dxrt-cli` is missing. Firmware is flashed only when DX_EXCLUDE_FW != 1.
    """
    expected_driver = normalize_version(read_first_line(DRIVER_RELEASE_VER))
    if expected_driver is None:
        pytest.skip(f"driver release.ver not found: {DRIVER_RELEASE_VER}")
    expected_fw = normalize_version(read_first_line(FW_RELEASE_VER))
    flash_fw = os.getenv("DX_EXCLUDE_FW", "0") != "1"

    def _gates_satisfied() -> bool:
        if shutil.which("dxrt-cli") is None:
            return False
        versions = get_installed_npu_versions()
        if versions.get("npu-driver") != expected_driver:
            return False
        if flash_fw and versions.get("dx-fw") != expected_fw:
            return False
        return True

    # Fast path: everything already at the expected version, no lock contention.
    if _gates_satisfied():
        return

    FileLock = _filelock()
    with FileLock(HOST_NPU_LOCK):
        # Double-check inside the lock (another worker may have just finished).
        if _gates_satisfied():
            return

        # Bootstrap dxrt-cli (driver + dx_rt) so version gating is possible.
        if shutil.which("dxrt-cli") is None:
            _run_host_install("dx_rt_npu_linux_driver",
                              "Installing NPU driver (host bootstrap)", capsys)
            _run_host_install("dx_rt", "Installing dx_rt (host bootstrap)", capsys)

        # Driver version gate.
        if get_installed_npu_versions().get("npu-driver") != expected_driver:
            _run_host_install("dx_rt_npu_linux_driver",
                              "Updating NPU driver (host, once)", capsys)
            installed = get_installed_npu_versions().get("npu-driver")
            if installed != expected_driver:
                pytest.fail(
                    f"Host NPU driver version mismatch after install: "
                    f"expected {expected_driver}, got {installed}"
                )

        # Firmware version gate (irreversible flash; strictly serialized).
        if flash_fw and get_installed_npu_versions().get("dx-fw") != expected_fw:
            _run_host_install("dx_fw", "Flashing NPU firmware (host, once)", capsys)


@pytest.fixture(scope="session")
def install_host_npu_stack():
    """
    Session-scoped prerequisite: ensure host NPU driver/dx_rt (and firmware unless
    excluded) are present at the expected versions exactly once, serialized across
    workers.

    Returns a callable so tests can trigger it explicitly inside their own capsys scope.
    """
    def _install(capsys=None):
        _ensure_host_npu_stack_impl(capsys=capsys)

    return _install


# ============================================================================
# host_exclusive serialization (across xdist workers)
# ============================================================================

@pytest.fixture(autouse=True)
def _host_exclusive_serialize(request):
    """Serialize any test marked host_exclusive behind a shared filelock."""
    if request.node.get_closest_marker("host_exclusive") is None:
        yield
        return
    FileLock = _filelock()
    with FileLock(HOST_EXCLUSIVE_LOCK):
        yield


# ============================================================================
# kcov helpers (bash coverage of install.sh, run inside containers)
# ============================================================================

def kcov_run_cmd(out_dir: str, include_path: str, script_and_args: str) -> str:
    """
    Build a kcov command string that instruments a bash script invocation.

    Args:
        out_dir: kcov output directory (per-combo, under the mounted workspace)
        include_path: restrict coverage collection to this path (the target script dir)
        script_and_args: the bash command to run under kcov (e.g. './dx-compiler/install.sh --target=dx_com')
    """
    return (
        f"mkdir -p {shlex.quote(out_dir)} && "
        f"kcov --bash-method=DEBUG --include-path={shlex.quote(include_path)} "
        f"{shlex.quote(out_dir)} {script_and_args}"
    )


def kcov_merge_cmd(merged_dir: str, run_glob: str) -> str:
    """Build a kcov --merge command string combining per-combo run dirs."""
    return (
        f"mkdir -p {shlex.quote(merged_dir)} && "
        f"kcov --merge {shlex.quote(merged_dir)} {run_glob}"
    )


def _coverage_numbers(data: dict) -> tuple[float, int, int] | None:
    """Extract (percent, covered, total) from a kcov coverage.json payload."""
    def _to_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    if data.get("total_lines") not in (None, "", 0, "0"):
        total = int(_to_float(data.get("total_lines")))
        covered = int(_to_float(data.get("covered_lines")))
        percent = _to_float(data.get("percent_covered"))
        if total > 0:
            if not data.get("percent_covered"):
                percent = round(covered * 100.0 / total, 2)
            return percent, covered, total

    # Fall back to aggregating per-file entries.
    files = data.get("files") or []
    total = sum(int(_to_float(f.get("total_lines"))) for f in files)
    covered = sum(int(_to_float(f.get("covered_lines"))) for f in files)
    if total > 0:
        return round(covered * 100.0 / total, 2), covered, total
    return None


def summarize_kcov_coverage(component: str) -> dict | None:
    """
    Read the merged kcov coverage.json for a component off the host filesystem.

    Returns a dict with percent/covered/total/html, or None if no coverage was
    produced (e.g. install_option tests were not run).
    """
    merged = COVERAGE_DIR / component / "merged"
    if not merged.is_dir():
        return None

    candidates = sorted(
        merged.rglob("coverage.json"),
        key=lambda p: (0 if "kcov-merged" in p.parts else 1, len(p.parts)),
    )
    for cov_json in candidates:
        try:
            data = json.loads(cov_json.read_text())
        except (OSError, ValueError):
            continue
        numbers = _coverage_numbers(data)
        if numbers is None:
            continue
        percent, covered, total = numbers
        index_html = cov_json.parent / "index.html"
        if not index_html.exists():
            index_html = merged / "index.html"
        return {
            "component": component,
            "percent": percent,
            "covered": covered,
            "total": total,
            "html": index_html if index_html.exists() else None,
        }
    return None


def pytest_html_results_summary(prefix, summary, postfix):
    """Surface kcov install.sh coverage as a summary block in the HTML report."""
    rows = []
    for component, label in KCOV_COMPONENTS:
        info = summarize_kcov_coverage(component)
        if info is None:
            continue
        pct = f"{info['percent']:.2f}%"
        lines = f"{info['covered']}/{info['total']} lines"
        if info["html"] is not None:
            try:
                href = os.path.relpath(info["html"], start=str(REPORTS_DIR))
            except ValueError:
                href = str(info["html"])
            name = f'<a href="{href}">{label}</a>'
        else:
            name = label
        rows.append(
            f"<tr><td>{name}</td>"
            f'<td style="text-align:right">{pct}</td>'
            f'<td style="text-align:right">{lines}</td></tr>'
        )

    if not rows:
        return

    prefix.append(
        "<h3>install.sh Coverage (kcov)</h3>"
        '<table style="border-collapse:collapse">'
        '<thead><tr><th style="text-align:left">Target</th>'
        '<th>Coverage</th><th>Lines</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


@pytest.hookimpl(optionalhook=True)
def pytest_json_modifyreport(json_report):
    """Embed kcov install.sh coverage into the JSON report metadata."""
    coverage = {}
    for component, _label in KCOV_COMPONENTS:
        info = summarize_kcov_coverage(component)
        if info is None:
            continue
        coverage[component] = {
            "percent": info["percent"],
            "covered_lines": info["covered"],
            "total_lines": info["total"],
            "html": str(info["html"]) if info["html"] else None,
        }
    if coverage:
        json_report.setdefault("kcov_coverage", {}).update(coverage)


# ============================================================================
# Auto-assign xdist groups so parallel runs stay safe (see plan section 6)
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Assign xdist_group markers based on suite/parameters so that, under
    `-n <N> --dist loadgroup`, dependent/host-mutating tests stay on one worker.
    """
    for item in items:
        # local_install: pin each OS-version pipeline (build->run->install) to one worker.
        if item.get_closest_marker("local_install"):
            params = getattr(getattr(item, "callspec", None), "params", {}) or {}
            os_type = params.get("os_type")
            version = params.get("version")
            if os_type and version:
                item.add_marker(pytest.mark.xdist_group(f"{os_type}-{version}"))

        # getting-started: single group + host_exclusive (sequential workflow, host mutating).
        if item.get_closest_marker("getting_started"):
            item.add_marker(pytest.mark.xdist_group("getting_started"))
            item.add_marker(pytest.mark.host_exclusive)

        # install_option (kcov): single group, shared workspace -> serialize within suite.
        if item.get_closest_marker("install_option"):
            item.add_marker(pytest.mark.xdist_group("install_option"))


# ============================================================================
# Reusable local-install docker helpers (image build + container start)
# ============================================================================

def compose_env(component: str, os_type: str, version: str) -> dict:
    """Build the environment dict used by the local-install docker-compose file."""
    env = os.environ.copy()
    env["COMPOSE_BAKE"] = "true"
    env["HOST_UID"] = str(os.getuid())
    env["HOST_GID"] = str(os.getgid())
    env["TARGET_USER"] = "deepx"
    env["TARGET_HOME"] = "/deepx"
    env["OS_TYPE"] = os_type
    env["VERSION"] = version
    env["VERSION_DASH"] = version.replace(".", "-")
    env["COMPONENT"] = component
    env["BASE_IMAGE"] = get_base_image(os_type, version)
    env["LOCAL_VOLUME_PATH"] = os.getenv("LOCAL_VOLUME_PATH", str(PROJECT_ROOT))
    env["DOCKER_VOLUME_PATH"] = os.getenv("DOCKER_VOLUME_PATH", "/deepx/workspace")

    if not env.get("XAUTHORITY"):
        dummy_xauth = "/tmp/dummy"
        Path(dummy_xauth).touch(exist_ok=True)
        env["XAUTHORITY"] = dummy_xauth
        env["XAUTHORITY_TARGET"] = dummy_xauth
    else:
        env["XAUTHORITY_TARGET"] = "/tmp/.docker.xauth"

    for key in ("USE_INTRANET", "CA_FILE_NAME", "DISPLAY"):
        if not env.get(key):
            env[key] = ""
    return env


def compose_config_args(env: dict) -> list[str]:
    """Compose -f config file args, honoring optional GPU/internal overlays."""
    args = ["-f", "tests/docker/docker-compose.local.install.test.yml"]
    if env.get("DX_TEST_NVIDIA_GPU", "0").lower() in {"1", "true", "yes", "y"}:
        args.extend(["-f", "docker/docker-compose.nvidia_gpu.yml"])
    if env.get("DX_TEST_INTERNAL", "0").lower() in {"1", "true", "yes", "y"}:
        args.extend(["-f", "docker/docker-compose.internal.yml"])
    return args


def build_local_install_image(component: str, os_type: str, version: str) -> None:
    """Build the local-install docker image if it does not already exist."""
    if check_docker_image_exists(os_type, version):
        return
    env = compose_env(component, os_type, version)
    no_cache = []
    if env.get("DX_TEST_NO_CACHE", "0").lower() in {"1", "true", "yes", "y"}:
        no_cache = ["--no-cache"]
    cmd = ["docker", "compose", *compose_config_args(env), "build", *no_cache,
           "dx-local-install-test"]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            cwd=str(PROJECT_ROOT), env=env, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to build image for {os_type}:{version}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def start_local_install_container(component: str, os_type: str, version: str) -> str:
    """(Re)create and start a local-install container, returning its name."""
    name = container_name(os_type, version, component)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
    env = compose_env(component, os_type, version)
    cmd = ["docker", "compose", *compose_config_args(env), "up", "-d",
           "dx-local-install-test"]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            cwd=str(PROJECT_ROOT), env=env, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to start container {name}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return name


def remove_container(name: str) -> None:
    """Force-remove a container, ignoring errors."""
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)


# ============================================================================
# Archive-once prerequisite for parallel docker_install (see plan section 7, Phase 0)
# ============================================================================

@pytest.fixture(scope="session")
def archive_once():
    """
    Produce the shared archives/*.tar.gz exactly once, serialized across workers.

    docker_build.sh writes OS-independent archives to the repo-shared archives/ dir;
    running it per-build in parallel races on those files. This fixture builds them
    once up front so every parallel docker build can safely pass --skip-archive.
    """
    FileLock = _filelock()
    with FileLock(ARCHIVE_LOCK):
        if os.path.exists(ARCHIVE_DONE_FLAG):
            return
        archive_cmds = [
            ["./scripts/archive_dx-compiler.sh"],
            ["./scripts/archive_git_repos.sh", "--target=dx-runtime"],
            ["./scripts/archive_git_repos.sh", "--target=dx-modelzoo"],
        ]
        for cmd in archive_cmds:
            result = run_command(cmd, f"Archiving (once): {' '.join(cmd)}",
                                 cwd=PROJECT_ROOT, timeout=7200)
            if result.returncode != 0:
                pytest.fail(
                    f"archive_once failed: {' '.join(cmd)}\n{result.stdout or ''}"
                )
        Path(ARCHIVE_DONE_FLAG).touch()
