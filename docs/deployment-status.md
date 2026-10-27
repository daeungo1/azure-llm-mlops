---
title: 실제 Azure 배포 상태
description: 정책 준수 네트워크 구성과 실제 클라우드 학습·모델·추론 검증 결과
ms.date: 2026-10-27
---

## 배포 완료

Korea Central의 `rg-kt-mlops`에 다음 리소스를 실제 생성했습니다.
ARM 배포 `kt-mlops-private-egress`와 Managed Network provisioning이 성공했습니다.

| 리소스 | 이름 |
|---|---|
| Azure ML Workspace | mlw-ktmlops-secure |
| Storage Account | stktmlopsaow7cshia2xmu |
| Azure Container Registry | crktmlopsaow7cshia2xmu |
| Key Vault | kv-ktmlops-aow7cshia2 |
| Application Insights | appi-ktmlops |
| Log Analytics Workspace | log-ktmlops |
| AML CPU cluster | cpu-secure |
| Network Security Perimeter | nsp-ktmlops |
| Managed Online Endpoint | kt-hf-cpu-secure |

CPU cluster는 DS3_v2, min=0, max=2로 생성하고
클러스터 identity에 Storage Blob Data Contributor를 부여했습니다.
Workspace가 identity 기반 datastore의 Blob/File 역할을 자동 생성하므로
동일 Blob 역할을 Bicep에서 중복 생성하지 않습니다.

## 정책을 충족하는 네트워크

관리 그룹의 `MCAPSGovDeployPolicies` 정책 집합에 포함된
`StorageAccount_PublicNetwork_Modify`가 Storage의
일반적인 unrestricted public 접근을 차단합니다.
정책이 지원하는 `SecuredByPerimeter`와 Enforced NSP를 사용했습니다.
운영자 egress IPv4 /32 및 구독의 인증된 identity 규칙으로 로컬 업로드를 제한하고,
공유 키와 익명 Blob 접근은 비활성화했습니다.

NSP만으로는 AML 이미지 빌드의 SAS 코드 다운로드가 차단되었습니다.
이를 해결하기 위해 새 Workspace에 `AllowInternetOutbound` Managed Network를
구성하고 Storage Blob/File, Key Vault, Premium ACR의 Private Endpoint를 사용합니다.
기존 compute가 있는 Workspace는 Managed Network 전환이 거부되므로
기존 리소스를 삭제하지 않고 `-secure` Workspace를 생성했습니다.
정책은 삭제·해제·예외 처리하지 않았습니다. Studio와 Endpoint ingress만 public입니다.

## 클라우드 E2E 검증 완료

2026-10-27 02:40 UTC에 `python -m demo.manage verify`가 성공했습니다.

| 검증 항목 | 실제 결과 |
|---|---|
| Data | telco-churn, telco-churn-table 각각 v1/v2 |
| 학습 환경 / Components | kt-sklearn-mlflow v2, prepare/train v2 |
| Logistic Pipeline | willing_squash_k6mh2f3234, Completed |
| Random Forest Pipeline | clever_ice_n93v3hjtt8, Completed |
| 학습 모델 | telco-churn-classifier v1/v2, MLflow 패키지 |
| 외부 CPU MLflow | e8b5a9c3-1161-42cb-8120-e287d8d4f9ff, telco-churn-external v1 |
| HF 모델 | hf-minilm-ticket-router v1, pinned MiniLM |
| Online Endpoint / blue | Succeeded, Entra aad_token, traffic 100% |
| 실제 추론 | billing / network / cancellation, HTTP 200 |
| 3회 왕복 지연 | 1.795 / 1.618 / 0.650초 |
| 무인증 요청 | HTTP 401 |
| 빈 texts | 외부 HTTP 424, model-error-statuscode 400 |

학습 run의 MLflow start/end 기준 소요 시간은 Logistic 약 34.4초,
Random Forest 약 115.6초였습니다. 이미지 빌드·Prepare·VM 대기 시간은 포함하지 않습니다.
동일 holdout의 accuracy / ROC AUC는 각각 Logistic 0.7333 / 0.7878,
Random Forest 0.7307 / 0.7845입니다. 버전 2가 더 우수하다고 주장하지 않습니다.

MLflow adapter 1.61.0은 MLflow 2.22.2의 artifact API와 충돌했습니다.
로컬에서 검증한 `azureml-mlflow==1.62.0.post6`으로 환경 v2를 만들어
실제 클라우드 학습·artifact·모델 등록을 성공시켰습니다.
실패 이력은 숨기지 않았으며 발표에는 위 Completed Job을 사용하세요.

## 발표 및 재실행

소규모 합성 데이터 1,500행으로 CPU 학습을 수행합니다.
두 모델은 동일한 1,125행 train / 375행 holdout을 사용합니다.
HF MiniLM은 별도 사전학습 임베딩 모델이며 continual fine-tuning은 하지 않았습니다.
훈련한 churn 모델을 HF 모델이라고 설명하면 안 됩니다.

기존 자산을 확인하고 Endpoint를 호출하는 검증은 다음과 같습니다.

```powershell
uv run --no-sync python -m demo.manage verify
```

실제 요청 결과는 Git에서 제외된 `local/verification.json`에 남았습니다.
환경·코드만 갱신하려면 `components`를 사용하고 버전을 증가시키세요.
기존 Data/Model 버전은 immutable이므로 `assets`나 전체 `all`을 기존 환경에서
반복 실행하여 덮어쓰지 마세요. 새 학습은 `train`으로 제출할 수 있으나
그 결과를 등록하려면 코드에서 모델 버전도 새 버전으로 올려야 합니다.
최초 이미지 빌드와 VM 할당은 학습 시간과 별개이며 사전 실행해야 합니다.

브라우저에서 Studio를 열었지만 로그인 화면으로 이동하여
로그인 후 탭별 시각적 검증은 수행하지 못했습니다.
자산 목록·Job 상태·모델 버전·Endpoint 호출은 인증된 SDK/API로 검증했습니다.
실제 발표자는 동일 Workspace에 로그인해서 탭을 확인해야 합니다.

기존 `mlw-ktmlops`, 실패한 이전 Endpoint와 Job 이력은 삭제하지 않았습니다.
새 Endpoint DS2_v2 1대, ACR Premium, Private Endpoint와 로그는 계속 과금됩니다.
학습 클러스터는 min=0입니다.

## 로컬 검증 결과

`HF_MODEL_DIR`를 다운로드한 고정 revision의 실제 모델 경로로 설정하고
`uv run --no-sync pytest -q`로 실제 CPU 모델 포함 24개 테스트가 통과했습니다.
실제 CPU 모델의 세 문장 intent 결과도 검증했습니다.
Ruff lint와 format 검사를 통과했습니다.
MLflow 및 관련 라이브러리의 deprecation 경고는 남아 있습니다.
이 결과는 로컬 검증이며 Azure Endpoint 검증을 대신하지 않습니다.
