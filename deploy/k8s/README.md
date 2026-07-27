# DX-M1 on Kubernetes (k3s)

Enables scheduling DEEPX DX-M1 NPUs on k3s. The device plugin itself lives in the
[`dx-k8s-device-plugin`](../../dx-k8s-device-plugin) submodule; this dir holds the
`dx-npu` Helm chart, the NFD labeling rule, and sample workloads.

## Architecture

```
host (per NPU node)          k3s cluster
─────────────────────        ─────────────────────────────────────────
dx-runtime/install.sh   ──►  driver (dxrt-driver-dkms) + firmware + dxrtd
containerd CDI enabled       (enable_cdi=true, cdi_spec_dirs incl /etc/cdi)

Helm: dx-npu ──► NodeFeatureRule (PCI 1ff4 → deepx.ai/dx-m1.present)
              └► device-plugin DaemonSet → advertises deepx.ai/dx-m1
                   ├─ writes /etc/cdi/deepx.json  (device nodes + host libs)
                   └─ Allocate → CDI ref deepx.ai/dx-m1=<id>
Pod requests deepx.ai/dx-m1: 1 → containerd injects /dev/dxrtN + libs
```

Design rationale and vendor survey: `.omc/research/` and `.omc/plans/` in the repo root.

## Prerequisites

1. **Each NPU node** — host driver + firmware + runtime:
   ```bash
   cd dx-runtime && ./install.sh --runtime-only
   dxrt-cli -s   # must list the NPU(s)
   ```
2. **k3s containerd CDI** — add to `/var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl`:
   ```toml
   [plugins."io.containerd.grpc.v1.cri".cdi]
     enable_cdi = true
     cdi_spec_dirs = ["/etc/cdi", "/var/run/cdi"]
   ```
   then `systemctl restart k3s`. (k3s manages containerd config; edit the template,
   not config.toml directly.)
3. **NFD** — node-feature-discovery in the cluster (set `nfd.enabled=true` to let this
   chart pull it in, or install separately). Required for the NodeFeatureRule.

## Install

```bash
helm install dx-npu ./charts/dx-npu -n dx-system --create-namespace
kubectl get node -o json | jq '.status.allocatable' | grep deepx.ai/dx-m1
kubectl apply -f samples/test-pod.yaml && kubectl logs -f dx-m1-test
```

## Key values

| Value | Default | Purpose |
|---|---|---|
| `resourceName` | `deepx.ai/dx-m1` | advertised extended resource |
| `devicePlugin.image.tag` | `latest` | plugin image (ghcr) |
| `devicePlugin.nodeSelectorLabel` | `deepx.ai/dx-m1.present` | NFD gate |
| `nodeFeatureRule.enabled` | `true` | apply the PCI 1ff4 label rule |
| `nfd.enabled` | `false` | also deploy NFD itself |

## Not yet included

`nfd.enabled` currently only reserves the toggle — wire NFD as a chart dependency (or
document an external install) before relying on it. A `deepx_npu_*` Prometheus metrics
exporter is planned in the plugin repo.
