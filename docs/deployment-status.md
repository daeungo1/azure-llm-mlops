---
title: 실제 Azure 배포 상태
description: 교육 MLOps 완료 범위, 로컬 랩탑 접근, 실제 ACR 이미지와 Endpoint 호출 검증 결과
ms.date: 2026-10-29
---

## 다중 팀 RG와 공용 Registry

팀별 권한·비용 경계를 Workspace 이름이나 태그만으로 구분하지 않고,
Korea Central에 세 개의 전용 Resource Group을 실제 배포했습니다.
구독 배포 `kt-three-teams`와 공통 RG 배포 `kt-shared-registry`는 Succeeded입니다.

| 구분 | Resource Group | Workspace 또는 Registry | 기본 인프라 |
|---|---|---|---|
| Team 1 | rg-kt-mlops-team-1 | mlw-ktmlops-secure-1 | 배포 성공 |
| Team 2 | rg-kt-mlops-team-2 | mlw-ktmlops-secure-2 | 배포 성공 |
| Team 3 | rg-kt-mlops-team-3 | mlw-ktmlops-secure-3 | 배포 성공 |
| 공통 자산 | rg-kt-mlops | mlr-ktmlops-shared | 배포 성공 |
| 기존 교육 이력·HF 서빙 | rg-kt-mlops | mlw-ktmlops-secure | 기존 검증 환경 유지 |

각 팀 RG는 Storage, Key Vault, Premium ACR, Application Insights,
Log Analytics, NSP와 Workspace를 전용으로 갖습니다.
각 팀 CPU Compute는 DS3_v2, min=0, max=1로 생성 완료했으며,
전용 subnet과 public IP 없는 노드 설정을 실제 API에서 확인했습니다.
Workspace Private Endpoint는 세 팀 모두 Approved입니다.
세 팀의 공유 자산 소비 Pipeline과 각 `consume` 노드는 모두 Completed입니다.
아래 Job 로그와 검증 보고서에서 실제 추론·자기 데이터 읽기·상대 팀 권한 거부를 확인했습니다.

![팀별 RG와 공용 Registry 구조](images/multi-team-architecture.svg)

### 공통 자산과 네트워크 경계

Azure ML Registry는 Model, Environment, Component를 공유하는 ML 자산 카탈로그입니다.
컨테이너 이미지를 저장하는 ACR과는 별도 서비스입니다.
기존 검증 Workspace에서 공유한 churn MLflow 모델 `telco-shared:1`과
CPU 학습 환경 `kt-shared-cpu:1`, Registry에 직접 등록한 검증 Component
`verify_shared_model:3`은 등록이 완료되었습니다.
Component v1/v2는 AML 실행 명령의 공백 정규화로 Python 들여쓰기가 손상되어 실패했습니다.
v2의 Registry 원문은 로컬과 동일했지만 실행 단계에서 다시 손상됨을 확인했습니다.
v3는 신뢰된 로컬 코드 원문을 Base64로 직렬화해 한 줄 명령으로 전달하고,
실행 시 복원합니다. 별도 코드 업로드나 입력 데이터의 실행은 하지 않습니다.
Model·Environment v1은 유지했으며 기존 불변 Component 버전은 덮어쓰지 않았습니다.
세 팀은 동일한 Model v1·Environment v1·Component v3를 사용했습니다.
HF MiniLM을 재학습하거나 각 팀에 Endpoint 세 개를 복제하는 구성이 아닙니다.

| 팀 | 완료된 Pipeline Job | 실제 예측 | 자기 Blob | 상대 팀 Blob |
|---|---|---|---|---|
| Team 1 | [plum_van_kv28bglrqg](https://ml.azure.com/runs/plum_van_kv28bglrqg?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops-team-1/workspaces/mlw-ktmlops-secure-1) | [1, 0, 1] | 200 | Team 2: 403 |
| Team 2 | [gifted_deer_66y29xx9f5](https://ml.azure.com/runs/gifted_deer_66y29xx9f5?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops-team-2/workspaces/mlw-ktmlops-secure-2) | [1, 0, 1] | 200 | Team 3: 403 |
| Team 3 | [strong_basin_qrgr4ykljk](https://ml.azure.com/runs/strong_basin_qrgr4ykljk?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops-team-3/workspaces/mlw-ktmlops-secure-3) | [1, 0, 1] | 200 | Team 1: 403 |

세 상대 팀 응답의 오류 코드는 모두 `AuthorizationPermissionMismatch`입니다.
자기 Blob의 팀 marker 내용도 일치했으며 운영자 토큰 대신 Compute managed identity를 사용했습니다.
검증은 위 세 방향이며 여섯 방향 전체나 별도 Entra 사용자·그룹의 격리를 검증한 것은 아닙니다.
실행 증적은 각 자식 Job의 `user_logs/std_log.txt`에 JSON으로 남습니다.
수집 코드는 실제 자식 로그를 다운로드하고 응답·팀·예측 형태를 다시 검사한 뒤
Job별 로컬 `verification.json`과 `multiteam.json`에 기록합니다.
Pipeline named-output URI가 없어 SDK가 다운로드를 건너뛰는 경우를
보고서 수집 성공으로 처리하지 않도록 검증했습니다.
최종 로컬 검증은 pytest 39개 통과·1개 skip, Ruff 검사와 포맷 검사를 통과했습니다.
네 개 SVG의 XML과 관련 문서의 로컬 링크 대상도 확인했습니다.
Job 종료 후 세 팀 Compute는 모두 실제 노드 0대·Steady로 축소된 것을 확인했습니다.
NAT·Private Endpoint·ACR 등은 노드가 0대여도 기본 비용이 발생합니다.

Registry가 자동 생성한 관리형 RG의 Storage는 조직 정책으로 public 접근이 Disabled입니다.
관리형 deny assignment를 제거하거나 Storage 쓰기 권한을 우회하지 않습니다.
팀 Managed Network에서 해당 Storage의 Blob Private Endpoint를 추가하려 했지만,
Workspace identity의 대상 Storage 읽기·연결 승인 권한이 없어 HTTP 400으로 거부되었습니다.
연결 생성 이전의 검증 단계에서 거부되어 수동 승인할 Pending 연결도 없습니다.
관리형 RG에 대한 일반 역할 추가도 deny assignment의 제한을 받으므로,
상위 범위 권한을 넓히지 않는 사용자 관리 VNet 경로를 선택했습니다.
각 팀에 전용 VNet, NAT, Blob/File/Vault 및 Workspace API·notebooks
Private DNS와 Private Endpoint를 구성했으며,
운영자가 허용된 Private Endpoint 작업으로 Registry Blob을 연결합니다.
새 팀 Workspace는 자산·Job·Compute가 없는 상태에서 Workspace만 재생성해
Managed Network mode를 처음부터 Disabled로 설정했습니다.
기존 AllowInternetOutbound 모드를 Disabled로 되돌리는 변경은 지원되지 않습니다.
Compute는 팀 전용 subnet과 public IP 없는 노드를 사용합니다.
Public IP 없는 AML Compute를 만들려면 Workspace Private Endpoint가 먼저 필요합니다.
Workspace의 publicNetworkAccess는 Enabled이므로 운영 PC의 Studio 진입은 유지됩니다.
Registry backing Blob의 public 접근은 열지 않았으므로,
운영 PC에서 그 Blob을 직접 다운로드하려면 별도 private 연결이 필요합니다.
Blob Private DNS 링크에만 `NxDomainRedirect`를 적용했습니다.
자기 팀·Registry의 기존 DNS 레코드는 private IP를 사용하고,
레코드가 없는 상대 팀 Blob은 public DNS로 해석해 실제 RBAC 거부를 검사합니다.
기본 Private DNS만 사용할 때 발생한 상대 팀 NXDOMAIN을 권한 차단 성공으로 집계하지 않았습니다.
다른 DNS 영역은 Default이며 VNet peering·상대 팀 데이터 권한은 추가하지 않았습니다.
설정 근거는 [Azure Private DNS fallback 공식 문서](https://learn.microsoft.com/en-us/azure/dns/private-dns-fallback)입니다.
기존 검증 Workspace의 Managed Network와 Endpoint에는 변경이 없습니다.
모델·환경 등록은 로컬 PC에서 Registry Storage에 직접 업로드하는 방식 대신
지원되는 Workspace-to-Registry 공유 API로 완료했습니다.
검증 Component는 별도 코드 업로드가 필요 없는 인라인 명령으로 등록했습니다.

팀 Compute identity에는 자기 Storage의 Blob 역할과 Registry Reader만 부여하는 방식입니다.
구독 Owner 계정의 모든 팀 조회는 팀 사용자 격리의 증거가 아닙니다.
실제 Entra 팀 사용자·그룹, 10개 팀 전체, Slurm 연동과 운영 보안 인증은 검증 범위가 아닙니다.

### 비용 구분과 현재 조회 결과

Cost Management의 Cost analysis에서 Resource group으로 그룹화합니다.
팀 전용 리소스 비용은 세 팀 RG로, Registry backing Storage·ACR 비용은
별도의 `azureml-rg-mlr-ktmlops-shared_...` 관리형 RG로 구분합니다.
후자는 공통 비용이며 팀에 자동 배분되지 않습니다.

2026-10-28 00:43 UTC의 MonthToDate ActualCost 조회에는 기존 `rg-kt-mlops`의
USD 5.59546797727373만 반환되었습니다.
신규 팀·Registry 관리형 RG의 청구 행 부재는 비용 0의 증거가 아닙니다.
신규 사용량이 청구 데이터에 반영된 이후 금액을 다시 확인해야 합니다.
`team`과 `costCenter` 태그는 보조 분류이며 권한 경계나 예산 강제 제한이 아닙니다.
max=1도 동시 VM 수 상한일 뿐 금액 한도가 아니며 별도 Budget은 설정하지 않았습니다.

### 기존 환경 보존과 정리 범위

`mlw-ktmlops-secure`에는 완료된 학습·MLflow·HF 서빙 이력이 있으므로 유지합니다.
초기 `mlw-ktmlops`는 실패 Job 네 개와 실패한 `blue` 배포만 확인했습니다.
두 Workspace가 기존 Storage·ACR·Key Vault·Insights를 공유하므로,
초기 Workspace 정리 시에도 이 종속 리소스를 함께 삭제하면 안 됩니다.
초기 Endpoint `kt-hf-cpu`와 Compute `cpu-demo`, Workspace `mlw-ktmlops`는
삭제 완료했습니다. Storage·ACR·Key Vault 등 공유 종속 리소스는 보존했습니다.
삭제 후 `mlw-ktmlops-secure`의 종속 리소스 참조가 동일함을 확인했고,
2026-10-27 23:55 UTC에 기존 교육 환경을 다시 검증했습니다.
Data·Model v1/v2, 완료된 두 학습 Job과 외부 MLflow run을 확인했으며,
HF 추론은 정상 응답과 billing/network/cancellation 순서를 유지했습니다.
무인증 호출은 401, 잘못된 입력은 424로 거부되었습니다.

## 전체 MLOps 파이프라인 검토 결론

요청한 교육 Agenda의 Data/Model 관리, CPU 학습, MLflow 추적,
HF CPU Endpoint 생성·추론은 완료 이력을 확인했습니다.
다만 동일한 학습 모델을 등록한 뒤 서빙하는 단일 연속 파이프라인이나
운영용 MLOps 전체 자동화가 완료된 것은 아닙니다.

이 절은 다중 팀 확장 이전의 교육 MLOps 검토 결과입니다.
검토는 코드·실행 로그·저장된 검증 기록, 당시 Azure 자산·Job 상태 조회,
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
| 운영 PC 브라우저 접근 | 사용자 확인 | 2026-10-29 07:50 KST, 운영자가 로컬 브라우저에서 리소스 화면이 보임을 확인 |
| Studio 전체 탭 기능 검사 | 별도 범위 | 모든 탭의 동작과 데이터 미리보기 렌더링을 전수 검사한 것은 아님 |

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

이전 검토 당시에는 [Bicep 템플릿](../infra/main.bicep)의 Key Vault public access가
Enabled이고 실제 배포 상태는 Disabled인 차이가 있었습니다.
후속 다중 팀 구성에서 템플릿도 Disabled로 정렬했습니다.
재배포 전에는 코드뿐 아니라 정책 적용 결과와 실제 유효 설정도 확인해야 합니다.

## 로컬 랩탑에서의 접근 확인

2026-10-28 23:26 KST(14:26 UTC)에 현재 랩탑의 Azure CLI 운영자 계정으로
아래 조회를 확인했습니다. 브라우저 로그인과 리소스의 네트워크·API 접근은 구분합니다.
2026-10-29 07:50 KST에는 운영자가 로컬 브라우저에서 리소스 화면이 보임을 확인했습니다.
자동화의 SDK/API 검증과 운영자의 브라우저 접근 확인을 함께 기록합니다.
Studio 전체 탭의 기능과 데이터 미리보기 렌더링을 전수 검사한 것은 아닙니다.

### 수정한 접근 설정

랩탑의 공인 egress IPv4가 기존 허용 주소와 달라 Storage 조회가 차단되었습니다.
공통 RG와 세 팀 RG의 NSP `operator-egress` 규칙에 현재 주소의 `/32`를 추가하고
기존 허용 주소도 유지했습니다. 네 개 Storage의 `SecuredByPerimeter`,
NSP `Enforced`, 공유 키·익명 Blob 비활성화 설정은 그대로입니다.
Workspace와 Endpoint의 인증 방식, 팀 Compute identity, Private Endpoint도 변경하지 않았습니다.

Azure Files 조회의 HTTP 403은 별도의 데이터 권한 부족이 원인이었습니다.
현재 운영자 사용자에게 각 Workspace의 `workspaceworkingdirectory`와
`workspacefilestore`가 가리키는 여덟 File share 각각을 범위로
`Storage File Data Privileged Reader`를 부여했습니다.
파일·디렉터리 ACL과 무관하게 해당 share를 읽을 수 있는 OAuth FileREST 역할이며,
쓰기·삭제 권한이나 구독·Storage 계정 전체 범위의 File 역할은 추가하지 않았습니다.
팀 Compute나 팀 사용자에게 다른 팀 데이터 권한을 부여한 것이 아닙니다.
[Azure Files OAuth 권한](https://learn.microsoft.com/en-us/azure/storage/files/authorize-oauth-rest)을 기준으로
공유 키 없이 `x-ms-file-request-intent: backup`을 사용하는 읽기를 검증했습니다.

### 실제 조회 결과

| 대상 | 현재 랩탑에서 확인한 결과 | 해석 |
|---|---|---|
| 기존·팀 1~3 Workspace | 모두 Succeeded, public ingress Enabled. Datastores·Jobs·Models·Environments API 조회 성공 | 팀 Models 목록은 비어 있음. 공유 모델은 Registry 범위에서 조회 |
| 기존 Data·Model | churn Data·MLTable 및 학습 모델 v1/v2 조회 성공 | 자산 메타데이터 접근 확인 |
| Blob 데이터 | 네 Storage의 컨테이너 목록 조회, 기존 CSV 27,947 bytes·MLTable 114 bytes, 세 팀 marker 각각 HTTP 200 | 실제 파일 읽기까지 확인 |
| File Datastore | 여덟 File share 모두 OAuth 목록 조회 HTTP 200 | 루트 항목은 모두 0개. 학습 데이터는 Blob에 저장되어 있음 |
| 브라우저 CORS | 네 Storage 모두 `ml.azure.com`과 `portal.azure.com` origin의 Blob OPTIONS HTTP 200 | 브라우저 미리보기의 CORS 전제 확인. 화면 렌더링 검증과는 다름 |
| MLflow | 외부 run의 FINISHED 상태와 accuracy·F1·ROC AUC 읽기 성공 | 기존 실험 기록을 실제 tracking API로 조회 |
| 팀 Job 로그 | Team 1의 완료된 `consume` 자식 Job 로그 다운로드 성공 | 상태 목록뿐 아니라 출력 로그 읽기도 확인 |
| 공용 ML Registry | `telco-shared:1`, `kt-shared-cpu:1`, `verify_shared_model:3` 조회 성공 | 공유 자산의 메타데이터 접근 확인 |
| ACR | 네 ACR 모두 인증된 Repository 목록 조회 성공. 기존 ACR의 이미지 태그·digest 확인 | 팀 ACR 세 개의 목록은 비어 있음. 조회 실패가 아님 |
| Application Insights·Logs | 네 연결 리소스 조회와 네 Logs workspace의 인증된 KQL 쿼리 성공 | 기존 workspace의 최근 1시간 AppTraces는 0건. 최근 요청 로그의 적재를 확인한 것은 아님 |
| HF Online Endpoint | 인증된 정상 추론 3회 성공, 무인증 401, 빈 입력 424 | 아래 E2E 검증과 동일 |
| Key Vault | 네 Vault 모두 Succeeded, public access Disabled 유지 | Portal의 리소스 설정 조회와 로컬에서 비밀 값을 읽는 것은 별개. 로컬 secret 조회는 열지 않음 |
| Registry backing Blob | public access Disabled, 팀 Private Endpoint 세 개 Approved 유지 | 로컬에서 모델 파일을 직접 내려받는 public 경로는 열지 않음 |

File share와 팀 ACR이 빈 것은 접근 오류가 아닙니다.
또한 운영자 계정이 모든 팀을 조회할 수 있다는 사실은 팀 사용자 간 격리 검증이 아닙니다.

### 리소스 바로가기

| 대상 | 링크 |
|---|---|
| 기존 학습·서빙 Workspace | [Azure ML Studio](https://ml.azure.com/?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops/workspaces/mlw-ktmlops-secure) |
| 팀 Workspace | [Team 1](https://ml.azure.com/?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops-team-1/workspaces/mlw-ktmlops-secure-1) · [Team 2](https://ml.azure.com/?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops-team-2/workspaces/mlw-ktmlops-secure-2) · [Team 3](https://ml.azure.com/?wsid=/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourcegroups/rg-kt-mlops-team-3/workspaces/mlw-ktmlops-secure-3) |
| 공통 리소스 RG | [Azure Portal](https://portal.azure.com/#@f6d04047-ac77-4fc2-941f-798ed4d54fcf/resource/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourceGroups/rg-kt-mlops/overview) |
| 기존 Storage | [Azure Portal](https://portal.azure.com/#@f6d04047-ac77-4fc2-941f-798ed4d54fcf/resource/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourceGroups/rg-kt-mlops/providers/Microsoft.Storage/storageAccounts/stktmlopsaow7cshia2xmu/overview) |
| 기존 ACR | [Azure Portal](https://portal.azure.com/#@f6d04047-ac77-4fc2-941f-798ed4d54fcf/resource/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourceGroups/rg-kt-mlops/providers/Microsoft.ContainerRegistry/registries/crktmlopsaow7cshia2xmu/overview) |
| 공용 ML Registry | [Azure Portal](https://portal.azure.com/#@f6d04047-ac77-4fc2-941f-798ed4d54fcf/resource/subscriptions/2cf925b6-80cb-4567-abda-5ccd3010aab5/resourceGroups/rg-kt-mlops/providers/Microsoft.MachineLearningServices/registries/mlr-ktmlops-shared/overview) |

> [!IMPORTANT]
> 현재 랩탑의 네트워크와 운영자 계정에서 확인한 결과입니다.
> 행사장 Wi-Fi, 테더링 또는 VPN 전환으로 공인 egress IP가 바뀌면
> Storage의 NSP 허용 `/32`와 Blob 읽기를 다시 확인해야 합니다.
> 템플릿 재배포 시에도 `operatorAddressPrefix`에는 현재 허용할 주소를 지정해야 합니다.
> Portal의 Storage browser에서는 공유 키가 아닌 Microsoft Entra 사용자 인증을 사용합니다.

## 클라우드 E2E 및 Endpoint 호출 검증

`python -m demo.manage verify`는 Pipeline·자산·Endpoint 상태를 확인한 뒤
Endpoint를 실제로 호출합니다. 초기 기록은 2026-10-27 02:40 UTC이고,
현재 `local/verification.json`에는 2026-10-28 14:15 UTC에
랩탑에서 다시 실행한 결과가 남아 있습니다.

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
| 3회 왕복 지연(2026-10-28 14:15 UTC) | 1.622 / 0.973 / 0.779초 |
| 무인증 요청 | HTTP 401 |
| 빈 texts | 외부 HTTP 424, model-error-statuscode 400 |

2026-10-27 실행의 3회 왕복 지연은 02:40 UTC에 1.795 / 1.618 / 0.650초,
09:25 UTC에 2.369 / 2.317 / 1.486초,
09:49 UTC에 0.893 / 0.685 / 0.748초였습니다.
직렬 호출 3회의 클라이언트 왕복 시간이며 편차가 있으므로 성능 SLO로 사용하지 않습니다.

학습 run의 MLflow start/end 기준 소요 시간은 Logistic 약 34.4초,
Random Forest 약 115.6초였습니다. 이미지 빌드·Prepare·VM 대기 시간은 포함하지 않습니다.
동일 holdout의 accuracy / ROC AUC는 각각 Logistic 0.7333 / 0.7878,
Random Forest 0.7307 / 0.7845입니다. 버전 2가 더 우수하다고 주장하지 않습니다.

MLflow adapter 1.61.0은 MLflow 2.22.2의 artifact API와 충돌했습니다.
로컬에서 검증한 `azureml-mlflow==1.62.0.post6`으로 환경 v2를 만들어
실제 클라우드 학습·artifact·모델 등록을 성공시켰습니다.
이전 실패 이력은 보존되어 있으며 현재 완료된 Job과 구분합니다.

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
한국어 입력이나 실제 업무에는 다국어 모델, 임계값과 "기타" 처리, 별도 품질 검증이 필요합니다.
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

Studio의 Environments에는 환경별 build log가,
Azure Portal의 ACR Repositories에는 같은 repository/tag/digest가 남아 있습니다.
학습 Job과 온라인 배포는 해당 환경 이미지를 사용하며,
실제 학습 완료와 Endpoint 추론 성공은 위 E2E 결과로 별도 검증했습니다.

## Studio 시각적 검증 범위

운영자는 2026-10-29 07:50 KST에 로컬 브라우저에서 리소스 화면 접근을 확인했습니다.
공유 테스트 브라우저의 로그인 상태와 운영자의 일반 브라우저는 별개입니다.
Studio 전체 탭과 데이터 미리보기의 기능 전수 검사는 수행하지 않았습니다.
자산 목록·Job 상태·모델 버전·Endpoint 호출은 인증된 SDK/API로 검증했습니다.

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
