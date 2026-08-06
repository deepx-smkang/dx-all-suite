# AWS Marketplace User Guide

## Overview

Deploying deep learning models to edge environments involves multiple manual steps. You must build NPU drivers to match each device's Linux distribution and kernel version, keep firmware and runtime versions aligned, and convert models trained in the cloud into the target NPU architecture's format. As the number of devices grows, this process repeats itself, and the risk of failures caused by version mismatches grows with it.

This document explains how to automate that process using the **DEEPX Greengrass Solution** available on AWS Marketplace. After deploying a single CloudFormation stack, simply uploading a standard ONNX model to Amazon S3 automatically compiles it into the DEEPX NPU-specific format (DXNN), and the drivers, firmware, and runtime required on edge devices are installed remotely through AWS IoT Greengrass V2. The guide walks through the entire process step by step, from subscribing on Marketplace to verifying the deployment on an edge device.

DEEPX is a company that develops low-power AI semiconductors (NPUs) for edge environments. The **DX-M1** supported by this solution is an M.2 form-factor AI accelerator that delivers 25 TOPS of compute performance at around 3 W of power. It can be installed in the M.2 slot of an arm64 host such as a Raspberry Pi 5 or an x86_64 industrial PC to run real-time inference for vision models such as object detection, face recognition, and OCR, targeting power- and space-constrained environments such as robotics, drones, CCTV, and smart factories.

Deploying these NPUs in the field requires driver, firmware, and runtime configuration work — and the DEEPX Greengrass Solution automates exactly this part with AWS infrastructure.

![Figure 1. DEEPX NPU product lineup](img/aws/fig01_npu_lineup.png)

### DEEPX Products on AWS Marketplace

AWS Marketplace offers the following two DEEPX products.

- **DX-Compiler (AMI)**: An Amazon Machine Image with the DEEPX model compiler (`dxcom`) pre-installed. You can launch an Amazon EC2 instance directly and compile ONNX models with `dxcom`.
- **DEEPX Greengrass Solution (CloudFormation)**: The product covered in this document. A single CloudFormation stack provisions a serverless compilation pipeline built on the DX-Compiler AMI, together with automated edge runtime deployment (ZTP) based on AWS IoT Greengrass V2.

## Solution Architecture

The key features of the DEEPX Greengrass Solution are as follows.

| Feature | Description |
| :--- | :--- |
| **Single-stack deployment** | One AWS CloudFormation stack provisions both the cloud model compilation infrastructure and the edge deployment architecture. |
| **Serverless compilation pipeline** | An event-driven pipeline built on Amazon S3, AWS Lambda, and AWS Step Functions converts ONNX models into the DXNN format for DEEPX NPUs. The compilation EC2 instance starts only when a job runs and terminates on completion. |
| **Automated runtime deployment (ZTP)** | AWS IoT Greengrass V2 automatically installs the runtime environment — the NPU driver (DKMS), firmware, dx_rt, and dx_stream — over the air (OTA). Both the classic Greengrass nucleus and Greengrass nucleus lite for lightweight devices are supported. |

![Figure 2. DEEPX Greengrass Solution overview](img/aws/fig02_solution_overview.png)

The overall architecture consists of two parts: a compilation pipeline running in the cloud, and runtime deployment to edge devices. The following description references the numbering in Figure 3.

![Figure 3. Overall architecture — cloud compilation pipeline (1–7) and edge runtime deployment (A–E)](img/aws/fig03_architecture.png)

### Cloud Compilation Pipeline (ONNX → DXNN)

1. The user uploads a pair of files — an `.onnx` model and a `.json` compilation configuration file — to the same directory in the S3 model bucket.
2. When the S3 `ObjectCreated` event fires, an AWS Lambda trigger function looks for the matching counterpart file in the same directory and proceeds to the next step only when both files of the pair are present. It derives the execution name from a filename-based hash to prevent duplicate executions.
3. The AWS Step Functions compilation workflow starts.
4. The workflow launches an Amazon EC2 instance based on the DX Compiler AMI provided through the Marketplace subscription. The instance runs in the existing VPC/subnet specified via CloudFormation parameters, and its security group allows outbound HTTPS (443) only.
5. AWS Systems Manager Run Command delivers the compilation commands defined in the SSM Document to the instance.
6. The `dxcom` compiler pre-installed on the instance runs. At this point, the `dataset_path` in the configuration file is automatically replaced with the calibration dataset path bundled in the AMI (`/opt/dx-compiler/calibration_dataset`).
7. The compiled `.dxnn` binary is uploaded to the same S3 directory as the original model. The workflow terminates the instance regardless of success or failure, so no idle cost is incurred, and execution logs are available in the Amazon CloudWatch Logs log group (`/dx-compiler/<stack-name>/execution`).

### Edge Runtime Deployment (AWS IoT Greengrass V2)

!!! note "Scope of ZTP (Zero-Touch Provisioning)"
    In this document, ZTP refers to the process in which drivers, firmware, and runtime are installed automatically — with no on-site work — after a device has been registered in an IoT Thing Group. Initial device registration (provisioning) is covered in Prerequisites.

- **A.** During CloudFormation stack deployment, a Custom Resource Lambda publishes the Greengrass component `com.deepx.dx-runtime`. The publishing is idempotent — if the same version already exists, it is reused — so deploying multiple stacks in one account does not cause conflicts.
- **B.** The published component is included in a Greengrass deployment.
- **C.** The target IoT Thing Group is either the group specified via a parameter or, if unspecified, one auto-created with the name `<stack-name>-cores`. If a group with the same name already exists, it is adopted as-is rather than deleted.
- **D.** The `com.deepx.dx-runtime` component is deployed to each device in the Thing Group via MQTT/TLS-based IoT Jobs.
- **E.** The device downloads the driver, firmware, and runtime packages over HTTPS from the DEEPX public artifact bucket and installs them.

The component recipe is written to support both the classic Greengrass nucleus and Greengrass nucleus lite for resource-constrained devices, so the same deployment pipeline works even on lightweight Raspberry Pi-class devices.

The component performs the installation on the device in the following four steps.

1. **NPU Linux driver (DKMS)**: The `dxrt-driver-dkms` package builds and installs the driver against the target device's kernel version.
2. **dx_rt runtime**: The `libdxrt-bin` package sets up the C/C++-based runtime (`dxcli`, `libdxrt.so`).
3. **Firmware update**: Downloads `fw.bin` and updates the NPU firmware with `dxcli -u`.
4. **dx_stream media pipeline**: Downloads `dx_stream.tar.gz` and sets up the OpenCV/GStreamer-integrated streaming environment.

!!! note "Installation time"
    Installation time varies with device specifications and network conditions. On low-end arm64 devices where dependency libraries are built from source, it can take tens of minutes or longer.

## Prerequisites

To use this solution, the following must be in place.

- An AWS account with permissions to create CloudFormation stacks
- An edge device with a DEEPX DX-M1 M.2 module installed — e.g., a Raspberry Pi 5 (arm64) or an x86_64 Ubuntu host
- [AWS IoT Greengrass Core V2](https://docs.aws.amazon.com/greengrass/v2/developerguide/getting-started.html) installed on the target device and the device registered in an IoT Thing Group — both the classic nucleus and nucleus lite can be used
- A trained ONNX model to deploy
- An existing VPC and subnet in which to run the compiler EC2 instance — the subnet needs internet access or VPC endpoints for S3, SSM, EC2, Step Functions, and CloudWatch Logs (the stack does not create a new VPC)

### AWS Marketplace Subscription

Subscribe on the [DEEPX Greengrass Solution page on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-732s46qfzuh34). The software is free of charge; you pay only for the AWS resources you use (see the **Cost** section below).

![Figure 4. DEEPX Greengrass Solution product page on AWS Marketplace](img/aws/fig04_marketplace_listing.png)

### Local AWS CLI Setup (aws configure)

To run the CLI commands in this guide, such as `aws s3 cp`, from your local working environment, AWS CLI credentials must be configured. Skip this section if they already are.

1. Issue an **access key** for your user in the AWS IAM console (Access Key ID / Secret Access Key).
2. Run `aws configure` to register the access key, default region, and output format.

    ```bash
    aws configure
    # AWS Access Key ID [None]: <access-key-id>
    # AWS Secret Access Key [None]: <secret-access-key>
    # Default region name [None]: <region, e.g. us-east-1>
    # Default output format [None]: json
    ```

3. Verify that the credentials are set up correctly.

    ```bash
    aws sts get-caller-identity
    ```

    If your account ID and user ARN are printed, the setup is complete.

## Step 1 — Deploy the CloudFormation Stack

Run the CloudFormation template provided after subscribing. The main parameters are as follows.

| Parameter | Description |
| :--- | :--- |
| `ImageId` | The SSM parameter path pointing to the DX Compiler AMI. It resolves automatically to the per-region AMI ID, so keep the default value. |
| `ModelBucketName` | The name of the S3 bucket to store model inputs and compilation outputs (must be globally unique). |
| `InstanceType` | The instance type used for compilation. The default is `t3.xlarge`. |
| `VpcId` / `SubnetId` | The existing VPC and subnet in which to place the compiler instance. |
| `ThingGroupName` | The name of the target IoT Thing Group for deployment. If left empty, `<stack-name>-cores` is auto-created; if you enter an existing group name, that group is adopted. |

![Figure 5. CloudFormation stack parameter input screen](img/aws/fig05_cfn_parameters.png)

The stack creates the S3 bucket, Lambda functions, a Step Functions state machine, least-privilege IAM roles, and the Greengrass component and deployment. Once creation completes, you can find the model bucket name, state machine ARN, and log group name in the stack's **Outputs** tab.

![Figure 6. Stack creation complete (CREATE_COMPLETE)](img/aws/fig06_cfn_create_complete.png)

## Step 2 — Upload an ONNX Model and Compile Automatically

Prepare the model and configuration file to compile. Besides models you trained yourself, you can also download pre-trained models validated for DEEPX NPUs from the [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/) and compile them right away.

!!! note "Automatic dataset_path substitution"
    Whatever value you put in the configuration file's `dataset_path`, it is automatically replaced at compile time with the path of the calibration dataset bundled in the AMI.

The following is an example configuration file.

```json
{
    "inputs": {
        "input.1": [1, 3, 640, 640]
    },
    "calibration_num": 100,
    "calibration_method": "ema",
    "default_loader": {
        "dataset_path": "/mnt/datasets/widerface/WIDER_val/images",
        "file_extensions": ["jpeg", "jpg", "png", "JPEG"],
        "preprocessings": [
            {
                "resize": {
                    "mode": "pad",
                    "size": 640,
                    "pad_location": "edge",
                    "pad_value": [114, 114, 114]
                }
            },
            {
                "convertColor": {
                    "form": "BGR2RGB"
                }
            },
            {
                "transpose": {
                    "axis": [2, 0, 1]
                }
            },
            {
                "div": {
                    "x": 255.0
                }
            },
            {
                "expandDim": {
                    "axis": 0
                }
            }
        ]
    }
}
```

Upload the model (`.onnx`) and configuration file (`.json`) to the same directory in the S3 model bucket. Once both files are uploaded, the pipeline starts automatically.

```bash
aws s3 cp yolov5-s-face_640x640.onnx s3://<model-bucket>/
aws s3 cp yolov5-s-face_640x640.json s3://<model-bucket>/
```

![Figure 7. .onnx / .json files uploaded to the S3 model bucket](img/aws/fig07_s3_upload.png)

You can monitor the workflow's progress in the Step Functions console. The workflow proceeds in the order of instance launch → compilation → status polling → instance termination, and it is designed to terminate the instance on the failure path as well.

![Figure 8. Step Functions compilation workflow execution result (Succeeded)](img/aws/fig08_stepfunctions_succeeded.png)

After completion, check the compiled `.dxnn` file in the same S3 directory as the original model. Detailed compilation logs are recorded in the CloudWatch Logs log group `/dx-compiler/<stack-name>/execution`.

```bash
aws s3 ls s3://<model-bucket>/
```

![Figure 9. .dxnn file created in the same directory after compilation](img/aws/fig09_dxnn_in_s3.png)

## Step 3 — Deploy the Runtime to Edge Devices (ZTP)

The `com.deepx.dx-runtime` component published during stack deployment is included in a Greengrass deployment targeting the Thing Group. If devices are registered in the Thing Group, the deployment triggers automatically, and the four-step runtime installation described earlier proceeds in sequence.

Confirm in the Greengrass console that the deployment status becomes **Completed**.

![Figure 10. Greengrass deployment execution result — all target devices Succeeded](img/aws/fig10_greengrass_deployment.png)

You can check the component installation logs on the device. Use the log file for the classic nucleus, and the systemd journal for nucleus lite.

```bash
# Classic Greengrass nucleus
sudo tail -f /greengrass/v2/logs/com.deepx.dx-runtime.log

# Greengrass nucleus lite
sudo journalctl -f -u ggl.com.deepx.dx-runtime.service
```

## Step 4 — Verify the Deployment

Once the installation completes, use `dxcli` on the device to check the NPU detection status and firmware version.

```bash
dxcli -s
```

![Figure 11. dxcli -s output — NPU device detected and firmware version confirmed](img/aws/fig11_dxcli_status.png)

Before running the dx_stream demo, set environment variables so the shell can find dx_stream's GStreamer plugins and libraries. Add the following to the end of `~/.bashrc`. It determines the architecture-specific plugin path automatically, so the same snippet works on both x86_64 and aarch64 (Raspberry Pi).

```bash
GST_ARCH_TRIPLET="$(gcc -dumpmachine 2>/dev/null || true)"
if [ -z "$GST_ARCH_TRIPLET" ]; then
    case "$(uname -m)" in
        x86_64) GST_ARCH_TRIPLET="x86_64-linux-gnu" ;;
        aarch64|arm64) GST_ARCH_TRIPLET="aarch64-linux-gnu" ;;
        armv7l|armv6l) GST_ARCH_TRIPLET="arm-linux-gnueabihf" ;;
        *) GST_ARCH_TRIPLET="$(uname -m)-linux-gnu" ;;
    esac
fi
GST_PLUGIN_DIR="/usr/local/lib/$GST_ARCH_TRIPLET/gstreamer-1.0"
export GST_PLUGIN_PATH="$GST_PLUGIN_DIR:$GST_PLUGIN_PATH"
export LD_LIBRARY_PATH="$GST_PLUGIN_DIR:/usr/local/share/gstdxstream/lib:$LD_LIBRARY_PATH"
export PATH="/usr/local/share/gstdxstream/bin:/usr/local/bin:$PATH"
```

After applying the changes, verify that the dx_stream plugin is registered correctly with the `gst-inspect-1.0` command.

```bash
source ~/.bashrc
gst-inspect-1.0 dxstream
```

![Figure 12. gst-inspect-1.0 dxstream output — 13 elements registered](img/aws/fig12_gst_inspect.png)

Downloading the compiled `.dxnn` model to the device and running inference through a dx_stream pipeline completes the end-to-end flow.

First, download the compiled `.dxnn` model from the S3 model bucket to the device.

```bash
aws s3 cp s3://<model-bucket>/yolov5-s-face_640x640.dxnn .
```

Download and extract the sample videos used for testing.

```bash
curl -fSLO https://sdk.deepx.ai/res/video/sample_videos.tar.gz
tar xzf sample_videos.tar.gz
```

Set the model path and input video path as environment variables. `INPUT_VIDEO_PATH` must be an absolute path; pick any file you like from the extracted videos.

```bash
export MODEL_PATH="$PWD/yolov5-s-face_640x640.dxnn"
export INPUT_VIDEO_PATH="$PWD/dance-group.mov"
export VIDEOCONVERT_PIPELINE="videoconvert"
```

Now run inference with the dx_stream pipeline. `dxpreprocess` converts video frames to the model input size (640×640), and `dxinfer` performs inference on the NPU. `dxpostprocess` interprets the detection results using the YOLOv5s-Face post-processing library, and `dxosd` draws the bounding boxes onto the video, which `fpsdisplaysink` displays on screen along with the FPS.

```bash
gst-launch-1.0 urisourcebin uri=file://$INPUT_VIDEO_PATH ! decodebin ! \
    dxpreprocess \
        preprocess-id=1 \
        resize-width=640 \
        resize-height=640 ! \
    queue max-size-buffers=1 ! \
    dxinfer \
        preprocess-id=1 \
        inference-id=1 \
        model-path=$MODEL_PATH ! \
    queue max-size-buffers=1 ! \
    dxpostprocess \
        inference-id=1 \
        library-file-path=/usr/local/share/gstdxstream/lib/libpostprocess_yolov5s_face.so \
        function-name=PostProcess ! \
    queue max-size-buffers=1 ! \
    dxosd ! \
    $VIDEOCONVERT_PIPELINE ! fpsdisplaysink sync=false
```

![Figure 13. dx_stream pipeline inference result — YOLOv5s-Face face detection with landmarks](img/aws/fig13_dxstream_result.png)

## Cost

The solution's software license is free of charge; you pay for the AWS resources you use.

- **Amazon EC2**: The compiler instance (default `t3.xlarge`) runs only during compilation jobs and is terminated regardless of success or failure, so you are billed only for the actual compilation time. For per-instance-type pricing, see [EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/).
- **Amazon S3 / AWS Lambda / AWS Step Functions**: Small charges apply for storing model files and running the pipeline.
- **AWS IoT Greengrass**: For pricing based on the number of devices, see [AWS IoT Greengrass pricing](https://aws.amazon.com/greengrass/pricing/).

!!! note "Measured cost reference"
    In a measured run with the YOLOv5s-Face model, compilation took about 12 minutes 30 seconds on the default `t3.xlarge` instance, and the billed time from instance launch to termination was about 17 minutes. At the US East (N. Virginia, us-east-1) On-Demand rate ($0.1664 per hour), a single compilation costs about $0.05 including the EBS volume. Time and cost may vary with model size and region.

## Cleaning Up Resources

To avoid ongoing charges, clean up resources in the following order after the walkthrough.

1. Delete the stack in the CloudFormation console. The Thing Group and component versions created by the stack are cleaned up with it, but a pre-existing group that was adopted is not deleted.
2. The model bucket is retained after stack deletion to protect your data. If it is no longer needed, empty the bucket and delete it yourself.
3. If you no longer need the AWS Marketplace subscription, cancel it in [Manage subscriptions](https://aws.amazon.com/marketplace/library).
4. (Optional) Revise the deployment in the Greengrass console to remove the component from the devices.

## References

- [DEEPX Greengrass Solution — AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-732s46qfzuh34)
- [AWS IoT Greengrass V2 Developer Guide](https://docs.aws.amazon.com/greengrass/v2/developerguide/what-is-iot-greengrass.html)
- [AWS Step Functions](https://aws.amazon.com/step-functions/)
- [DEEPX Developer Documentation](https://developer.deepx.ai)
- [DEEPX dx-all-suite — GitHub](https://github.com/DEEPX-AI/dx-all-suite)
