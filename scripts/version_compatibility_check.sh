#!/bin/bash
#
# Version Compatibility Check Script
#
# Verifies that installed component versions match the expected versions
# defined in docs/source/04_Version_Compatibility.md for the current release.
#
# Usage:
#   ./scripts/version_compatibility_check.sh [OPTIONS]
#
# Options:
#   --release-ver-only   Only check submodule release.ver files
#   --cli-check-only     Only check installed binary versions (dxcom, dxrt-cli)
#   --quiet              Show only PASS/FAIL summary
#   -h, --help           Show this help message
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#   2 - Dependency or configuration error
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPAT_MD="${PROJECT_ROOT}/docs/source/04_Version_Compatibility.md"

# Source color definitions
source "${SCRIPT_DIR}/color_env.sh"

# --- Options ---
RUN_RELEASE_VER=1
RUN_CLI_CHECK=1
QUIET_MODE=0

# --- Counters ---
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
SKIPPED_CHECKS=0

# --- Parsed expected versions (populated by parse_matrix) ---
EXPECTED_DX_COMPILER=""
EXPECTED_DX_RUNTIME=""
EXPECTED_DXCOM=""
EXPECTED_DXTRON=""
EXPECTED_DX_FW=""
EXPECTED_NPU_DRIVER=""
EXPECTED_DX_RT=""
EXPECTED_DX_STREAM=""
EXPECTED_DX_APP=""

# ============================================================================
# Helper Functions
# ============================================================================

show_help() {
    cat << 'EOF'
Usage: version_compatibility_check.sh [OPTIONS]

Verifies component versions against the DX-AllSuite compatibility matrix
defined in docs/source/04_Version_Compatibility.md.

OPTIONS:
  --release-ver-only   Only check submodule release.ver files (Phase 1)
  --cli-check-only     Only check installed binary versions (Phase 2)
  --quiet              Show only final PASS/FAIL result
  -h, --help           Show this help message

EXIT CODES:
  0  All checks passed
  1  One or more checks failed
  2  Dependency or configuration error

EXAMPLES:
  ./scripts/version_compatibility_check.sh
  ./scripts/version_compatibility_check.sh --release-ver-only
  ./scripts/version_compatibility_check.sh --cli-check-only
  ./scripts/version_compatibility_check.sh --quiet

EOF
}

print_pass() {
    local label="$1"
    local actual="$2"
    local expected="$3"
    if [[ $QUIET_MODE -eq 0 ]]; then
        printf "  ${COLOR_BRIGHT_GREEN}✅ %-20s${COLOR_RESET}: %s (expected: %s)\n" "$label" "$actual" "$expected"
    fi
    ((TOTAL_CHECKS++)) || true
    ((PASSED_CHECKS++)) || true
}

print_fail() {
    local label="$1"
    local actual="$2"
    local expected="$3"
    if [[ $QUIET_MODE -eq 0 ]]; then
        printf "  ${COLOR_BRIGHT_RED}❌ %-20s${COLOR_RESET}: %s (expected: %s)\n" "$label" "$actual" "$expected"
    fi
    ((TOTAL_CHECKS++)) || true
    ((FAILED_CHECKS++)) || true
}

print_skip() {
    local label="$1"
    local reason="$2"
    if [[ $QUIET_MODE -eq 0 ]]; then
        printf "  ${COLOR_BRIGHT_YELLOW}⚠️  %-20s${COLOR_RESET}: %s\n" "$label" "$reason"
    fi
    ((SKIPPED_CHECKS++)) || true
}

print_header() {
    if [[ $QUIET_MODE -eq 0 ]]; then
        echo ""
        echo -e "${COLOR_BOLD}$1${COLOR_RESET}"
    fi
}

# ============================================================================
# Matrix Parsing from 04_Version_Compatibility.md
# ============================================================================

parse_matrix() {
    local suite_ver="$1"

    if [[ ! -f "${COMPAT_MD}" ]]; then
        echo -e "${TAG_ERROR} Compatibility matrix file not found: ${COMPAT_MD}"
        exit 2
    fi

    # The HTML table has a repeating 3-row pattern per version:
    #   Row 1: <td colspan="7">vX.X.X</td>           (dx-all-suite version)
    #   Row 2: <td colspan="2">vA</td> <td colspan="5">vB</td>  (dx-compiler, dx-runtime)
    #   Row 3: 7 individual <td> cells: dxcom, dxtron, dx-fw, npu-driver, dx-rt, dx-stream, dx-app

    local found=0
    local line_num=0
    local match_line=0

    while IFS= read -r line; do
        ((line_num++)) || true
        if echo "$line" | grep -qP "colspan=\"7\".*>${suite_ver}<"; then
            match_line=$line_num
            found=1
            break
        fi
    done < "${COMPAT_MD}"

    if [[ $found -eq 0 ]]; then
        echo -e "${TAG_ERROR} Version ${suite_ver} not found in ${COMPAT_MD}"
        exit 2
    fi

    # Get all remaining content after the match line
    local remaining
    remaining=$(tail -n +"$((match_line + 1))" "${COMPAT_MD}")

    # Extract all version strings (vX.X.X pattern) from remaining lines until next rowspan or end of block
    # Row 2 has colspan="2" (dx-compiler) and colspan="5" (dx-runtime)
    # Row 3 has 7 plain <td> cells with versions
    # We need the next ~12 lines to cover both rows

    local block
    block=$(echo "$remaining" | head -15)

    # dx-compiler: from colspan="2" cell
    EXPECTED_DX_COMPILER=$(echo "$block" | grep -oP 'colspan="2"[^>]*>(<b>)?v[0-9.]+' | grep -oP 'v[0-9.]+' | head -1)

    # dx-runtime: from colspan="5" cell
    EXPECTED_DX_RUNTIME=$(echo "$block" | grep -oP 'colspan="5"[^>]*>(<b>)?v[0-9.]+' | grep -oP 'v[0-9.]+' | head -1)

    # Row 3: individual <td> cells (no colspan, no rowspan)
    # Filter lines with plain <td> containing version strings
    local component_versions
    mapfile -t component_versions < <(echo "$block" | grep -P '^\s*<td>(<b>)?v[0-9.]+' | grep -oP 'v[0-9.]+')

    if [[ ${#component_versions[@]} -ge 7 ]]; then
        EXPECTED_DXCOM="${component_versions[0]}"
        EXPECTED_DXTRON="${component_versions[1]}"
        EXPECTED_DX_FW="${component_versions[2]}"
        EXPECTED_NPU_DRIVER="${component_versions[3]}"
        EXPECTED_DX_RT="${component_versions[4]}"
        EXPECTED_DX_STREAM="${component_versions[5]}"
        EXPECTED_DX_APP="${component_versions[6]}"
    else
        echo -e "${TAG_ERROR} Failed to parse component versions from matrix (found ${#component_versions[@]}/7)"
        echo -e "${TAG_HINT} Check format of ${COMPAT_MD} for version ${suite_ver}"
        exit 2
    fi
}

# ============================================================================
# Version Reading
# ============================================================================

read_suite_version() {
    local ver_file="${PROJECT_ROOT}/release.ver"
    if [[ ! -f "${ver_file}" ]]; then
        echo -e "${TAG_ERROR} release.ver not found at project root: ${ver_file}"
        exit 2
    fi
    head -n 1 "${ver_file}" | tr -d '\r\n '
}

read_file_version() {
    local file_path="$1"
    if [[ -f "${file_path}" ]]; then
        head -n 1 "${file_path}" | tr -d '\r\n '
    else
        echo ""
    fi
}

compare_version() {
    local label="$1"
    local actual="$2"
    local expected="$3"

    if [[ -z "$expected" ]]; then
        print_skip "$label" "not defined in matrix"
        return
    fi

    if [[ -z "$actual" ]]; then
        print_skip "$label" "release.ver not found"
        return
    fi

    if [[ "$actual" == "$expected" ]]; then
        print_pass "$label" "$actual" "$expected"
    else
        print_fail "$label" "$actual" "$expected"
    fi
}

# ============================================================================
# Phase 1: Submodule release.ver Check
# ============================================================================

check_release_ver() {
    print_header "[Phase 1] Submodule release.ver check"

    # dx-compiler
    local actual
    actual=$(read_file_version "${PROJECT_ROOT}/dx-compiler/release.ver")
    compare_version "dx-compiler" "$actual" "$EXPECTED_DX_COMPILER"

    # dx-runtime (top-level)
    actual=$(read_file_version "${PROJECT_ROOT}/dx-runtime/release.ver")
    compare_version "dx-runtime" "$actual" "$EXPECTED_DX_RUNTIME"

    # dx-runtime sub-components
    actual=$(read_file_version "${PROJECT_ROOT}/dx-runtime/dx_rt_npu_linux_driver/release.ver")
    compare_version "npu-driver" "$actual" "$EXPECTED_NPU_DRIVER"

    actual=$(read_file_version "${PROJECT_ROOT}/dx-runtime/dx_rt/release.ver")
    compare_version "dx-rt" "$actual" "$EXPECTED_DX_RT"

    actual=$(read_file_version "${PROJECT_ROOT}/dx-runtime/dx_fw/release.ver")
    compare_version "dx-fw" "$actual" "$EXPECTED_DX_FW"

    actual=$(read_file_version "${PROJECT_ROOT}/dx-runtime/dx_app/release.ver")
    compare_version "dx-app" "$actual" "$EXPECTED_DX_APP"

    actual=$(read_file_version "${PROJECT_ROOT}/dx-runtime/dx_stream/release.ver")
    compare_version "dx-stream" "$actual" "$EXPECTED_DX_STREAM"
}

# ============================================================================
# Phase 2: CLI Binary Version Check
# ============================================================================

check_cli_versions() {
    print_header "[Phase 2] Installed binary version check"

    # --- dxcom -v ---
    check_dxcom_version

    # --- dxrt-cli -s ---
    check_dxrt_cli_version
}

check_dxcom_version() {
    if [[ -z "$EXPECTED_DXCOM" ]]; then
        print_skip "dxcom" "not defined in matrix"
        return
    fi

    if ! command -v dxcom &>/dev/null; then
        print_skip "dxcom" "command not found (not installed or venv not activated)"
        return
    fi

    local output
    output=$(dxcom -v 2>&1) || true
    local actual
    actual=$(echo "$output" | grep -oP 'v?\d+\.\d+\.\d+' | head -1)

    # Normalize: ensure 'v' prefix
    if [[ -n "$actual" && "$actual" != v* ]]; then
        actual="v${actual}"
    fi

    if [[ -z "$actual" ]]; then
        print_fail "dxcom" "parse error (output: ${output:0:60})" "$EXPECTED_DXCOM"
        return
    fi

    compare_version "dxcom" "$actual" "$EXPECTED_DXCOM"
}

check_dxrt_cli_version() {
    if ! command -v dxrt-cli &>/dev/null; then
        print_skip "DXRT" "dxrt-cli command not found (not installed)"
        print_skip "FW" "dxrt-cli not available"
        print_skip "NPU Driver" "dxrt-cli not available"
        return
    fi

    local output
    output=$(dxrt-cli -s 2>&1) || true

    # --- DXRT version (first line: "DXRT vX.X.X") ---
    if [[ -n "$EXPECTED_DX_RT" ]]; then
        local actual_dxrt
        actual_dxrt=$(echo "$output" | grep -oP 'DXRT\s+v\K[\d.]+' | head -1)
        if [[ -n "$actual_dxrt" ]]; then
            compare_version "DXRT" "v${actual_dxrt}" "$EXPECTED_DX_RT"
        else
            print_fail "DXRT" "parse error" "$EXPECTED_DX_RT"
        fi
    fi

    # --- FW version ---
    if [[ -n "$EXPECTED_DX_FW" ]]; then
        local actual_fw
        actual_fw=$(echo "$output" | grep -oP 'FW version\s*:\s*v\K[\d.]+' | head -1)
        if [[ -n "$actual_fw" ]]; then
            compare_version "FW" "v${actual_fw}" "$EXPECTED_DX_FW"
        else
            print_fail "FW" "parse error" "$EXPECTED_DX_FW"
        fi
    fi

    # --- NPU Driver version (RT Driver version) ---
    if [[ -n "$EXPECTED_NPU_DRIVER" ]]; then
        local actual_drv
        actual_drv=$(echo "$output" | grep -oP 'RT Driver version\s*:\s*v\K[\d.]+' | head -1)
        if [[ -n "$actual_drv" ]]; then
            compare_version "NPU Driver" "v${actual_drv}" "$EXPECTED_NPU_DRIVER"
        else
            print_fail "NPU Driver" "parse error" "$EXPECTED_NPU_DRIVER"
        fi
    fi
}

# ============================================================================
# Main
# ============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --release-ver-only)
            RUN_RELEASE_VER=1
            RUN_CLI_CHECK=0
            shift
            ;;
        --cli-check-only)
            RUN_RELEASE_VER=0
            RUN_CLI_CHECK=1
            shift
            ;;
        --quiet)
            QUIET_MODE=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${TAG_ERROR} Unknown option: $1"
            show_help
            exit 2
            ;;
    esac
done

# Pre-flight
if [[ ! -f "${COMPAT_MD}" ]]; then
    echo -e "${TAG_ERROR} Compatibility matrix file not found: ${COMPAT_MD}"
    exit 2
fi

# Read current suite version
SUITE_VERSION=$(read_suite_version)

# Parse expected versions from markdown matrix
parse_matrix "$SUITE_VERSION"

if [[ $QUIET_MODE -eq 0 ]]; then
    echo ""
    echo -e "${COLOR_BOLD}=== Version Compatibility Check ===${COLOR_RESET}"
    echo -e "DX-AllSuite version: ${COLOR_BRIGHT_CYAN}${SUITE_VERSION}${COLOR_RESET}"
fi

# Run checks
if [[ $RUN_RELEASE_VER -eq 1 ]]; then
    check_release_ver
fi

if [[ $RUN_CLI_CHECK -eq 1 ]]; then
    check_cli_versions
fi

# Summary
if [[ $QUIET_MODE -eq 0 ]]; then
    echo ""
    echo -e "${COLOR_BOLD}--- Result ---${COLOR_RESET}"
fi

if [[ $FAILED_CHECKS -gt 0 ]]; then
    echo -e "${TAG_FAIL} ${PASSED_CHECKS}/${TOTAL_CHECKS} passed, ${FAILED_CHECKS} failed, ${SKIPPED_CHECKS} skipped"
    exit 1
elif [[ $TOTAL_CHECKS -eq 0 && $SKIPPED_CHECKS -gt 0 ]]; then
    echo -e "${TAG_WARN} All checks skipped (${SKIPPED_CHECKS} skipped). Nothing to verify."
    exit 0
else
    echo -e "${TAG_SUCC} ALL PASS (${PASSED_CHECKS}/${TOTAL_CHECKS} passed, ${SKIPPED_CHECKS} skipped)"
    exit 0
fi
