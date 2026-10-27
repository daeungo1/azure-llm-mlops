---
title: AML 기반 MLOps 및 모델 서빙 진행 가이드
description: 강사용 개념 정리, Studio 탭별 시연, 외부 MLflow 추적과 CPU Endpoint 실습
ms.date: 2026-10-26
---

## 권장 진행 순서

`mlw-ktmlops-secure` Workspace에서 시연합니다.
[배포 상태](deployment-status.md)의 실제 검증 결과를 먼저 확인하세요.
학습은 소규모 CPU 분류기이며 HF 모델의 continual fine-tuning은 아닙니다.

| 구간 | 내용 | 시연 핵심 |
|---|---|---|
| 0~15분 | MLOps 개념, DevOps와 차이 | 코드만 같아도 데이터·환경이 바뀌면 결과가 달라짐 |
| 15~30분 | Data와 Model 등록·버전 | Data v1/v2, MLTable 미리보기, MLflow 모델 |
| 30~50분 | AML 실험과 재현 가능한 학습 | 두 모델의 동일 holdout 비교, Pipeline graph |
| 50~65분 | 외부 학습에서 AML 활용 | 학습은 외부 CPU, 추적·모델 관리만 AML |
| 65~80분 | 소형 Hugging Face CPU 모델 서빙 | Endpoint Test, Consume, 오류와 인증 |
| 80~90분 | 운영 전환 논의와 정리 | 비용, 격리, 승인, 재학습과 모니터링 |

## MLOps와 DevOps의 연결

DevOps의 소스 버전·빌드·테스트·배포는 MLOps에도 필요합니다.
MLOps는 여기에 학습 데이터의 버전과 스키마, 실험의 매개변수와 지표,
학습 환경, 모델 패키지, 데이터 변화와 예측 품질의 관리를 추가합니다.

모델 정확도는 애플리케이션 테스트 통과만으로 보장되지 않습니다.
동일한 holdout, 데이터 누수 방지, 적절한 품질 기준과 배포 승인이 필요합니다.
데이터 변화는 재학습을 검토하는 신호이지 자동 배포 허가가 아닙니다.

## 세션 전 점검

1. Azure 계정과 데모 Workspace의 접근 권한을 확인합니다.
2. `uv run --no-sync python -m demo.manage verify`를 실행합니다.
3. Studio에서 Data, Jobs, Models, Components, Environments, Compute, Endpoints를 엽니다.
4. `kt-hf-cpu-secure`의 `blue` 상태가 Succeeded, 트래픽이 100%인지 확인합니다.
5. 이미지 빌드와 학습을 발표 현장에서 처음 실행하지 않습니다.
6. 검증 결과와 샘플 요청을 열어 네트워크 문제에 대비합니다.

포털의 메뉴 이름과 위치는 업데이트나 언어 설정에 따라 바뀔 수 있습니다.
SDK/API 성공과 사람이 보는 Studio 렌더링은 구분해야 합니다.

## Data

`telco-churn`에서 버전 1과 2를 선택합니다. v1은 1,500행,
v2는 1,800행이며 두 번째 버전은 support/network 분포가 바뀐 합성 데이터입니다.
이름은 같아도 버전과 경로가 다르다는 점을 설명합니다.

`telco-churn-table`의 Explore/Preview에서 열과 데이터를 확인합니다.
MLTable 자산은 CSV를 읽는 선언적 정의와 연결됩니다.
표 미리보기는 로그인 사용자에게 Blob 읽기 권한이 있어야 합니다.
합성 데이터에는 고객 이름, 전화번호, 고객 ID가 없습니다.

## Jobs와 Pipeline

실험 `kt-telco-churn`에서 `telco-logistic-data-v1`,
`telco-forest-data-v1`을 확인합니다. 두 모델은 동일한 v1 데이터와
random seed=42의 holdout을 사용합니다.

Pipeline graph의 Prepare -> Train 노드를 선택해서
Inputs/Outputs, 코드 snapshot, Environment, Compute를 확인합니다.
두 학습 노드의 Metrics에서 accuracy/f1/roc_auc를 비교합니다.
Outputs + logs에서 confusion matrix, metrics JSON, MLflow model을 엽니다.
데이터 버전이 다른 외부 실험을 여기에 섞어 우열을 주장하지 않습니다.

## Models

`telco-churn-classifier`의 v1(logistic), v2(forest)를 확인합니다.
MLflow 모델은 가중치 파일만이 아니라 `MLmodel`, 환경 정의,
입출력 signature와 input example을 포함하는 배포 가능한 패키지입니다.
원본 Job과 데이터 입력을 따라가며 lineage를 설명합니다.

버전 2가 항상 더 좋은 모델이라는 뜻은 아닙니다.
품질 지표와 운영 기준에 따라 배포 대상을 선택해야 합니다.
실제 승인 기반 승격·롤백은 이 교육 데모에 자동화하지 않았습니다.

## 외부 MLflow 추적

`uv run --no-sync python -m demo.manage external`을 실행합니다.
이때 학습 연산은 PC에서, 추적 저장과 모델 등록은 AML에서 수행됩니다.
`kt-external-mlflow`의 새 run에서 `execution_source=external-local-cpu`,
데이터 v2, 지표와 모델을 확인합니다.

이 방식은 Slurm job에서도 AML tracking URI와 인증을 설정하는 패턴으로 확장할 수 있습니다.
그러나 외부 MLflow run을 AML Compute에서 실행한 managed Job으로 설명하면 안 됩니다.
외부 run만으로는 AML 파이프라인 그래프나 동일한 데이터 lineage가 자동 생성되지 않습니다.
실제 Slurm의 인증·네트워크·다중 과제 격리는 별도 검증 대상입니다.

## HF CPU 실시간 Endpoint

`kt-hf-cpu-secure` -> `blue` -> Test에서 아래 요청을 사용합니다.

```json
{
  "texts": [
    "My invoice includes unexpected charges and I need a refund.",
    "My mobile internet is very slow and calls keep dropping.",
    "Please cancel my subscription and close my account."
  ]
}
```

예상 intent 순서는 `billing`, `network`, `cancellation`입니다.
출력에 384차원 임베딩 모델이라는 정보가 있지만 전체 벡터는 반환하지 않습니다.
추론 코드는 평균 pooling과 L2 정규화 후 cosine similarity로 분류합니다.
하드코딩된 응답이나 API 대체 응답이 아닙니다.

Consume에서 scoring URI와 인증 방식을 확인합니다.
Public network는 익명 공개 API를 뜻하지 않습니다. Entra token이 필요합니다.
`{"texts":[]}`는 4xx 오류, 인증 없는 요청은 401/403을 반환해야 합니다.
실제 Managed Endpoint에서는 잘못된 입력의 모델 응답 400을 외부 HTTP 424로
감싸 반환하며 `ms-azureml-model-error-statuscode: 400` 헤더로 확인할 수 있습니다.
Logs/Monitoring에서 컨테이너 로그와 요청 지표를 확인합니다.
이 예제는 원문 상담 내용을 로그에 남기지 않습니다.

## Compute, Components, Environments

Compute의 `cpu-secure`에서 min=0, max=2, DS3_v2를 확인합니다.
대기 중 0대인 상태는 정상이며 온라인 Endpoint CPU와 별개입니다.
Components에서 prepare/train의 입력·출력 계약을,
Environments에서 학습용과 서빙용의 패키지 버전을 확인합니다.

Notebooks, AutoML, Designer 편집기, Responsible AI, Batch Endpoint,
드리프트 모니터는 이번 실습의 완료 조건이 아닙니다.
빈 탭을 채우기 위한 미검증 자산은 만들지 않습니다.

## 자주 발생하는 문제

| 증상 | 확인과 대응 |
|---|---|
| Blob 403 | 업로더/학습 Compute/Endpoint identity의 Blob 역할과 RBAC 전파 확인 |
| 이미지 빌드 실패 | Environments의 build log, ACR 접근, 패키지 버전 확인 |
| CPU 할당 실패 | AML 리전별 VM family quota와 실제 VM capacity를 별도로 확인 |
| Endpoint 401/403 | `aad_token`의 audience와 `score/action` 권한 확인 |
| Endpoint 4xx | JSON 필드, 1~16개 문장, 문장당 2,000자 제한 확인 |
| Studio 메뉴가 다름 | Workspace가 ML Workspace인지 확인하고 최신 포털 메뉴에 맞춰 탐색 |
| 외부 실험이 안 보임 | Tracking URI와 Workspace, experiment 이름, 로그인 tenant 확인 |

실패한 환경이나 Job을 성공이라고 숨기지 말고 해당 로그와 상태를 먼저 확인합니다.
