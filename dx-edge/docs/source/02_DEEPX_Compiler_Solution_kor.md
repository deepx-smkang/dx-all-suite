# DEEPX Compiler Solution

**AWS에서 ONNX 모델을 DEEPX NPU 실행 형식(DXNN)으로 컴파일하기**

DEEPX NPU는 표준 ONNX 모델을 그대로 실행하지 않습니다. NPU가 실행할 수 있는 명령 집합과 가중치를 담은 DXNN(`.dxnn`) 형식으로 먼저 변환해야 하며, 이 변환을 담당하는 것이 DEEPX 컴파일러 `dxcom`입니다. 컴파일 과정에는 INT8 양자화를 위한 캘리브레이션이 포함되므로 대표 데이터셋과 충분한 CPU·메모리 자원이 필요합니다.

이 문서에서는 **DEEPX Compiler Solution**을 사용해 이 컴파일 단계를 AWS에서 수행하는 방법을 설명합니다. 로컬에 컴파일 환경을 구축하지 않고, AWS Marketplace에서 제공하는 DX-Compiler AMI로 필요할 때만 인스턴스를 띄워 컴파일하는 방식입니다.

!!! note "이 문서의 범위"
    이 문서는 **모델 컴파일만** 다룹니다. 컴파일된 DXNN 모델을 엣지 디바이스에 배포하고 NPU 드라이버·펌웨어·런타임까지 자동으로 설치하려면 [DEEPX Greengrass Solution](01_DEEPX_Greengrass_Solution_kor.md)을 참고하십시오. Greengrass Solution은 이 문서에서 설명하는 컴파일 파이프라인을 포함합니다.

---

## 1. 두 가지 사용 경로

DEEPX Compiler Solution은 사용 방식에 따라 두 가지 경로를 제공합니다. 목적에 맞는 쪽을 선택하면 됩니다.

| | **Path A — DX-Compiler AMI 직접 사용** | **Path B — 이벤트 기반 컴파일 파이프라인** |
| :--- | :--- | :--- |
| 제공 형태 | AMI (Amazon Machine Image) | CloudFormation 스택 |
| 실행 방식 | EC2 인스턴스를 직접 기동하고 `dxcom` 실행 | S3에 파일 업로드 → 자동 컴파일 |
| 적합한 상황 | 컴파일 옵션을 반복적으로 바꿔가며 실험, 대화형 디버깅 | 정형화된 컴파일을 반복 수행, CI/자동화 연계 |
| 인스턴스 수명 | 사용자가 직접 기동·종료 | 워크플로가 자동 기동·종료 |
| Marketplace | [DX-Compiler (AMI)](https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo) | [DEEPX Greengrass Solution](https://aws.amazon.com/marketplace/pp/prodview-732s46qfzuh34)에 포함 |

두 경로 모두 동일한 `dxcom` 컴파일러와 동일한 캘리브레이션 데이터셋을 사용하므로 컴파일 결과는 같습니다.

---

## 2. 사전 준비 사항

- EC2 인스턴스를 기동하거나 CloudFormation 스택을 생성할 수 있는 AWS 계정과 권한
- 컴파일할 ONNX 모델과 컴파일 설정 JSON 파일. 직접 학습한 모델 외에도 [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/)에서 DEEPX NPU용으로 검증된 사전 학습 모델을 내려받아 바로 사용할 수 있습니다.
- 인스턴스를 실행할 기존 VPC와 서브넷. 서브넷은 Amazon S3, AWS Systems Manager, Amazon CloudWatch Logs 등 필요한 AWS 서비스에 HTTPS로 연결할 수 있어야 합니다. 프라이빗 서브넷을 사용한다면 NAT Gateway 또는 필요한 VPC 엔드포인트를 구성합니다.
- 로컬에서 AWS CLI 명령을 실행하려면 자격 증명이 설정되어 있어야 합니다.

### 로컬 AWS CLI 설정

이미 설정되어 있다면 이 절은 건너뜁니다.

```bash
aws configure
# AWS Access Key ID [None]: <access-key-id>
# AWS Secret Access Key [None]: <secret-access-key>
# Default region name [None]: <region, 예: us-east-1>
# Default output format [None]: json

# 자격 증명이 올바르게 설정되었는지 확인
aws sts get-caller-identity
```

계정 ID와 사용자 ARN이 출력되면 설정이 완료된 것입니다.

---

## 3. Path A — DX-Compiler AMI 직접 사용

AWS Marketplace의 [DX-Compiler (AMI)](https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo)는 DEEPX 모델 컴파일러 `dxcom`과 캘리브레이션 데이터셋이 미리 설치된 Amazon Machine Image입니다. 별도 설치 과정 없이 인스턴스를 기동하는 즉시 컴파일을 시작할 수 있습니다.

### 단계 1. 구독 및 인스턴스 기동

1. Marketplace 제품 페이지에서 **Continue to Subscribe**를 선택해 구독합니다. 소프트웨어 구독 비용은 없으며, 사용한 AWS 리소스 비용만 발생합니다.
2. **Continue to Configuration**에서 배포할 Region과 AMI 버전을 선택합니다.
3. **Continue to Launch**에서 인스턴스 유형, VPC/서브넷, 보안 그룹, 키 페어를 지정하고 인스턴스를 기동합니다.

!!! note "인스턴스 유형 선택"
    컴파일은 CPU와 메모리를 많이 사용하는 작업입니다. DEEPX Greengrass Solution의 컴파일 파이프라인은 기본값으로 `t3.xlarge`를 사용합니다. 모델 크기와 캘리브레이션 이미지 수에 따라 더 큰 인스턴스가 유리할 수 있습니다.

보안 그룹은 필요한 아웃바운드 통신만 허용하도록 구성합니다. 컴파일 자체는 인바운드 접속을 요구하지 않으며, 대화형 작업이 필요하다면 SSH 대신 AWS Systems Manager Session Manager를 사용해 인바운드 포트를 열지 않는 구성을 권장합니다.

### 단계 2. 모델과 설정 파일 준비

인스턴스에 접속한 뒤 컴파일할 ONNX 모델과 JSON 설정 파일을 준비합니다.

```bash
# Model Zoo 예제 모델 내려받기
curl -fLO https://sdk.deepx.ai/modelzoo/onnx/yolov5-s-face_640x640.onnx

# 또는 S3에 올려둔 자체 모델 가져오기
aws s3 cp s3://<your-bucket>/<path>/model.onnx .
```

### 단계 3. 컴파일 실행

`dxcom`은 모델(`-m`), 설정 파일(`-c`), 출력 경로(`-o`)를 인자로 받습니다.

```bash
dxcom -m yolov5-s-face_640x640.onnx \
      -c yolov5-s-face_640x640.json \
      -o output/yolov5-s-face_640x640
```

컴파일이 완료되면 지정한 출력 경로에 `.dxnn` 파일이 생성됩니다. 결과물을 S3에 업로드해 두면 엣지 디바이스나 다른 작업 환경에서 내려받아 사용할 수 있습니다.

```bash
aws s3 cp output/yolov5-s-face_640x640.dxnn s3://<your-bucket>/<path>/
```

### 단계 4. 인스턴스 종료

컴파일은 일회성 작업이므로, 작업이 끝나면 인스턴스를 종료해 비용 발생을 멈춥니다. 반복 작업이 예상된다면 이어지는 Path B의 자동화된 파이프라인을 사용하는 편이 관리와 비용 양쪽에서 유리합니다.

---

## 4. Path B — 이벤트 기반 컴파일 파이프라인

Path B는 컴파일러 인스턴스를 사람이 직접 다루지 않는 방식입니다. Amazon S3에 모델과 설정 파일을 업로드하면 이벤트가 워크플로를 시작하고, 워크플로가 DX-Compiler AMI 기반 인스턴스를 기동해 컴파일한 뒤 인스턴스를 종료합니다. 사용자는 결과물만 내려받으면 됩니다.

이 파이프라인은 DEEPX Greengrass Solution CloudFormation 스택에 포함되어 있습니다. 스택 배포 절차와 파라미터는 [DEEPX Greengrass Solution](01_DEEPX_Greengrass_Solution_kor.md) 문서를 참고하십시오.

### 동작 순서

1. 사용자가 `.onnx` 모델과 `.json` 설정 파일을 S3 모델 버킷의 **같은 경로**에 업로드합니다.
2. S3 `ObjectCreated` 이벤트가 AWS Lambda 트리거 함수를 호출합니다. 함수는 같은 경로에서 짝이 되는 파일을 찾아 **두 파일이 모두 존재할 때만** 다음 단계로 진행합니다. 실행 이름은 파일명 기반 해시로 생성해 중복 실행을 방지합니다.
3. AWS Step Functions 컴파일 워크플로가 시작됩니다.
4. 워크플로가 DX-Compiler AMI 기반 Amazon EC2 인스턴스를 기동합니다. 인스턴스는 CloudFormation 파라미터로 지정한 기존 VPC/서브넷에서 실행됩니다.
5. AWS Systems Manager Run Command가 SSM Document에 정의된 컴파일 명령을 인스턴스에 전달합니다.
6. 인스턴스에 사전 설치된 `dxcom` 컴파일러가 실행됩니다. 이때 설정 파일의 `dataset_path`는 AMI에 포함된 캘리브레이션 데이터셋 경로인 `/opt/dx-compiler/calibration_dataset`으로 자동 치환됩니다.
7. 컴파일된 `.dxnn` 바이너리가 원본 모델과 같은 S3 경로에 업로드됩니다. 워크플로는 성공·실패와 무관하게 인스턴스를 종료하므로 유휴 비용이 발생하지 않으며, 실행 로그는 Amazon CloudWatch Logs 로그 그룹(`/dx-compiler/<스택명>/execution`)에서 확인할 수 있습니다.

### 사용 예

```bash
export STACK_NAME=<cloudformation-stack-name>

export MODEL_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ModelBucketName'].OutputValue" \
  --output text)

export MODEL_PREFIX=models/yolov5-s-face_640x640

aws s3 cp --only-show-errors yolov5-s-face_640x640.onnx "s3://${MODEL_BUCKET}/${MODEL_PREFIX}/"
aws s3 cp --only-show-errors yolov5-s-face_640x640.json  "s3://${MODEL_BUCKET}/${MODEL_PREFIX}/"

# 컴파일 완료 후 결과 확인
aws s3 ls "s3://${MODEL_BUCKET}/${MODEL_PREFIX}/"
```

!!! note "모델별 전용 prefix 사용"
    트리거 함수는 같은 경로에 있는 `.onnx`와 `.json`을 한 쌍으로 인식합니다. 여러 모델을 다룰 때는 모델마다 별도 prefix를 사용해 다른 모델의 설정 파일이 섞이지 않도록 합니다.

---

## 5. 컴파일 설정 파일 (JSON)

컴파일 설정 파일은 입력 텐서의 형상과 INT8 양자화를 위한 캘리브레이션 방식을 정의합니다. 아래는 640×640 입력을 받는 검출 모델의 예시입니다.

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

| 항목 | 설명 |
| :--- | :--- |
| `inputs` | 입력 텐서 이름과 형상. ONNX 모델의 입력 정의와 일치해야 합니다. |
| `calibration_num` | 캘리브레이션에 사용할 이미지 수 |
| `calibration_method` | 캘리브레이션 알고리즘 (예: `ema`) |
| `default_loader.dataset_path` | 캘리브레이션 데이터셋 경로 |
| `default_loader.preprocessings` | 학습 시 사용한 전처리와 동일하게 구성해야 정확도 손실을 최소화할 수 있습니다. |

!!! note "`dataset_path` 자동 치환"
    Path B의 파이프라인을 사용하는 경우, 설정 파일의 `dataset_path`에 어떤 값을 넣더라도 컴파일 시점에 AMI에 포함된 캘리브레이션 데이터셋 경로(`/opt/dx-compiler/calibration_dataset`)로 자동 치환됩니다. Path A에서 직접 `dxcom`을 실행할 때는 이 치환이 적용되지 않으므로, 인스턴스에서 실제로 접근 가능한 경로를 지정해야 합니다.

---

## 6. DEEPX Model Zoo 연계

직접 학습한 모델이 없더라도 [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/)에서 DEEPX NPU용으로 검증된 사전 학습 ONNX 모델과 그에 대응하는 설정 파일을 내려받아 즉시 컴파일할 수 있습니다. 객체 검출, 얼굴 검출, 분류, 세그멘테이션, 포즈 추정 등 주요 비전 태스크의 모델이 제공되며, INT8 양자화 후 정확도 수치도 함께 공개되어 있습니다.

---

## 7. 비용

DEEPX Compiler Solution의 소프트웨어 구독 비용은 없습니다. 다만 다음 AWS 리소스 사용량에 따라 비용이 발생합니다.

- **Amazon EC2**: 컴파일러 인스턴스 실행 시간에 대해 비용이 발생합니다. Path B의 파이프라인은 컴파일 작업 중에만 인스턴스를 실행하고 성공·실패 양쪽 경로에서 종료하므로 유휴 비용이 없습니다. Path A에서는 사용자가 인스턴스를 직접 종료해야 합니다.
- **Amazon EBS**: 인스턴스에 연결된 볼륨에 대해 비용이 발생합니다.
- **Amazon S3, AWS Lambda, AWS Step Functions, Amazon CloudWatch Logs** (Path B): 모델 파일 저장, 이벤트 처리, 워크플로 실행, 로그 보관에 따른 비용이 발생합니다.

실제 비용은 모델 크기, 컴파일 시간, 인스턴스 유형, 리전, 로그 보관 기간에 따라 달라집니다. 배포 전에는 [AWS Pricing Calculator](https://calculator.aws/)와 각 서비스의 최신 요금을 기준으로 예상 비용을 확인합니다.

---

## 8. 문제 해결

| 증상 | 확인 사항 |
| :--- | :--- |
| 파일을 업로드했는데 워크플로가 시작되지 않음 (Path B) | `.onnx`와 `.json` 두 파일이 **같은 S3 경로**에 모두 업로드되었는지 확인합니다. 한쪽만 있으면 트리거 함수가 대기합니다. |
| 워크플로가 실패로 종료됨 | Amazon CloudWatch Logs의 `/dx-compiler/<스택명>/execution` 로그 그룹에서 `dxcom` 실행 로그를 확인합니다. |
| 인스턴스가 기동되지 않음 | 서브넷이 필요한 AWS 서비스에 HTTPS로 나갈 수 있는지(NAT Gateway 또는 VPC 엔드포인트), 그리고 Marketplace 구독이 완료되었는지 확인합니다. |
| 입력 형상 관련 컴파일 오류 | 설정 파일의 `inputs` 텐서 이름과 형상이 ONNX 모델의 입력 정의와 일치하는지 확인합니다. |
| 양자화 후 정확도가 기대보다 낮음 | `preprocessings`가 학습 시 전처리와 동일한지, `calibration_num`이 충분한지 확인합니다. |

## 9. 리소스 정리

1. **Path A**: 사용을 마친 EC2 인스턴스를 종료합니다. 인스턴스와 함께 삭제되지 않는 EBS 볼륨이 있다면 별도로 삭제합니다.
2. **Path B**: CloudFormation 콘솔에서 스택을 삭제합니다. 모델 버킷은 데이터 보호를 위해 유지되므로, 더 이상 필요하지 않다면 버킷을 비우고 직접 삭제합니다.
3. AWS Marketplace 구독이 더 이상 필요 없다면 [Manage subscriptions](https://aws.amazon.com/marketplace/library)에서 구독을 취소합니다.

## 다음 단계

컴파일한 `.dxnn` 모델을 엣지 디바이스에서 실행하려면 디바이스에 NPU 드라이버, 펌웨어, dx_rt 런타임이 설치되어 있어야 합니다. 이 과정을 AWS IoT Greengrass로 자동화하는 방법은 [DEEPX Greengrass Solution](01_DEEPX_Greengrass_Solution_kor.md) 문서를 참고하십시오.

## 참고 자료

- [DX-Compiler (AMI) — AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-ev6ed5omu4ulo)
- [DEEPX Greengrass Solution — AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-732s46qfzuh34)
- [DEEPX Model Zoo](https://developer.deepx.ai/modelzoo/)
- [DEEPX 개발자 문서](https://developer.deepx.ai)
- [Amazon EC2 사용 설명서](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html)
- [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [AWS Step Functions 개발자 안내서](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [DEEPX dx-all-suite — GitHub](https://github.com/DEEPX-AI/dx-all-suite)
