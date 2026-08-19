# DEEPX Compiler Solution

**Compiling ONNX models into the DEEPX NPU execution format (DXNN) on AWS**

A DEEPX NPU does not run a standard ONNX model as is. The model must first be converted into the DXNN (`.dxnn`) format, which contains the instruction set and weights the NPU executes. The DEEPX compiler `dxcom` performs this conversion. Compilation includes a calibration step for INT8 quantization, so it requires a representative dataset along with sufficient CPU and memory resources.

This document describes how to run that compilation step on AWS using the **DEEPX Compiler Solution**. Instead of building a compilation environment locally, you use the DX-Compiler AMI from AWS Marketplace to launch an instance only when you need one.

!!! note "Scope of this document"
    This document covers **model compilation only**. To deploy a compiled DXNN model to an edge device and install the NPU driver, firmware, and runtime automatically, see [DEEPX Greengrass Solution](01_DEEPX_Greengrass_Solution.md). The Greengrass Solution includes the compilation pipeline described here.

---

## 1. Two Usage Paths

The DEEPX Compiler Solution offers two paths, depending on how you want to work. Choose the one that fits your purpose.

| | **Path A — Using the DX-Compiler AMI directly** | **Path B — Event-driven compilation pipeline** |
| :--- | :--- | :--- |
| Delivery form | AMI (Amazon Machine Image) | CloudFormation stack |
| How it runs | You launch an EC2 instance and run `dxcom` yourself | You upload files to S3 and compilation starts automatically |
| Best suited for | Experimenting by changing compilation options repeatedly, interactive debugging | Running a standardized compilation repeatedly, integrating with CI and automation |
| Instance lifecycle | You start and stop the instance | The workflow starts and stops the instance |
| Marketplace | [DX-Compiler (AMI)](https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo) | Included in [DEEPX Greengrass Solution](https://aws.amazon.com/marketplace/pp/prodview-732s46qfzuh34) |

Both paths use the same `dxcom` compiler and the same calibration dataset, so the compilation result is identical.

---

## 2. Prerequisites

- An AWS account and permissions to launch EC2 instances or create a CloudFormation stack
- The ONNX model to compile and its JSON configuration file. In addition to models you train yourself, you can download pre-trained models validated for DEEPX NPUs from the [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/) and use them directly.
- An existing VPC and subnet in which to run the instance. The subnet must be able to reach the required AWS services, including Amazon S3, AWS Systems Manager, and Amazon CloudWatch Logs, over HTTPS. If you use a private subnet, configure a NAT gateway or the necessary VPC endpoints.
- Credentials configured locally if you want to run AWS CLI commands from your machine

### Configuring the AWS CLI Locally

Skip this section if you have already configured the AWS CLI.

```bash
aws configure
# AWS Access Key ID [None]: <access-key-id>
# AWS Secret Access Key [None]: <secret-access-key>
# Default region name [None]: <region, for example us-east-1>
# Default output format [None]: json

# Verify that the credentials are configured correctly
aws sts get-caller-identity
```

If the command prints your account ID and user ARN, the configuration is complete.

---

## 3. Path A — Using the DX-Compiler AMI Directly

[DX-Compiler (AMI)](https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo) in AWS Marketplace is an Amazon Machine Image with the DEEPX model compiler `dxcom` and the calibration dataset preinstalled. There is nothing to install: you can start compiling as soon as the instance launches.

### Step 1. Subscribe and Launch an Instance

1. On the Marketplace product page, choose **Continue to Subscribe**. There is no software subscription charge; you pay only for the AWS resources you use.
2. On **Continue to Configuration**, choose the Region and AMI version to deploy.
3. On **Continue to Launch**, specify the instance type, VPC and subnet, security group, and key pair, and launch the instance.

!!! note "Choosing an instance type"
    Compilation is a CPU-intensive and memory-intensive job. The compilation pipeline in the DEEPX Greengrass Solution uses `t3.xlarge` by default. Depending on model size and the number of calibration images, a larger instance may perform better.

Configure the security group to allow only the outbound traffic you need. Compilation itself does not require inbound connectivity. If you need to work interactively, we recommend using AWS Systems Manager Session Manager instead of SSH so that no inbound ports are open.

### Step 2. Prepare the Model and Configuration File

After you connect to the instance, prepare the ONNX model to compile and its JSON configuration file.

```bash
# Download a sample model from the Model Zoo
curl -fLO https://sdk.deepx.ai/modelzoo/onnx/yolov5-s-face_640x640.onnx

# Or retrieve your own model from S3
aws s3 cp s3://<your-bucket>/<path>/model.onnx .
```

### Step 3. Run the Compilation

`dxcom` takes the model (`-m`), the configuration file (`-c`), and the output path (`-o`) as arguments.

```bash
dxcom -m yolov5-s-face_640x640.onnx \
      -c yolov5-s-face_640x640.json \
      -o output/yolov5-s-face_640x640
```

When compilation finishes, a `.dxnn` file is created at the output path you specified. Upload the artifact to S3 so that edge devices or other environments can download and use it.

```bash
aws s3 cp output/yolov5-s-face_640x640.dxnn s3://<your-bucket>/<path>/
```

### Step 4. Terminate the Instance

Compilation is a one-time job, so terminate the instance when you are done to stop incurring charges. If you expect to compile repeatedly, the automated pipeline in Path B is a better choice for both management and cost.

---

## 4. Path B — Event-Driven Compilation Pipeline

In Path B, no one handles the compiler instance directly. When you upload a model and a configuration file to Amazon S3, an event starts a workflow that launches an instance based on the DX-Compiler AMI, runs the compilation, and then terminates the instance. All you have to do is download the result.

This pipeline is included in the DEEPX Greengrass Solution CloudFormation stack. For the stack deployment procedure and parameters, see the [DEEPX Greengrass Solution](01_DEEPX_Greengrass_Solution.md) document.

### How It Works

1. You upload the `.onnx` model and the `.json` configuration file to the **same path** in the S3 model bucket.
2. An S3 `ObjectCreated` event invokes an AWS Lambda trigger function. The function looks for the matching file in the same path and proceeds to the next step **only when both files are present**. The execution name is generated as a hash based on the file names, which prevents duplicate runs.
3. The AWS Step Functions compilation workflow starts.
4. The workflow launches an Amazon EC2 instance based on the DX-Compiler AMI. The instance runs in the existing VPC and subnet specified by the CloudFormation parameters.
5. AWS Systems Manager Run Command sends the compilation commands defined in an SSM document to the instance.
6. The `dxcom` compiler preinstalled on the instance runs. At this point, the `dataset_path` value in the configuration file is automatically replaced with `/opt/dx-compiler/calibration_dataset`, the calibration dataset path included in the AMI.
7. The compiled `.dxnn` binary is uploaded to the same S3 path as the source model. The workflow terminates the instance whether the job succeeds or fails, so there is no idle cost, and you can review execution logs in the Amazon CloudWatch Logs log group (`/dx-compiler/<stack-name>/execution`).

### Example

```bash
export STACK_NAME=<cloudformation-stack-name>

export MODEL_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ModelBucketName'].OutputValue" \
  --output text)

export MODEL_PREFIX=models/yolov5-s-face_640x640

aws s3 cp --only-show-errors yolov5-s-face_640x640.onnx "s3://${MODEL_BUCKET}/${MODEL_PREFIX}/"
aws s3 cp --only-show-errors yolov5-s-face_640x640.json  "s3://${MODEL_BUCKET}/${MODEL_PREFIX}/"

# Check the result after compilation completes
aws s3 ls "s3://${MODEL_BUCKET}/${MODEL_PREFIX}/"
```

!!! note "Use a dedicated prefix per model"
    The trigger function treats the `.onnx` and `.json` files in the same path as a pair. When you work with several models, use a separate prefix for each one so that configuration files for different models do not get mixed together.

---

## 5. Compilation Configuration File (JSON)

The compilation configuration file defines the input tensor shape and the calibration method used for INT8 quantization. The following is an example for a detection model that takes 640×640 input.

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

| Item | Description |
| :--- | :--- |
| `inputs` | The input tensor names and shapes. These must match the input definition of the ONNX model. |
| `calibration_num` | The number of images to use for calibration |
| `calibration_method` | The calibration algorithm (for example, `ema`) |
| `default_loader.dataset_path` | The path to the calibration dataset |
| `default_loader.preprocessings` | Configure these to match the preprocessing used during training to minimize accuracy loss. |

!!! note "Automatic `dataset_path` replacement"
    When you use the Path B pipeline, whatever value you set for `dataset_path` in the configuration file is automatically replaced at compilation time with the calibration dataset path included in the AMI (`/opt/dx-compiler/calibration_dataset`). This replacement does not apply when you run `dxcom` yourself in Path A, so you must specify a path that the instance can actually access.

---

## 6. Working with the DEEPX Model Zoo

Even if you do not have a model of your own, you can download pre-trained ONNX models validated for DEEPX NPUs, along with their corresponding configuration files, from the [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/) and compile them immediately. Models are available for the main vision tasks, including object detection, face detection, classification, segmentation, and pose estimation, and accuracy figures after INT8 quantization are published as well.

---

## 7. Cost

There is no software subscription charge for the DEEPX Compiler Solution. However, you incur charges for the following AWS resource usage.

- **Amazon EC2**: You are charged for the time the compiler instance runs. The Path B pipeline runs the instance only during a compilation job and terminates it on both success and failure paths, so there is no idle cost. In Path A, you must terminate the instance yourself.
- **Amazon EBS**: You are charged for the volumes attached to the instance.
- **Amazon S3, AWS Lambda, AWS Step Functions, and Amazon CloudWatch Logs** (Path B): You incur charges for model file storage, event processing, workflow execution, and log retention.

Actual costs vary with model size, compilation time, instance type, Region, and log retention period. Before you deploy, estimate costs using the [AWS Pricing Calculator](https://calculator.aws/) and the current pricing for each service.

---

## 8. Troubleshooting

| Symptom | What to check |
| :--- | :--- |
| The workflow does not start after a file upload (Path B) | Confirm that both the `.onnx` and `.json` files were uploaded to the **same S3 path**. If only one is present, the trigger function waits. |
| The workflow ends in a failure | Review the `dxcom` execution logs in the `/dx-compiler/<stack-name>/execution` log group in Amazon CloudWatch Logs. |
| The instance does not launch | Confirm that the subnet has outbound HTTPS access to the required AWS services (through a NAT gateway or VPC endpoints), and that the Marketplace subscription is complete. |
| A compilation error related to input shape | Confirm that the `inputs` tensor names and shapes in the configuration file match the input definition of the ONNX model. |
| Accuracy after quantization is lower than expected | Confirm that `preprocessings` matches the preprocessing used during training and that `calibration_num` is large enough. |

## 9. Cleaning Up Resources

1. **Path A**: Terminate the EC2 instance when you finish using it. If any EBS volumes are not deleted with the instance, delete them separately.
2. **Path B**: Delete the stack in the CloudFormation console. The model bucket is retained to protect your data, so if you no longer need it, empty the bucket and delete it manually.
3. If you no longer need the AWS Marketplace subscription, cancel it in [Manage subscriptions](https://aws.amazon.com/marketplace/library).

## Next Steps

To run a compiled `.dxnn` model on an edge device, the device must have the NPU driver, firmware, and dx_rt runtime installed. For how to automate this process with AWS IoT Greengrass, see the [DEEPX Greengrass Solution](01_DEEPX_Greengrass_Solution.md) document.

## References

- [DX-Compiler (AMI) — AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo)
- [DEEPX Greengrass Solution — AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-732s46qfzuh34)
- [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/)
- [DEEPX Developer Documentation](https://developer.deepx.ai)
- [Amazon EC2 User Guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html)
- [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [AWS Step Functions Developer Guide](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [DEEPX dx-all-suite — GitHub](https://github.com/DEEPX-AI/dx-all-suite)
