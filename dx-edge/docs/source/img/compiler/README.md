# DEEPX Compiler Solution — figures

Screenshots referenced by `02_DEEPX_Compiler_Solution.md` (and its `_kor` edition).
Place them in this directory using exactly these filenames.

## Common capture rules

- **Format / size** — PNG, at least 1600 px wide. Match the existing Greengrass figures
  (`../greengrass/fig01.png` … `fig08.png`), which run 1700–2200 px wide.
- **Browser chrome** — crop the console screenshots to the content pane. Do not include
  browser tabs, the bookmark bar, or the OS taskbar.
- **Light mode** — capture the AWS console in light mode so the figures match the
  Greengrass set.
- **Terminal** — dark or light is fine, but keep one style across `fig03` and `fig04`.
  Use a monospace font at a size that stays legible after downscaling.
- **Terminal figures must be captured on the EC2 instance, not on a local machine.**
  Path A is defined as launching an instance from the DX-Compiler AMI and running `dxcom`
  there, so the figure has to make that evident. Either capture method works:
  - **Session Manager (recommended)** — EC2 console → select the instance → **Connect** →
    **Session Manager**. Capture the browser terminal together with the console header so
    the instance ID is visible. This matches the document's own advice to use Session
    Manager rather than opening an inbound SSH port.
  - **SSH** — capture a local terminal SSH'd into the instance, leaving the
    `ubuntu@ip-10-0-1-23:~$` prompt visible so the host is identifiable as the instance.
- **Redact before committing** — the 12-digit AWS account ID, any ARN containing it,
  access key IDs, public IP addresses and public DNS names, and the S3 bucket name if it is
  not a throwaway. Blur or solid-block them; do not rely on cropping alone.
  **Keep** the default EC2 host name in the shell prompt (`ubuntu@ip-10-0-1-23`) — the
  address is private, non-routable, and it is what proves the terminal is on the instance.
- **Consistent example** — use the same model across every figure. The document walks
  through `yolov5-s-face_640x640`.

## Required — Path A (DX-Compiler AMI)

Nothing in the document illustrates Path A today, so these four carry the most value.

### `fig01_ami_listing.png`
- **Placement** — section 3, Step 1 ("Subscribe and Launch an Instance"), before the numbered steps.
- **Must show** — the DX-Compiler AMI product page on AWS Marketplace with the product
  title, the DEEPX vendor name, the pricing area showing the software cost as free, and the
  **Continue to Subscribe** button.
- **Source** — https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo

### `fig02_launch_configuration.png`
- **Placement** — section 3, Step 1, after step 3 of the numbered list.
- **Must show** — the launch configuration screen with the Region, the AMI version, the
  selected instance type (`t3.xlarge` keeps it consistent with the document), and the
  VPC / subnet / security group fields.
- **Note** — the Marketplace "Launch through EC2" screen and the EC2 console launch wizard
  are both acceptable; pick whichever matches the wording in Step 1.

### `fig03_dxcom_run.png`
- **Placement** — section 3, Step 3 ("Run the Compilation"), right after the `dxcom` command block.
- **Must show** — a terminal on the instance running
  `dxcom -m yolov5-s-face_640x640.onnx -c yolov5-s-face_640x640.json -o output/yolov5-s-face_640x640`,
  with the command line itself visible at the top and the compiler's progress and
  completion output below. If the log is long, capture the head and tail rather than a
  mid-section with no context.
- **This is the single most useful figure in the document** — it is the only one that shows
  the compiler actually doing its job.

### `fig04_dxnn_output.png`
- **Placement** — section 3, Step 3, after the sentence about the generated `.dxnn` file.
- **Must show** — `ls -lhR output/` with the produced `.dxnn` file and its size, captured in
  the same terminal session as `fig03`.
- **Optional extra** — the following `aws s3 cp` upload succeeding in the same capture.
- **Please confirm the actual output layout while capturing this.** The document currently
  passes `-o output/yolov5-s-face_640x640` and then uploads
  `output/yolov5-s-face_640x640.dxnn`, which assumes `-o` takes a path prefix. If `dxcom`
  instead treats it as a directory and writes the artifact inside it, the `aws s3 cp` path
  in section 3, Step 3 needs to be corrected to match.

## Optional — Path B (event-driven pipeline)

Path B runs the same pipeline the Greengrass Solution deploys, so the existing figures can
be reused instead of capturing new ones. Reference them as
`../greengrass/fig05.png` (S3 upload) and `../greengrass/fig06.png` (Step Functions
execution succeeded).

Capture these only if you want Path B illustrated with a compiler-only stack, where the
stack name and resource names differ from the Greengrass walkthrough:

### `fig05_stepfunctions_succeeded.png`
- **Placement** — section 4, after "How It Works".
- **Must show** — the Step Functions execution graph with every state green and the status
  **Succeeded**, plus the state machine name.

### `fig06_cloudwatch_logs.png`
- **Placement** — section 4, at the end of "Example".
- **Must show** — the `/dx-compiler/<stack-name>/execution` log group with the lines that
  trace the S3 download, the `dxcom` invocation, and the `.dxnn` upload.

## After adding the files

Insert the image reference and an italic caption in **both** the English and Korean
editions, keeping the numbering aligned across the two:

```markdown
![DX-Compiler AMI on AWS Marketplace](img/compiler/fig01_ami_listing.png)

*Figure 1. The DX-Compiler AMI product page on AWS Marketplace*
```
