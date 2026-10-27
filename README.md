---
title: Azure ML CPU MLOps Demo
description: 합성 통신 데이터와 MLflow, Azure ML SDK v2, Hugging Face CPU 서빙 실습
ms.date: 2026-10-27
---

## 무엇을 시연하나요

> [!IMPORTANT]
> 현재 데모 Workspace는 `mlw-ktmlops-secure`입니다.
> Storage는 NSP `SecuredByPerimeter` 및 Enforced 규칙으로 보호하고,
> AML의 Storage/Key Vault 접근은 Managed Network의 Private Endpoint를 사용합니다.
> [실제 배포 상태와 검증 결과](docs/deployment-status.md)를 먼저 확인하세요.
> 교육 Agenda의 데이터·학습·등록·HF 서빙은 완료 이력을 확인했습니다.
> 학습한 churn 모델과 서빙하는 HF 모델은 별도 경로입니다.
> 동일 학습 모델의 자동 배포나 운영용 MLOps 전체 자동화가 완료된 구성은 아닙니다.

Azure Machine Learning Studio에서 데이터 버전, 실험 비교, MLflow 모델 패키지,
파이프라인 실행 이력, 실시간 CPU 서빙을 연결해서 확인하는 교육용 저장소입니다.
실제 고객 데이터, 고객 내부 설계 원문, 발표 자료, 자격 증명은 포함하지 않습니다.

| 교육 Agenda | 실행 결과 | Studio 메뉴 |
|---|---|---|
| MLOps Overview, DevOps와 차이 | 코드 + 데이터 + 환경 + 모델의 버전 연결 | [진행 가이드](docs/session-guide.md) |
| 데이터 등록·관리 | `telco-churn` 및 `telco-churn-table`, 각 v1/v2 | Data |
| MLflow 실험 추적 | 동일 holdout의 Logistic / Random Forest 비교 | Jobs, Experiments |
| 모델 패키징·등록 | Signature, input example, metrics, confusion matrix | Models, Jobs의 Outputs + logs |
| AML 파이프라인 | 데이터 준비 -> 학습 -> 모델 출력 | Jobs의 pipeline graph, Components |
| Custom 환경 이미지 빌드 | 학습·서빙 의존성을 이미지로 빌드하고 ACR에 저장 | Environments의 build log, Azure Portal의 ACR Repositories |
| 외부 학습 연계 | 로컬 CPU 학습을 AML MLflow에 기록 | Jobs의 `kt-external-mlflow` |
| HF 소형 CPU 모델 서빙 | 상담 문장 3개 intent 분류 | Models, Endpoints의 Test/Consume/Logs |

> [!IMPORTANT]
> `all-MiniLM-L6-v2`는 약 22.7M 파라미터의 영어 임베딩 모델입니다.
> 생성형 LLM이나 한국어 품질 검증 모델이 아닙니다.
> 영어 합성 상담 문장을 임베딩하고 프로토타입과 cosine similarity를 비교합니다.
> similarity는 보정된 확률이 아니며 실제 고객 업무 판단에 사용하지 않습니다.
> 한국어 3문장을 호출한 확인에서는 모두 `cancellation`으로 분류되었고,
> 신뢰도 임계값과 "기타" 범주가 없어 무관한 문장도 한 범주로 분류됩니다.

## 아키텍처

![Azure ML 아키텍처: Entra 인증, Managed Network, CPU 학습과 HF 서빙, 보호된 Storage 및 ACR 이미지 경로](docs/images/azure-architecture.svg)

[아키텍처 SVG 원본 크게 보기](docs/images/azure-architecture.svg)

실선은 제어·호출·이미지·관측 연결, 녹색 점선은 Private Endpoint 의존 경로입니다.
네트워크 subnet 배치도가 아닌 리소스 및 연결 개념도입니다.

기본 리전은 Korea Central입니다. 이 예제는 secure Workspace, public Studio/Endpoint ingress,
Entra 인증 및 Storage/Key Vault의 private dependency 경로를 사용하는 교육 환경입니다.
ACR은 public access Enabled이며 Private Endpoint는 없습니다.
이미지 push/pull은 인증과 RBAC으로 제한하며 ACR admin과 anonymous pull은 비활성화했습니다.
Managed Network는 `AllowInternetOutbound`이므로 완전한 인터넷 차단 환경이 아닙니다.
GPU, Slurm/Lustre, 과제별 다중 Workspace 격리와 운영 HA는 배포하지 않습니다.
외부 추적은 Slurm과 같은 위치 독립적인 MLflow 패턴을 PC에서 재현하며,
실제 Slurm 통합 검증을 대신하지 않습니다.

## MLOps Pipeline

![MLOps Pipeline: Data v1 기반 Prepare와 Train, MLflow 모델 등록, 외부 CPU 추적 및 별도 HF 서빙 경로](docs/images/mlops-pipeline.svg)

[Pipeline SVG 원본 크게 보기](docs/images/mlops-pipeline.svg)

* 클라우드 학습: 동일 Data v1 holdout으로 Logistic과 Random Forest를 비교합니다.
  AML Pipeline graph는 Prepare -> Train이며 모델 등록은 Job 완료 후 SDK에서 수행합니다.
* 외부 학습: Data v2로 PC에서 학습하고 같은 Workspace의 MLflow에 기록합니다.
  Data v1 실험과 평가 데이터가 달라 성능 순위를 직접 비교하지 않습니다.
* HF 서빙: 사전학습 MiniLM을 별도로 등록·배포합니다.
  churn 학습 출력의 자동 배포나 LLM fine-tuning 경로가 아닙니다.

## 실행 Workflow

![실행 Workflow: GitHub CI 검증과 운영자 수동 Azure 실행, 발표 당일 Studio 탐색 순서](docs/images/demo-workflow.svg)

[Workflow SVG 원본 크게 보기](docs/images/demo-workflow.svg)

GitHub Actions는 Ruff·pytest·Bicep build를 수행하며 클라우드 배포는 하지 않습니다.
운영자가 기반 리소스와 Managed Network를 준비한 뒤
`compute -> assets -> train -> external -> deploy -> verify`를 실행합니다.
`assets`는 Components 등록을 포함하며 `all`은 이 여섯 단계를 순서대로 호출합니다.
환경 이미지 빌드는 AML이 수행하고 ACR에 저장하므로 CI 이미지 빌드와 구분합니다.

발표에서는 준비된 Completed Job과 Endpoint를 먼저 사용하세요.
정확한 실행 명령은 아래 [시작하기](#시작하기),
탭별 진행은 [교육 진행 가이드](docs/session-guide.md),
실제 결과와 한계는 [배포 검증 결과](docs/deployment-status.md)에서 확인할 수 있습니다.
세 SVG는 외부 이미지·폰트·스크립트 없이 GitHub README에서 직접 표시됩니다.

## 시작하기

필수 도구: Python 3.11, [uv](https://docs.astral.sh/uv/), Azure CLI, Bicep,
리소스 생성·역할 부여 권한이 있는 Azure 계정.
아래 명령은 저장소 루트의 PowerShell에서 실행합니다.

```powershell
az login
az account set --subscription "<your-subscription-id>"
uv sync --locked --extra serving --python 3.11
uv run --no-sync pytest -q

az group create --name rg-kt-mlops --location koreacentral
$operatorId = az ad signed-in-user show --query id -o tsv
az bicep build --file infra\main.bicep
$operatorPrefix = "<your-public-egress-ipv4>/32"
az deployment group validate --resource-group rg-kt-mlops `
  --template-file infra\main.bicep `
  --parameters operatorPrincipalId=$operatorId operatorAddressPrefix=$operatorPrefix
az deployment group what-if --resource-group rg-kt-mlops `
  --template-file infra\main.bicep `
  --parameters operatorPrincipalId=$operatorId operatorAddressPrefix=$operatorPrefix
az deployment group create --name kt-mlops-foundation `
  --resource-group rg-kt-mlops --template-file infra\main.bicep `
  --parameters operatorPrincipalId=$operatorId operatorAddressPrefix=$operatorPrefix

New-Item -ItemType Directory -Force local | Out-Null
az deployment group show --resource-group rg-kt-mlops `
  --name kt-mlops-foundation --query properties.outputs.config.value -o json |
  Set-Content -Encoding utf8 local\config.json
$workspaceId = az resource show --resource-group rg-kt-mlops `
  --name mlw-ktmlops-secure --resource-type Microsoft.MachineLearningServices/workspaces `
  --query identity.principalId -o tsv
$scope = "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/rg-kt-mlops"
az role assignment create --assignee-object-id $workspaceId `
  --assignee-principal-type ServicePrincipal `
  --role "Azure AI Enterprise Network Connection Approver" --scope $scope
uv run --no-sync python -c "from demo.workspace import client,ROOT; m=client(ROOT/'local'/'config.json'); m.workspaces.begin_provision_network(workspace_name=m.workspace_name).result()"
uv run --no-sync python -m demo.manage all
```

Azure RBAC 변경은 전파에 수 분 걸릴 수 있습니다. 실패한 단계는 원인을 확인한 뒤
개별적으로 다시 실행합니다. 모든 실패는 예외와 종료 코드로 노출합니다.
완료된 단계와 run ID는 Git에서 제외된 `local/state.json`에,
실시간 검증 결과는 `local/verification.json`에 남습니다.

```powershell
uv run --no-sync python -m demo.manage compute
uv run --no-sync python -m demo.manage assets
uv run --no-sync python -m demo.manage components
uv run --no-sync python -m demo.manage train
uv run --no-sync python -m demo.manage external
uv run --no-sync python -m demo.manage deploy
uv run --no-sync python -m demo.manage verify
```

첫 실행은 이미지 빌드와 VM 할당 때문에 오래 걸립니다. 세션 전날 미리 실행하세요.
같은 이름/버전의 자산은 덮어쓰는 용도가 아닙니다. 코드·환경·데이터를 변경했다면
새 버전으로 등록하세요. `train` 재실행은 새 Job을 제출하므로 추가 비용이 발생합니다.

### 가벼운 학습 시나리오

1,500행의 합성 데이터에서 동일한 1,125행 train / 375행 holdout을 사용합니다.
CPU Logistic Regression과 깊이 6, 100개 트리의 작은 Random Forest를 비교합니다.
LLM continual fine-tuning은 실행하지 않습니다. 짧은 학습으로 Data → Prepare →
Train → MLflow package → Model registration을 설명하고, 별도 HF 모델로 CPU 서빙을 보여줍니다.
HF MiniLM은 학습한 churn 모델이 아니며 두 모델의 lineage를 혼동하지 않습니다.

발표에서는 준비된 Job과 Endpoint를 먼저 보여주세요. 학습 자체와 달리
최초 Conda 이미지 빌드, 네트워크 및 VM provisioning은 수 분 이상 걸릴 수 있습니다.

### ACR Custom 이미지 빌드

[학습 환경](environments/training.yml)과 [서빙 환경](environments/serving.yml)의
Conda/pip 의존성을 MCR 기본 이미지 위에 설치하도록 AML이 Dockerfile을 생성합니다.
`cpu-secure`에서 이미지 빌드를 수행하고 연결된 ACR
`crktmlopsaow7cshia2xmu.azurecr.io`에 push합니다.
학습 Job과 온라인 배포는 인증된 ACR public 경로로 각 환경의 이미지를 pull합니다.
기본 이미지만 참조한 것이 아니라 실제 의존성이 설치된 Custom 이미지가 저장되어 있습니다.

현재 학습은 `kt-sklearn-mlflow:2`, HF 서빙은 `kt-hf-cpu:1`을 사용합니다.
두 이미지의 Completed 빌드 Job과 불변 digest는
[실제 배포 상태](docs/deployment-status.md#acr-custom-이미지-빌드-검증)에 기록했습니다.
수동 Dockerfile이나 `az acr build`를 이용한 ACR Tasks 빌드가 아니라
AML이 관리하는 환경 이미지 빌드입니다. GitHub CI는 테스트·Bicep 검증을 수행하며
이미지 빌드·push를 자동 실행하지 않습니다.

### 전체 MLOps 완료 범위

기존 실행 이력, 현재 자산 조회, 실제 Endpoint 호출로 다음 두 경로를 확인했습니다.
이번 검토에서는 학습·이미지 빌드·배포·테스트를 다시 실행하지 않았습니다.

* 학습 경로: Data v1/v2 등록 -> Prepare/Train Pipeline -> MLflow 추적·패키징 ->
  Job 완료 후 SDK로 churn 모델 v1/v2 등록
* 서빙 경로: 사전학습 HF MiniLM 고정 revision -> 별도 custom model 등록 ->
  ACR 환경 이미지 -> CPU Endpoint 배포 -> 인증·추론 호출 검증

`all`은 CLI에서 각 단계를 순서대로 호출하는 편의 명령입니다.
AML Pipeline graph 자체는 Prepare -> Train이며,
등록한 churn 모델의 배포 단계까지 연결된 단일 그래프가 아닙니다.
자동 최적 모델 선택·품질 기준 승인·승격/롤백·드리프트 기반 재학습·클라우드 CD는
구현하지 않았습니다. Studio 로그인 후 탭별 시각적 검증도 남아 있습니다.
[완료 판정과 한계](docs/deployment-status.md#전체-mlops-파이프라인-검토-결론)를 확인하세요.

### 패키지 다운로드 환경

작업 PC에서 PyPI 파일 호스트 TLS 연결이 실패하여 public PyPI mirror를 사용했습니다.
TLS 인증서 검증은 유지합니다. PyTorch는 공식 CPU wheel index만 사용합니다.
`uv.lock`은 버전과 해시를 고정합니다.
일반 네트워크에서 공식 PyPI를 쓰려면 `pyproject.toml`의 `pypi-mirror` index를 제거하고
`uv lock`을 다시 실행한 뒤 변경된 lockfile을 검토하세요.
클라우드 환경의 pip 설치는 공식 PyPI와 공식 PyTorch CPU index를 사용합니다.

## 기능·SDK 기준

* Azure ML SDK v2의 `azure-ai-ml`, `Input/Output`, `command`, `dsl.pipeline` 사용
* 데이터는 v1 Dataset API 대신 v2 Data asset 및 MLTable 사용
* ACI/AKS v1 배포 대신 Managed Online Endpoint 사용
* 호환성 기준으로 MLflow 2.22.2 고정, MLflow 3 전용 API는 사용하지 않음
* MLflow registry stage에 의존하지 않고 명시적인 AML 모델 버전 사용
* HF commit SHA 고정, safetensors 사용, remote code 실행 금지
* 추론 시 HF 네트워크 접근 없이 Workspace에 등록한 모델 사용

최신 기능은 리전·구독·포털 업데이트에 따라 달라집니다.
모든 Azure ML 기능을 구성하는 예제는 아닙니다.
AutoML, Designer의 시각적 편집, Responsible AI, Drift monitor, Batch Endpoint는
이번 Agenda 밖이며 빈 화면을 채우기 위해 가짜 자산을 만들지 않습니다.

## 비용과 종료

2026-10-26 Retail Prices API에서 Korea Central Linux DS2_v2는
US$0.165/시간으로 확인했습니다. 24시간 약 US$3.96이며 ACR Basic,
Storage와 로그 비용은 별도입니다. 현재 구성은 ACR Premium, Private Endpoint,
Managed Network를 추가 사용하므로 이전 Basic 기준 일일 비용 추정은 적용하지 않습니다.
사용량·요율·세금·환율에 따라 달라집니다.

* 학습 DS3_v2 클러스터: min=0, max=2, 유휴 120초 후 축소
* 실시간 서빙 DS2_v2 1대: 요청이 없어도 계속 과금
* Log Analytics: 30일 보존, 일일 1GB soft cap (강제 예산 한도 아님)
* GPU 및 상시 Compute Instance 없음

서빙 비용만 중지하려면 인증된 Azure ML Studio에서 `kt-hf-cpu-secure` endpoint를 삭제하세요.
코드·데이터·모델·Job 이력은 Workspace에 남습니다. 필요 시 `deploy` 단계로 재생성합니다.
전체 삭제는 아래 명령의 대상 RG를 확인하고 명시적으로 실행합니다.

```powershell
# 이 RG의 데모 자산과 실행 이력을 모두 삭제합니다.
az group delete --name rg-kt-mlops --yes --no-wait
```

Key Vault purge protection 때문에 삭제 후에도 보존 기간 동안 이름 재사용이 제한됩니다.
이 저장소의 자동 실행은 리소스를 삭제하지 않습니다.

## 문서

* [교육 진행 가이드와 Studio 탭 순서](docs/session-guide.md)
* [현재 기능에 대한 공식 근거](docs/research.md)
* [실행 검증 결과와 전체 MLOps 완료 범위](docs/deployment-status.md)
