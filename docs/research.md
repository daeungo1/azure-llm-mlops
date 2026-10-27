---
title: Azure ML 데모 설계의 공식 근거
description: 2026-10-26 기준 확인한 SDK v2, MLflow, Data asset, Endpoint 인증 자료
ms.date: 2026-10-26
---

## 현재 기준으로 반영한 내용

2024년 발표 자료는 수명주기 개념의 참고 자료로만 사용했습니다.
고객의 내부 설계 자료와 원본 발표 파일은 재배포하지 않습니다.
현재 API와 직접 실행 검증을 기준으로 구현합니다.

| 항목 | 반영 내용 | 근거 |
|---|---|---|
| SDK v1 지원 종료 | 신규 예제는 SDK v2만 사용 | [v1 -> v2 전환](https://learn.microsoft.com/azure/machine-learning/how-to-migrate-from-v1?view=azureml-api-2) |
| Data 등록 | URI_FILE과 MLTable을 명시적 버전으로 등록 | [Data asset 생성](https://learn.microsoft.com/azure/machine-learning/how-to-create-data-assets?view=azureml-api-2) |
| MLflow | 추적·패키징·등록, 외부 Compute 연계 | [MLflow와 Azure ML](https://learn.microsoft.com/azure/machine-learning/concept-mlflow?view=azureml-api-2) |
| Pipeline | 재사용 가능한 command component와 DSL | [SDK v2 pipeline](https://learn.microsoft.com/azure/machine-learning/how-to-create-component-pipeline-python?view=azureml-api-2) |
| Endpoint | Managed Online Endpoint, custom scoring script | [온라인 모델 배포](https://learn.microsoft.com/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2) |
| 무코드 MLflow 배포 | MLflow 모델의 별도 확장 경로로 설명, 이번 live Endpoint는 HF custom model | [MLflow 온라인 배포](https://learn.microsoft.com/azure/machine-learning/how-to-deploy-mlflow-models-online-endpoints?view=azureml-api-2) |
| 인증 | Public network + Entra `aad_token` | [Endpoint 인증](https://learn.microsoft.com/azure/machine-learning/how-to-authenticate-online-endpoint?view=azureml-api-2) |
| 데이터 인증 | Workspace system datastore에 identity 사용 | [서비스 인증](https://learn.microsoft.com/azure/machine-learning/how-to-identity-based-service-authentication?view=azureml-api-2) |
| HF 모델 | 영어, Apache-2.0, 고정 revision, 384차원 | [공식 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |
| 비용 | 지역별 공개 Linux CPU 가격 조회 | [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices) |

SDK v1은 2026-06-30 지원 종료 일정이 안내되어 있으므로 신규 데모에 사용하지 않습니다.
MLflow 3.x의 모든 기능이 AML과 동등하게 동작한다고 가정하지 않습니다.
이번 예제는 MLflow 2.22.2의 검증 가능한 기능을 사용하고,
MLflow 3 전용 logged model API나 registry stage에 의존하지 않습니다.

## 의도적인 범위 제한

* 단일 Workspace에서 MLOps 기본 흐름을 교육하는 public-network 데모
* 합성 데이터만 사용하고 실서비스 보안·격리 아키텍처로 제시하지 않음
* CPU 소형 임베딩 모델 서빙, GPU LLM 학습·서빙 아님
* 외부 tracking client 패턴 시연, Slurm 자체의 구축·통합 테스트 아님
* 데이터 변화 버전은 만들지만 운영 drift monitor나 재학습 trigger는 미구성
* 모든 Studio 탭을 채우는 것이 아니라 Agenda의 실제 기능에 해당하는 자산만 생성

Public Studio/Endpoint ingress는 인증된 교육용 경로입니다.
스토리지 익명 Blob 공개, ACR admin, 공유 Storage key는 비활성화하며
Key Vault는 RBAC, soft delete와 purge protection을 사용합니다.
실제 배포는 Storage NSP Enforced 및 AML Managed Network Private Endpoint를 사용합니다.
`AllowInternetOutbound`는 의존성 설치를 위한 인터넷 egress를 허용하므로
완전한 인터넷 차단 구성은 아닙니다.
운영 전환 시에는 최소 권한 재검토, CI/CD OIDC, 승인 단계,
데이터/모델 품질 기준, 모니터링과 비용 예산을 추가 설계해야 합니다.
