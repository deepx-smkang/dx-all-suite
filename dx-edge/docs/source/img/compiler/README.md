# DEEPX Compiler Solution — figures

Figures referenced by `02_DEEPX_Compiler_Solution.md` (and its `_kor` edition).

## Already in place

| File | Used in | Shows |
| :--- | :--- | :--- |
| `fig01_marketplace_listing.png` | section 1 | The DEEPX Compiler Solution product page on AWS Marketplace |
| `fig02_launch_configuration.png` | section 3, Step 1 | The launch page with Service set to Amazon EC2, the vendor-recommended instance type, and the network and key pair settings |

The VPC ID, subnet ID and CIDR, and key pair name in `fig02` are masked with placeholders.
The AMI alias and the per-Region AMI IDs are left visible — they are public Marketplace
identifiers and are useful to the reader.

## Still needed

Both are terminal captures, and both must be taken **on the EC2 instance launched from the
DEEPX Compiler Solution AMI** — a local machine would not show what the section describes.
Connect over SSH as the `ubuntu` user, per the vendor's launch and connection instructions
on the Marketplace launch page.

### `fig03_dx_compile_run.png`
- **Placement** — section 3, Step 3 ("Run the Compilation"), right after the `dx-compile` command block.
- **Must show** — a terminal on the instance running
  `dx-compile yolov5-s-face_640x640.onnx`, with the command line itself visible at the top
  and the compiler's progress and completion output below. If the log is long, capture the
  head and tail rather than a mid-section with no context.
- **Keep the prompt visible** — `ubuntu@ip-10-0-1-23:~$` is what identifies the terminal as
  running on the instance. The address is private and non-routable, so it does not need masking.
- **This is the single most useful figure in the document** — it is the only one that shows
  the compiler actually doing its job.

### `fig04_dxnn_output.png`
- **Placement** — section 3, Step 3, after the sentence about uploading the artifact.
- **Must show** — `ls -lhR` in the working directory, with the produced `.dxnn` file and its
  size, captured in the same terminal session as `fig03`.
- **Optional extra** — the following `aws s3 cp` upload succeeding in the same capture.
- **Please confirm two things while capturing this**, so the document can be corrected if needed:
  1. Where `dx-compile` writes the artifact — the document currently assumes it lands in the
     working directory next to the model, and uploads `yolov5-s-face_640x640.dxnn` from there.
  2. What `dx-compile --help` reports — specifically how to pass a compilation configuration
     file and an output path. Section 3, Step 3 links to `--help` rather than naming flags,
     because the vendor instructions document only the single-argument form.

## Optional — CloudFormation deployment

Section 4 runs the same pipeline the DEEPX Greengrass Solution deploys, so the existing
figures can be reused instead of capturing new ones: `../greengrass/fig05.png` (S3 upload)
and `../greengrass/fig06.png` (Step Functions execution succeeded).

Capture these only if you want the CloudFormation deployment illustrated with a
compiler-only stack, where the stack and resource names differ from the Greengrass walkthrough:

- `fig05_stepfunctions_succeeded.png` — the Step Functions execution graph with every state
  green, the status **Succeeded**, and the state machine name.
- `fig06_cloudwatch_logs.png` — the `/dx-compiler/<stack-name>/execution` log group with the
  lines that trace the S3 download, the compiler invocation, and the `.dxnn` upload.

## Capture rules

- **Format / size** — PNG, at least 1600 px wide, matching the Greengrass figures
  (`../greengrass/fig01.png` … `fig08.png`), which run 1700–2200 px wide.
- **Browser chrome** — crop console screenshots to the content pane. No browser tabs,
  bookmark bar, or OS taskbar.
- **Light mode** — capture the AWS console in light mode so the figures match the Greengrass set.
- **Terminal** — dark or light is fine, but keep one style across `fig03` and `fig04`.
  Use a monospace font at a size that stays legible after downscaling.
- **Redact before committing** — the 12-digit AWS account ID, any ARN containing it, access
  key IDs, public IP addresses and public DNS names, and the S3 bucket name if it is not a
  throwaway. Blur or solid-block them; do not rely on cropping alone.
- **Consistent example** — use `yolov5-s-face_640x640` throughout, as the document does.

## After adding a file

Insert the image reference and an italic caption in **both** the English and Korean editions,
keeping the figure numbering aligned across the two:

```markdown
![Running dx-compile on the instance](img/compiler/fig03_dx_compile_run.png)

*Figure 3. Compiling the ONNX model with dx-compile on the EC2 instance*
```
