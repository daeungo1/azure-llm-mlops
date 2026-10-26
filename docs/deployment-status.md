---
title: 실제 Azure 배포 상태
description: 2026-10-26 배포 결과와 조직 네트워크 정책으로 인한 차단 사항
ms.date: 2026-10-26
---

## 배포 완료

Korea Central의 `rg-kt-mlops`에 다음 리소스를 실제 생성했습니다.
ARM 배포 `kt-mlops-foundation`의 상태는 Succeeded입니다.

| 리소스 | 이름 |
|---|---|
| Azure ML Workspace | mlw-ktmlops |
| Storage Account | stktmlopsaow7cshia2xmu |
| Azure Container Registry | crktmlopsaow7cshia2xmu |
| Key Vault | kv-ktmlops-aow7cshia2 |
| Application Insights | appi-ktmlops |
| Log Analytics Workspace | log-ktmlops |
| AML CPU cluster | cpu-demo |

CPU cluster는 DS3_v2, min=0, max=2로 생성하고
클러스터 identity에 Storage Blob Data Contributor를 부여했습니다.
Workspace가 identity 기반 datastore의 Blob/File 역할을 자동 생성하므로
동일 Blob 역할을 Bicep에서 중복 생성하지 않습니다.

## 차단 사항

관리 그룹의 `MCAPSGovDeployPolicies` 정책 집합에 포함된
`StorageAccount_PublicNetwork_Modify`가 Storage의
`publicNetworkAccess`를 `Disabled`로 변경합니다.
ARM validation과 what-if는 통과하지만 배포 후 데이터 평면 접근은 차단됩니다.
따라서 ARM 성공은 전체 데모 성공을 뜻하지 않습니다.

실제 Blob 업로드에서 `AuthorizationFailure`를 재현했습니다.
Public 접근 설정 변경도 정책에 의해 Disabled로 유지되는 것을 확인했습니다.
정책은 삭제·해제·예외 처리하지 않았습니다.

다음 작업은 완료하지 않았으며 시연 가능한 상태로 표시하면 안 됩니다.

* Data v1/v2와 MLTable 등록
* 환경·Component 등록 및 클라우드 학습 Pipeline 실행
* AML에 MLflow 실험과 모델 기록
* Hugging Face 모델 등록 및 Managed Online Endpoint 생성
* 원격 추론, 인증 거부와 잘못된 입력 응답 검증
* 로그인된 Studio의 탭별 화면 검증

## 안전한 재개 절차

조직 정책 담당자가 데모 RG에 대한 정식 예외를 승인하거나,
허용된 Private Endpoint 및 네트워크 실행 환경을 설계해야 합니다.
리전을 바꾸어도 관리 그룹 정책은 그대로 적용될 수 있습니다.
정책을 우회하기 위한 다른 Storage 또는 구독 사용은 권장하지 않습니다.

승인된 네트워크 경로와 Blob 접근을 확인한 뒤 저장소 루트에서 실행합니다.

```powershell
az storage container list --account-name stktmlopsaow7cshia2xmu --auth-mode login
uv run --no-sync python -m demo.manage assets
uv run --no-sync python -m demo.manage train
uv run --no-sync python -m demo.manage external
uv run --no-sync python -m demo.manage deploy
uv run --no-sync python -m demo.manage verify
```

클라우드 검증이 성공하면 Git에서 제외된 `local/verification.json`에
실제 요청 결과와 검증 시간이 남습니다. 현재는 성공 보고서가 없습니다.
스토리지와 관측 리소스는 유지되며 비용이 발생할 수 있습니다.
온라인 배포는 생성되지 않았고 학습 클러스터는 min=0입니다.

## 로컬 검증 결과

`HF_MODEL_DIR`를 다운로드한 고정 revision의 실제 모델 경로로 설정하고
`uv run --no-sync pytest -q`를 실행하여 21개 테스트가 모두 통과했습니다.
실제 CPU 모델의 세 문장 intent 결과도 검증했습니다.
Ruff lint와 format 검사를 통과했습니다.
MLflow 및 관련 라이브러리의 deprecation 경고는 남아 있습니다.
이 결과는 로컬 검증이며 Azure Endpoint 검증을 대신하지 않습니다.
