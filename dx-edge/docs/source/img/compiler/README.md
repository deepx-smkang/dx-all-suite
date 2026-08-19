# DEEPX Compiler Solution — figures

Figures referenced by `02_DEEPX_Compiler_Solution.md` (and its `_kor` edition).
All four are in place; this file documents what they show and how they were captured, so
they can be reproduced when the product or the compiler changes.

| File | Used in | Shows |
| :--- | :--- | :--- |
| `fig01_marketplace_listing.png` | section 1 | The DEEPX Compiler Solution product page on AWS Marketplace |
| `fig02_launch_configuration.png` | section 3, Step 1 | The launch page with Service set to Amazon EC2, the vendor-recommended instance type, and the network and key pair settings |
| `fig03_dxcom_run.png` | section 3, Step 3 | `dxcom -m/-c/-o` running on the instance — compilation configuration, quantization and preprocessing decisions, and the progress bar at 100% |
| `fig04_dxnn_output.png` | section 3, Step 3 | `ls -lhR output/` showing the `.dxnn` artifact inside the output directory |

The VPC ID, subnet ID and CIDR, and key pair name in `fig02` are masked with placeholders.
The AMI alias and the per-Region AMI IDs are left visible — they are public Marketplace
identifiers and are useful to the reader.

## Reproducing the terminal figures

`fig03` and `fig04` are captured **on the EC2 instance launched from the DEEPX Compiler
Solution AMI**, not on a local machine. Connect over SSH as the `ubuntu` user, per the
vendor's launch and connection instructions on the Marketplace launch page.

1. Download the model and write the configuration file — see section 3, Step 2 of the document.
2. Run `clear` before the compile command, so the SSH invocation above it (which contains the
   instance's public IP) is off screen.
3. Run the `dxcom` command from section 3, Step 3 and capture once the progress bar reaches 100%.
4. Run `clear`, then `ls -lhR output/`, and capture.

Keep the `ubuntu@ip-172-31-x-x:~$` prompt visible in both. The address is private and
non-routable, and it is what identifies the terminal as running on the instance.

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

- **Format / size** — PNG. Console screenshots at least 1600 px wide, matching the Greengrass
  figures (`../greengrass/fig01.png` … `fig08.png`), which run 1700–2200 px wide. Terminal
  captures only need to be wide enough that the text stays legible at full size.
- **Browser chrome** — crop console screenshots to the content pane. No browser tabs,
  bookmark bar, or OS taskbar.
- **Light mode** — capture the AWS console in light mode so the figures match the Greengrass set.
- **Terminal** — dark or light is fine, but keep one style across `fig03` and `fig04`.
- **Redact before committing** — the 12-digit AWS account ID, any ARN containing it, access
  key IDs, public IP addresses and public DNS names, and the S3 bucket name if it is not a
  throwaway. Blur or solid-block them; do not rely on cropping alone.
- **Consistent example** — use `yolov5-s-face_640x640` throughout, as the document does.
