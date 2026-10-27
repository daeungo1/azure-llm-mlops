---
title: 실제 Azure 배포 상태
description: 교육 MLOps 완료 범위, 실제 ACR 이미지, 네트워크 설정 및 Endpoint 호출 검증 결과
ms.date: 2026-10-27
---

## 전체 MLOps 파이프라인 검토 결론

요청한 교육 Agenda의 Data/Model 관리, CPU 학습, MLflow 추적,
HF CPU Endpoint 생성·추론은 완료 이력을 확인했습니다.
다만 동일한 학습 모델을 등록한 뒤 서빙하는 단일 연속 파이프라인이나
운영용 MLOps 전체 자동화가 완료된 것은 아닙니다.

이번 검토는 코드·실행 로그·저장된 검증 기록, 현재 Azure 자산·Job 상태 조회,
실제 Endpoint 호출을 대상으로 했습니다.
Endpoint는 `verify`와 [추가 호출 테스트](#추가-호출-테스트)로 호출했으며
가장 최근 `verify`는 2026-10-27 09:49 UTC에 실행했습니다.
학습·이미지 빌드·배포·pytest는 새로 실행하지 않았으며,
Azure 리소스나 실행 코드는 변경하지 않았습니다.
포털 시각적 검증이나 운영 품질 인증을 대체하는 판정은 아닙니다.

| 단계 | 판정 | 증적과 실제 범위 |
|---|---|---|
| 인프라·Storage 정책 대응 | 완료 이력 및 현재 설정 확인 | Storage SecuredByPerimeter, NSP Enforced, Managed Network Active |
| Data 등록·버전 관리 | 완료 | telco-churn / telco-churn-table 각각 v1/v2 |
| 환경·Component 등록 | 완료 | kt-sklearn-mlflow:2, prepare/train:2 |
| 데이터 준비·CPU 학습 | 완료 | Logistic / Forest Pipeline 두 개 모두 Completed |
| MLflow 실험·패키징 | 완료 이력 확인 | 지표, confusion matrix, signature, input example, MLflow model |
| 학습 모델 등록 | 완료 | telco-churn-classifier v1/v2, Job 완료 후 SDK 등록 |
| 외부 학습 추적 | 완료 | 기존 외부 run FINISHED, telco-churn-external v1 |
| Custom 환경 이미지 | 완료 | 현재 학습·HF 서빙 이미지의 Completed 빌드 Job과 ACR digest 대조 |
| HF 모델 등록·CPU 배포 | 완료 | hf-minilm-ticket-router:1, Endpoint/blue Succeeded, traffic 100% |
| 인증·실제 추론·오류 응답 | 재호출 검증 완료 | 09:49 UTC `verify`에서 HTTP 200 및 의도 분류, 무인증 401, 잘못된 입력 424 |
| 입력 언어·범주 한계 | 한계 확인 | 한국어 3문장이 모두 cancellation(2건 오분류), 범주와 무관한 문장도 한 범주로 분류 |
| 모니터링 연결 | 호출 흔적 확인 | Endpoint 지표와 Application Insights에 요청 기록, 경보·SLO 검증 아님 |
| GitHub CI | 기존 성공 이력 확인 | commit c3a81e9의 CI 성공, 학습·배포 자동화가 아닌 코드 검증 |
| Studio 탭별 시각 검증 | 미검증 | 브라우저가 Microsoft 로그인 화면에 머물러 인증 후 화면 검증 필요 |

### 단일 학습 모델의 E2E와 구분

[학습 코드](../demo/pipeline.py)의 AML Pipeline graph는 Prepare -> Train입니다.
두 Job의 완료를 기다린 뒤 SDK가 churn 모델 v1/v2를 등록합니다.
[서빙 코드](../demo/endpoint.py)는 학습된 churn 모델이 아니라
별도의 사전학습 HF MiniLM을 등록하고 배포합니다.
`all`은 이들을 순차 호출하는 CLI이며 모델 승격을 자동화하는 CD 파이프라인은 아닙니다.

다음 항목은 미구현이거나 이번 교육 범위에 포함하지 않았습니다.

* 학습한 churn 모델의 Endpoint 배포 및 동일 모델 lineage의 학습 -> 등록 -> 서빙 연결
* 품질 임계값에 따른 자동 최적 모델 선택, 승인, 승격, canary 및 자동 롤백
* 데이터·모델 드리프트 감지, 재학습 trigger와 스케줄
* GitHub OIDC 기반 Azure 학습·이미지 빌드·배포 CD
* HF 모델 continual fine-tuning, 생성형 LLM 및 한국어 품질 검증
* 운영 경보·SLO, 부하/장애·복구 테스트, 다중 인스턴스 HA

위 항목까지 포함해 "운영용 전체 MLOps 완료"라고 설명하지 않습니다.
현재 완료 판정은 교육 Agenda의 두 별도 학습·서빙 경로를 기준으로 합니다.

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
구성하고 Storage Blob/File과 Key Vault의 Active Private Endpoint 규칙을 사용합니다.
기존 compute가 있는 Workspace는 Managed Network 전환이 거부되므로
기존 리소스를 삭제하지 않고 `-secure` Workspace를 생성했습니다.
정책은 삭제·해제·예외 처리하지 않았습니다.

현재 조회 결과 ACR Premium은 public access Enabled, admin/anonymous pull Disabled이며
Private Endpoint connection은 없습니다. 이미지 push/pull은 인증 기반 public 경로입니다.
Studio와 Endpoint ingress도 public이며 Key Vault의 실제 public access는 Disabled입니다.
ACR까지 Private Endpoint로 연결되었다는 이전 설명은 실제 상태에 맞춰 정정했습니다.
`AllowInternetOutbound`는 일반 인터넷 egress를 허용하므로 완전한 private-only 환경은 아닙니다.

[Bicep 템플릿](../infra/main.bicep)은 Key Vault public access를 Enabled로 선언하지만
실제 배포 상태는 Disabled입니다. 템플릿과 실제 유효 설정을 동일하다고 가정하지 말고
재배포 전에 정책 적용 결과와 목표 설정을 확인해야 합니다.
이번 검토에서는 인프라 코드를 수정하거나 재배포하지 않았습니다.

## 클라우드 E2E 및 Endpoint 호출 검증

`python -m demo.manage verify`는 Pipeline·자산·Endpoint 상태를 확인한 뒤
Endpoint를 실제로 호출합니다. 초기 기록은 2026-10-27 02:40 UTC이고,
현재 `local/verification.json`에는 같은 날 09:49 UTC에 다시 실행한 결과가 남아 있습니다.

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
| 임베딩 차원 | 384 |
| 상위 cosine similarity | 0.792 / 0.736 / 0.740 |
| 3회 왕복 지연(09:49 UTC) | 0.893 / 0.685 / 0.748초 |
| 무인증 요청 | HTTP 401 |
| 빈 texts | 외부 HTTP 424, model-error-statuscode 400 |

이전 실행의 3회 왕복 지연은 02:40 UTC에 1.795 / 1.618 / 0.650초,
09:25 UTC에 2.369 / 2.317 / 1.486초였습니다.
직렬 호출 3회의 클라이언트 왕복 시간이며 편차가 있으므로 성능 SLO로 사용하지 않습니다.

학습 run의 MLflow start/end 기준 소요 시간은 Logistic 약 34.4초,
Random Forest 약 115.6초였습니다. 이미지 빌드·Prepare·VM 대기 시간은 포함하지 않습니다.
동일 holdout의 accuracy / ROC AUC는 각각 Logistic 0.7333 / 0.7878,
Random Forest 0.7307 / 0.7845입니다. 버전 2가 더 우수하다고 주장하지 않습니다.

MLflow adapter 1.61.0은 MLflow 2.22.2의 artifact API와 충돌했습니다.
로컬에서 검증한 `azureml-mlflow==1.62.0.post6`으로 환경 v2를 만들어
실제 클라우드 학습·artifact·모델 등록을 성공시켰습니다.
실패 이력은 숨기지 않았으며 발표에는 위 Completed Job을 사용하세요.

### 추가 호출 테스트

`verify`의 고정 샘플 외에 같은 Entra token으로 별도 요청을 보냈습니다.
요청과 응답 원문은 Git에 저장하지 않았으며 아래 표는 요약입니다.

| 요청 | 결과 |
|---|---|
| 샘플에 없는 영문 4문장 | HTTP 200, billing / network / cancellation / billing, 약 1.2초 |
| 동일 영문 문장 16개 | HTTP 200, 16개 예측 반환 |
| 2,000자 문자열 | HTTP 200 |
| 한국어 3문장(청구, 인터넷 장애, 해지) | HTTP 200, 3개 모두 cancellation, top similarity 0.075~0.083 |
| 범주와 무관한 영문 1문장 | HTTP 200, billing, top similarity 0.040 |
| 빈 배열, 공백 문장, 17개 문장, 2,001자, 문자열 texts, 숫자 항목, 추가 필드, JSON이 아닌 본문 | 외부 HTTP 424, model-error-statuscode 400 |
| 토큰 없음 | HTTP 401, `Jwt is missing` |

이 테스트는 동작 확인용 smoke test이며 정확도 평가가 아닙니다.
영문 4문장의 기대 label은 테스트 작성자가 정했고 표본도 작습니다.
이 문장들의 top similarity는 0.34~0.56으로 샘플 문장의 0.74~0.79보다 낮았습니다.

[서빙 코드](../demo/serving/score.py)는 입력과 범주 설명 3개의 임베딩을
cosine similarity로 비교해 가장 큰 범주를 반환합니다.
신뢰도 임계값과 "기타" 범주가 없어 낮은 similarity에서도 항상 한 범주를 반환합니다.
MiniLM은 영어 임베딩 모델이므로 한국어 청구·네트워크 문장은 cancellation으로 오분류되었습니다.
한국어 시연이나 실제 업무에는 다국어 모델, 임계값과 "기타" 처리, 별도 품질 검증이 필요합니다.
토큰화는 256 token에서 잘리므로 2,000자 입력 허용이 전체 문장 반영을 뜻하지 않습니다.

배포 로그(`get_logs`)에는 거부된 요청의 `Rejected invalid scoring request: <사유>`
WARNING만 보였고 요청 문장은 로그에 남지 않았습니다.
성공 요청의 `Scored` INFO는 최근 600줄에서 보이지 않았으므로
컨테이너 로그로 성공 건수를 세지 않습니다.

Azure Monitor의 `RequestsPerMinute`에는 호출 후 1~2분 내에 HTTP 200, 401, 424가
상태 코드별로 나타났고 `RequestLatency`에는 `blue` 값이 기록되었습니다.
1분 Average 집계값은 실제 호출 수와 일치하지 않았으므로
지표 수집 확인에만 사용하고 호출 수 검증에는 쓰지 않습니다.
`RequestLatency`는 `deployment` 차원만 지원하여 상태 코드별로 나눌 수 없습니다.

Application Insights에는 컨테이너에 도달한 `/score` 요청이 기록되었습니다.
무인증 401 요청은 컨테이너에 도달하기 전에 거부되어 기록되지 않았습니다.
요청 텔레메트리의 `resultCode`와 `duration`은 0으로 남으므로
요청 수 확인에만 사용하고 성공률과 지연 분석에는 쓰지 않습니다.

## ACR Custom 이미지 빌드 검증

연결된 Premium ACR `crktmlopsaow7cshia2xmu.azurecr.io`에
학습·서빙 의존성이 설치된 Custom 이미지가 실제 저장되어 있습니다.
AML은 MCR 기본 이미지와 Conda 정의로 Dockerfile을 생성하고,
`cpu-secure`에서 빌드한 뒤 ACR에 push합니다.
직접 작성한 Dockerfile이나 ACR Tasks의 `az acr build` 실행 결과는 아닙니다.

아래 매핑은 Completed 이미지 빌드 Job의 `docker build` 명령,
패키지 설치 내역 및 push digest를 ACR 태그 조회 결과와 대조했습니다.
ACR 이미지 태그 번호는 AML Environment 버전과 별개이며,
각 repository의 `latest`도 같은 digest를 가리키지만 변경 가능한 태그입니다.

| 용도 / AML Environment | ACR repository:tag | 이미지 빌드 Job | 상태 |
|---|---|---|---|
| 현재 학습 / kt-sklearn-mlflow:2 | azureml/azureml_882df10a7bff22e2d69b3fa30657dfa5:1 | imgbldrun_b6f62eb | Completed |
| 현재 HF 서빙 / kt-hf-cpu:1 | azureml/azureml_8bb3369a9b31112c26f6a1f2ebd3b2f4:1 | imgbldrun_73d816a | Completed |
| 이전 학습 / kt-sklearn-mlflow:1 | azureml/azureml_4bb4598bf36822bb5d652caa849d434b:2 | imgbldrun_855134a | Completed |

이미지 식별에는 다음 불변 digest를 사용합니다.

```text
현재 학습
crktmlopsaow7cshia2xmu.azurecr.io/azureml/azureml_882df10a7bff22e2d69b3fa30657dfa5@sha256:6efeaac01755aa7c319f811428a77fa48afd0d12ebe8c3caedf16e94254e3781

현재 HF 서빙
crktmlopsaow7cshia2xmu.azurecr.io/azureml/azureml_8bb3369a9b31112c26f6a1f2ebd3b2f4@sha256:98cbf092716a30d90c6be880ff1806724da5b449e050885c68ada550fd69b646

이전 학습
crktmlopsaow7cshia2xmu.azurecr.io/azureml/azureml_4bb4598bf36822bb5d652caa849d434b@sha256:e7d86960637b36807ad8df6735a737114312b37d4c0f7c7583a792df3a4a2ebf
```

현재 학습 이미지에는 `azureml-mlflow==1.62.0.post6`와 `mlflow==2.22.2`,
HF 서빙 이미지에는 `torch==2.8.0+cpu`, `transformers==4.57.6`,
`azureml-inference-server-http==1.5.0`이 설치되었습니다.
이전 학습 이미지는 빌드 자체는 성공했지만 MLflow adapter 1.61.0의
런타임 호환성 문제로 현재 학습에는 사용하지 않습니다.
이미지 빌드 성공과 모델 학습 성공은 별개의 검증 항목입니다.

이미지 태그와 digest는 다음 읽기 전용 명령으로 확인할 수 있습니다.

```powershell
az acr repository list --name crktmlopsaow7cshia2xmu -o table
az acr repository show-tags --name crktmlopsaow7cshia2xmu `
  --repository azureml/azureml_882df10a7bff22e2d69b3fa30657dfa5 `
  --detail --query "[].{tag:name,digest:digest}" -o table
```

Studio의 Environments에서 환경별 build log를 확인하고,
Azure Portal의 ACR Repositories에서 같은 repository/tag/digest를 보여주세요.
학습 Job과 온라인 배포는 해당 환경 이미지를 사용하며,
실제 학습 완료와 Endpoint 추론 성공은 위 E2E 결과로 별도 검증했습니다.

## 발표 및 재실행

소규모 합성 데이터 1,500행으로 CPU 학습을 수행합니다.
두 모델은 동일한 1,125행 train / 375행 holdout을 사용합니다.
HF MiniLM은 별도 사전학습 임베딩 모델이며 continual fine-tuning은 하지 않았습니다.
훈련한 churn 모델을 HF 모델이라고 설명하면 안 됩니다.

기존 자산을 확인하고 Endpoint를 호출하는 검증은 다음과 같습니다.

```powershell
uv run --no-sync python -m demo.manage verify
```

위 명령은 실제 추론 요청을 발생시키는 실행 명령이며 읽기 전용 상태 조회가 아닙니다.
2026-10-27 09:49 UTC 실행 결과는 Git에서 제외된 `local/verification.json`에 남았습니다.
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
이번 문서 검토에서 테스트·lint·Bicep build를 재실행하지 않았습니다.
기존 GitHub CI 성공은 [run 40440292071](https://github.com/daeungo1/azure-llm-mlops/actions/runs/40440292071)에서 확인했습니다.
해당 CI 로그의 pytest 결과는 23 passed, 1 skipped입니다.
CI에는 `HF_MODEL_DIR` 설정이 없으므로 선택적 실제 HF 모델 테스트는 skip되며,
CI 성공을 실제 모델 추론 테스트까지 모두 실행한 결과로 해석하지 않습니다.
