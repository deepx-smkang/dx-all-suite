# DX Cloud (AWS)

The studio's entry point to **DEEPX on AWS Marketplace** — compile ONNX models into
`.dxnn` in the cloud and roll the NPU runtime out to edge devices automatically, with
every card linking straight to the relevant Marketplace listing or guide. Open it from
the hub tile (☁️) or with `Alt`+`9`.

AWS Marketplace offers two DEEPX products, and the page is organized around them:

- **DX-Compiler (AMI)** — an Amazon Machine Image with the DEEPX model compiler
  (`dxcom`) pre-installed.
- **DEEPX Greengrass Solution (CloudFormation)** — a single stack that provisions a
  serverless compilation pipeline plus automated edge runtime deployment (ZTP) based
  on AWS IoT Greengrass V2.

## AWS Compiler

Two cards cover cloud compilation:

- **DX-Compiler (AMI)** — launch an Amazon EC2 instance from the DX-Compiler AMI and
  compile ONNX models to `.dxnn` directly with the pre-installed `dxcom`. The card's
  button searches for DEEPX on AWS Marketplace.
- **Cloud Compile Pipeline** — the fully automatic route. After subscribing, set your
  local credentials with `aws configure`, then upload a pair of files — the `.onnx`
  model and its `.json` compilation config — to the same directory in the S3 model
  bucket. The event-driven pipeline (S3 → Lambda → Step Functions) launches a compiler
  instance, runs `dxcom`, drops the compiled `.dxnn` back into S3, and terminates the
  instance — so you only download the result:

```bash
aws configure
aws s3 cp yolov5-s-face_640x640.onnx s3://<model-bucket>/
aws s3 cp yolov5-s-face_640x640.json s3://<model-bucket>/
aws s3 cp s3://<output-bucket>/yolov5-s-face_640x640.dxnn .
```

## AWS Greengrass

Two cards cover edge deployment:

- **Subscribe & Deploy Stack** — subscribe to the DEEPX Greengrass Solution on
  Marketplace, then deploy the provided CloudFormation stack; it auto-provisions the
  IoT Core / Greengrass resources together with the compilation pipeline above. The
  card's button opens the Marketplace listing.
- **Thing Group & ZTP** — register a device in the target IoT Thing Group and the
  runtime installs automatically over the air (Zero-Touch Provisioning): the NPU Linux
  driver (DKMS), firmware, `dx_rt`, and `dx_stream` — no on-site work needed. Both the
  classic Greengrass nucleus and nucleus lite are supported.

!!! note "Related"
    The full step-by-step walkthrough — stack parameters, S3 upload, ZTP verification
    with `dxcli` and a `dx_stream` demo, plus cost and cleanup — is in the
    [AWS Marketplace User Guide](https://developer.deepx.ai/06_AWS_Marketplace_Guide.html).
    For compiling locally inside the studio instead, see
    **[DX Compiler](04_DX_Compiler.md)**.
