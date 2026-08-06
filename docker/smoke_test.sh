#!/usr/bin/env bash
# Smoke test for released DEEPX Docker images.
#
# No NPU hardware required: every check is an import / file-existence / plugin
# registration probe. Nothing here opens an NPU device, so this runs on a plain
# GitHub Actions runner as well as on a developer machine.
#
# Usage: docker/smoke_test.sh <image_ref> <component> [variant]
#   component : runtime | compiler | modelzoo
#   variant   : rt | rt-app | rt-stream | rt-app-stream   (runtime only; default rt-app-stream)
#
# Exit code: 0 = all checks passed, 1 = at least one check failed (or bad usage).
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: smoke_test.sh <image_ref> <component> [variant]
  component : runtime | compiler | modelzoo
  variant   : rt | rt-app | rt-stream | rt-app-stream   (runtime only; default rt-app-stream)

Examples:
  smoke_test.sh ghcr.io/deepx-ai/dx-runtime:ubuntu-24.04 runtime rt-app-stream
  smoke_test.sh ghcr.io/deepx-ai/dx-compiler:ubuntu-24.04 compiler
EOF
    exit 1
}

[ $# -ge 2 ] || usage

IMAGE="$1"
COMPONENT="$2"
VARIANT="${3:-rt-app-stream}"

FAILED=0

# check <label> <bash snippet executed inside the image>
# The snippet runs under `set -euo pipefail`, so any failing command in it makes
# the container exit non-zero. Failures are reported with the snippet and the
# captured container output so CI logs show exactly which probe broke and why.
check() {
    local label="$1" snippet="$2" out rc=0
    out=$(docker run --rm --entrypoint bash "$IMAGE" -c "set -euo pipefail
$snippet" 2>&1) || rc=$?
    if [ "$rc" -eq 0 ]; then
        printf '  [ OK ] %s\n' "$label"
    else
        {
            printf '  [FAIL] %s (container exit=%d)\n' "$label" "$rc"
            printf '         probe: %s\n' "$snippet"
            printf '%s\n' "$out" | sed 's/^/         | /'
        } >&2
        FAILED=1
    fi
}

# dx_stream installs its plugin to /usr/local/lib/<arch>/gstreamer-1.0, which is
# outside gst's default scan path, and exports GST_PLUGIN_PATH only from
# /root/.bashrc (which early-returns for non-interactive shells). So locate the
# .so and point GST_PLUGIN_PATH at it before asking gst whether the element exists.
# shellcheck disable=SC2016  # intentional: this expands inside the container, not here
GST_PROBE='SO=$(find /usr/local/lib /usr/lib -name libgstdxstream.so 2>/dev/null | head -1)
test -n "$SO"
export GST_PLUGIN_PATH="$(dirname "$SO")"
gst-inspect-1.0 --exists dxpreprocess'

# variant only means something for the runtime image
LABEL="$COMPONENT"
if [ "$COMPONENT" = runtime ]; then
    LABEL="$COMPONENT $VARIANT"
fi

echo "SMOKE TEST: $IMAGE ($LABEL)"

case "$COMPONENT" in
runtime)
    check "dxrtd binary present"        'test -x /usr/local/bin/dxrtd'
    # Must succeed without an NPU driver. If this fails, find the real cause —
    # do not weaken it to a file-existence check. It must not open a device.
    check "dx_engine imports in venv"   'source /venv-dxnn/bin/activate && python -c "import dx_engine"'
    case "$VARIANT" in
    rt)
        check "dx_app absent"           'test ! -d /deepx/dx-runtime/dx_app'
        check "dx_stream absent"        'test ! -d /deepx/dx-runtime/dx_stream'
        ;;
    rt-app)
        check "dx_app present"          'test -d /deepx/dx-runtime/dx_app'
        check "dx_stream absent"        'test ! -d /deepx/dx-runtime/dx_stream'
        ;;
    rt-stream)
        check "dx_app absent"           'test ! -d /deepx/dx-runtime/dx_app'
        check "dx_stream present"       'test -d /deepx/dx-runtime/dx_stream'
        check "dxpreprocess registered" "$GST_PROBE"
        ;;
    rt-app-stream)
        check "dx_app present"          'test -d /deepx/dx-runtime/dx_app'
        check "dx_stream present"       'test -d /deepx/dx-runtime/dx_stream'
        check "dxpreprocess registered" "$GST_PROBE"
        ;;
    *)
        echo "ERROR: unknown variant: $VARIANT" >&2
        usage
        ;;
    esac
    ;;
compiler)
    # Image ends on `USER deepx` with an init-workspace.sh entrypoint; --entrypoint
    # bash skips the workspace chown, and /venv-dxnn stays world-readable, so the
    # import works as the unprivileged user.
    check "dx_com imports in venv"      'source /venv-dxnn/bin/activate && python -c "import dx_com"'
    check "compiler examples present"   'test -d /deepx/dx-compiler/example'
    ;;
modelzoo)
    # dx-modelzoo itself is intentionally NOT pip-installed in the image (see
    # Dockerfile.dx-modelzoo) — only the source tree ships. So verify (a) the
    # dx_rt runtime the image is built on actually works, and (b) the source
    # tarball landed intact, by byte-compiling the package entry point rather
    # than just stat-ing the directory.
    check "dxrtd binary present"        'test -x /usr/local/bin/dxrtd'
    check "dx_engine imports in venv"   'source /venv-dxnn/bin/activate && python -c "import dx_engine"'
    check "modelzoo pyproject present"  'test -f /deepx/dx-modelzoo/pyproject.toml'
    check "modelzoo source compiles"    'source /venv-dxnn/bin/activate && python -m py_compile /deepx/dx-modelzoo/src/dx_modelzoo/main.py'
    ;;
*)
    echo "ERROR: unknown component: $COMPONENT" >&2
    usage
    ;;
esac

if [ "$FAILED" -ne 0 ]; then
    echo "SMOKE TEST FAILED: $IMAGE ($LABEL)" >&2
    exit 1
fi
echo "SMOKE TEST PASSED: $IMAGE ($LABEL)"
