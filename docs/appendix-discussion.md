---
title: Appendix · 공유 학습 환경의 MLOps 설계 비교
description: 공유 GPU·Slurm 환경에서 팀별 격리, 메타데이터 관리, 비용 배분을 논의하기 위한 설계 대안과 데모 검증 범위
ms.date: 2026-10-28
---

## 배경과 범위

여러 과제가 하나의 GPU 학습 환경을 공유하면서 데이터·권한·비용을 구분해야 하는 상황을 다룹니다.
기존 Slurm 기반 학습을 유지하고, 실험·데이터·모델 이력을 관리할 계층을 선택하는 것이 핵심입니다.
제공된 배경 시나리오와 작성자가 공개를 허용한 **원문 기반 SVG 7개**를 포함한 Discussion용 설계 비교입니다.
원문 도식의 배치·연결·레이블을 유지하고, 정확한 장비 규모와 내부 시스템 이름을 일반화한 기존 SVG를 사용합니다.

> [!IMPORTANT]
> 아래 Plan A/B/C는 검토 대안입니다. 고객 환경에 배포되었거나 운영 적합성이 입증되었다는 뜻이 아닙니다.
> 현재 데모의 실측 결과는 [배포·검증 기록](deployment-status.md)과 구분합니다.
> 그림의 인증·등록·승격 방식은 원문 제안이며, 제품 동작이 검증된 표준 구성으로 해석하지 않습니다.

## 1. 먼저 구분할 경계: 연산 공유와 과제 격리

![원문 그림 1: 공유 GPU·Slurm·Lustre와 과제별 Identity·Storage·Registry 경계](images/ktc-case/01-shared-isolation.svg)

[그림 1 SVG 크게 보기](images/ktc-case/01-shared-isolation.svg)

원문 시나리오는 약 10개 과제가 공유 GPU 풀을 사용하는 구성입니다.
파랑은 공유 연산 또는 Registry, 초록은 과제 데이터 경로, 점선은 RG 경계입니다.
SP 인증서 파일 배포 방식 등은 원문 제안이며, 현재 데모에서 구현하거나 운영 보안 적합성을 검증하지 않았습니다.

공유 자원은 GPU 연산 풀, 스케줄러, 학습용 파일시스템입니다.
반면 데이터 접근 주체, 모델·실험의 조회·등록 권한과 비용 귀속은 과제별로 구분해야 합니다.
같은 과제 식별자를 세 계층에서 연결해도 각 계층의 권한 설정이 자동으로 동기화되지는 않습니다.

| 계층 | 논의할 격리 수단 | 경계와 주의점 |
|---|---|---|
| Unix·파일시스템 | 사용자·그룹, 일관된 UID/GID, 과제 디렉터리 권한·쿼터 | 파일 권한과 관리자 권한을 별도로 검토 |
| Slurm | 과제 Account, Job 제출 범위, QoS·자원 한도, Accounting | 연산량 제한이 Azure 데이터 권한을 대신하지 않음 |
| Azure·관리 서비스 | Entra 주체, 리소스 범위 RBAC, Storage·Registry 권한, 네트워크 경계 | 공유 GPU 노드의 Identity를 과제별 실행 Identity와 동일시하지 않음 |

다음 세 가지 요구는 분리해 정의합니다.

- 다른 과제의 원본·체크포인트·모델 파일을 읽거나 수정하지 못하도록 데이터 접근을 격리합니다.
- 실험 이름, 지표, 모델 목록 자체의 공개 범위도 정합니다.
- 승인한 공통 모델만 공유하고, 다른 과제 Storage 전체의 권한을 함께 열지 않습니다.

## 2. Plan A/B/C: 형상관리 계층의 선택

아래 원문 도식은 각 대안의 제안 구조입니다.
화살표만으로 데이터 복사 여부나 Slurm 스케줄러의 관리형 서비스 통합을 단정하지 않습니다.
어느 대안이든 코드·이미지·데이터 버전과 외부 Job 식별자를 연결하는 기준이 필요합니다.

| 비교 항목 | Plan A · Azure ML | Plan B · 자체 MLflow + DVC | Plan C · Databricks + Unity Catalog |
|---|---|---|---|
| 학습 위치 | 기존 Slurm 환경 유지 | 기존 Slurm 환경 유지 | 기존 Slurm 환경 유지 |
| 관리 계층 | AML MLflow 추적, Data·Model 자산 | 자체 Tracking Server, Model Registry, Git·DVC | Databricks MLflow 추적, Models in Unity Catalog |
| 격리 설계 예 | 과제별 Workspace·Storage와 범위별 RBAC | 과제별 서버/DB·Artifact 저장소 또는 검증된 접근 제어 | Catalog·Schema·Model 권한과 Storage 접근 제어 |
| 공용 모델 | 별도 AML Registry에 승인된 버전 공유 | 인스턴스 간 복사·승인 절차를 별도 구현 | Unity Catalog의 모델 권한·공유 범위 설계 |
| 운영 부담 | Azure 리소스·Identity·네트워크와 API 호환성 관리 | 서버·DB·인증·업그레이드·백업·복구를 직접 운영 | Databricks 계정·Workspace·UC 권한과 비용 관리 |
| 주요 검증 대상 | 외부 인증, MLflow 지원 API, 모델 파일 처리·접근 경로 | 사용자 권한, Artifact 프록시, DB·저장소 복구, DVC 접근 | 외부 클라이언트 인증, UC 모델 등록·권한, 저장소·네트워크 경로 |
| 현재 데모와의 관계 | 일부 개념을 실제 검증 | 구축하지 않음 | 구축하지 않음 |

### Plan A: 연산은 유지하고 AML 관리 계층 활용

![원문 그림 2: Slurm 학습과 과제별 AML Workspace의 형상관리 연결](images/ktc-case/02-plan-a-architecture.svg)

[그림 2 SVG 크게 보기](images/ktc-case/02-plan-a-architecture.svg)

외부 연산 환경에서 Workspace의 tracking URI로 실험을 기록하는 패턴입니다.
현재 데모는 외부 PC CPU에서 이 패턴을 검증했지만, 실제 Slurm/GPU Job을 연결한 검증은 아닙니다.
공용 모델은 Workspace-to-Registry 공유 API로 관리할 수 있습니다.

AML의 MLflow 지원 범위는 OSS 전체 API와 같지 않습니다.
대형 모델을 등록할 때 파일이 어디에 저장되고 어떤 업로드·복사가 발생하는지는
모델 유형과 API·Artifact 경로별로 검증해야 하며, 단순히 “메타데이터만 관리하므로 복사가 없다”고 가정하지 않습니다.
외부 run 기록만으로 관리형 Pipeline graph나 동일 수준의 lineage가 자동 생성되는 것도 아닙니다.

![원문 그림 3: 공유 GPU·Lustre 위에 과제별 AML Workspace·Identity·Storage를 분리한 10개 과제 격리 뷰](images/ktc-case/03-plan-a-project-isolation.svg)

[그림 3 SVG 크게 보기](images/ktc-case/03-plan-a-project-isolation.svg)

과제별 RG·Workspace·Identity·Storage와 공통 연산의 경계를 보여줍니다.
그림의 `stage` 표기는 원문 개념 표현입니다.
현재 데모는 MLflow registry stage가 아니라 명시적인 AML 모델 버전으로 공유 자산을 소비합니다.

### Plan B: MLflow·DVC를 직접 운영

![원문 그림 4: 과제별 MLflow·DB·Artifact 프록시와 DVC 데이터 참조](images/ktc-case/04-plan-b-architecture.svg)

[그림 4 SVG 크게 보기](images/ktc-case/04-plan-b-architecture.svg)

MLflow가 실험·모델 메타데이터를, Git·DVC가 데이터 버전 참조를 관리하는 대안입니다.
과제별 인스턴스·DB·Artifact 저장소 분리는 격리 설계의 한 예이며 유일한 구성은 아닙니다.
실제 사용할 MLflow 버전의 접근 제어 기능과 운영 정책을 기준으로 선택합니다.

Artifact 프록시를 구성하면 서버가 저장소 접근을 중계할 수 있지만,
클라이언트 직접 접근 여부와 필요한 Blob 권한은 서버 옵션·기존 실험의 Artifact URI에 따라 달라집니다.
관리형 서비스 비용을 줄이는 선택이 운영 인력·인증·백업·복구 비용까지 없애는 것은 아닙니다.

![원문 그림 5: 공통 호스팅 기반에서 과제별 MLflow 인스턴스·DB·Blob 권한을 구분한 10개 과제 격리 뷰](images/ktc-case/05-plan-b-project-isolation.svg)

[그림 5 SVG 크게 보기](images/ktc-case/05-plan-b-project-isolation.svg)

과제 카드의 논리적 격리와 공통 Container·DB 호스팅 리소스의 실제 비용 경계를 구분합니다.
인스턴스 수만 늘린다고 인증·데이터·메타데이터 격리가 자동으로 보장되는 것은 아닙니다.

### Plan C: Databricks·Unity Catalog 활용

![원문 그림 6: Slurm 외부 추적과 Databricks Workspace·Unity Catalog·ADLS 연결](images/ktc-case/06-plan-c-architecture.svg)

[그림 6 SVG 크게 보기](images/ktc-case/06-plan-c-architecture.svg)

Unity Catalog의 모델 버전·권한·검색·감사 기능을 활용하는 대안입니다.
Catalog·Schema를 과제 경계에 대응시키는 방식은 Azure RG 격리와 다른 논리적 관리 경계입니다.
외부 Slurm 클라이언트의 인증·모델 파일 등록·조회 경로는 별도 검증 대상입니다.

Unity Catalog에서 지원하는 lineage 기능이 외부 학습 과정 전체를 자동 수집한다는 뜻은 아닙니다.
데이터·Job·코드·이미지와의 연결을 어떤 API와 태그로 남길지 정해야 합니다.
이 대안도 Slurm을 Databricks Compute로 이전하는 구성과 구분합니다.

![원문 그림 7: 공통 UC Metastore와 과제별 Workspace·Catalog 바인딩·Identity·Storage의 10개 과제 격리 뷰](images/ktc-case/07-plan-c-project-isolation.svg)

[그림 7 SVG 크게 보기](images/ktc-case/07-plan-c-project-isolation.svg)

원문은 공통 Metastore와 과제별 Workspace·Catalog 바인딩·Access Connector·Storage를 제안합니다.
Catalog의 `ISOLATED` 바인딩과 과제 권한은 PoC 대상이며,
관리형 API·스토리지·네트워크와 Compute의 청구 조건을 나눠 확인해야 합니다.
Databricks Compute를 쓰지 않는다는 이유만으로 전체 비용이 없다고 가정하지 않습니다.

## 3. 비용: 직접 비용과 공유 비용을 나누기

| 비용 종류 | 구분 방법 | Discussion 쟁점 |
|---|---|---|
| 과제 전용 Storage·관리 리소스 | 과제 RG와 리소스별 비용 조회 | 로그·네트워크·보존 비용까지 과제 비용에 포함할지 |
| 공통 Registry·DB·운영 서비스 | 공통 RG 또는 서비스 청구 단위 | 기본료·운영 비용의 배분 기준과 담당자 |
| 공유 GPU | Slurm Accounting의 과제별 사용량과 Azure 청구 대조 | GPU-hour 정의, 예약·유휴·실패 Job 비용 처리 |
| 공유 파일시스템 | 용량·보존·I/O 등 합의한 배분 기준 | 일관된 측정 방법과 비용 배분 주기 |

Azure가 공유 VM 비용을 Slurm 과제별로 자동 분할 청구하는 구조는 아닙니다.
Job 사용량과 실제 청구 금액을 연결하는 배분 규칙이 필요합니다.
태그와 Compute의 최대 노드 수는 비용 식별·자원 제한 수단이지 금액 기준의 강제 예산 한도가 아닙니다.

## 4. 실제 데모가 확인한 것과 남은 것

| 항목 | 현재 확인한 사실 | 아직 확인하지 않은 것 |
|---|---|---|
| 외부 학습 추적 | 외부 PC CPU run의 MLflow 지표·모델 기록 | 실제 Slurm·다중 GPU·다중 노드 연계 |
| 팀별 관리 경계 | 세 팀의 독립 RG·Workspace·Storage·Compute | 실제 팀 사용자·Entra 그룹 전체의 접근 제어 |
| 공용 자산 | 세 팀이 동일 Registry Model·Environment·Component 버전을 소비 | 고객의 대형 모델·데이터를 사용한 운영 적합성 |
| 데이터 접근 | Compute identity로 자기 Blob 200, 상대 팀 Blob 403 | 모든 팀·모든 방향·모든 API의 격리 |
| 접근 경로 | 새 팀의 전용 VNet·Private Endpoint에서 소비 Job 완료 | 공유 GPU 클러스터에서의 같은 인증·네트워크 경로 |
| 비용 | 팀 RG와 Registry 공통 관리형 RG를 구분해 조회 | 공유 GPU·Lustre 사용량 기반 배분과 예산 집행 |
| 모델 운영 | 별도의 사전학습 HF MiniLM CPU Endpoint 호출 | 학습한 churn 모델의 자동 승격·서빙·롤백 |

Blob 거부 검증은 세 방향의 순환 경로이며 여섯 방향 전체가 아닙니다.
구독 Owner 계정의 조회 결과를 일반 팀 구성원 권한의 증거로 사용하지 않습니다.
기존 데모의 Managed Network와 새 팀의 전용 VNet 구성도 구분합니다.
자세한 Job·응답·비용 조회 근거는 [배포·검증 기록](deployment-status.md)에 있습니다.

## 5. Discussion 쟁점

| 질문 | 결정하거나 검증할 내용 |
|---|---|
| 무엇을 바꾸지 않을 것인가? | Slurm·학습 코드·파일시스템을 유지할 범위와 관리 계층 도입 범위 |
| 누가 무엇을 볼 수 있어야 하는가? | 데이터뿐 아니라 실험·모델 목록, 등록·승인·공유 권한까지 역할별 정의 |
| 학습 주체와 등록 주체를 나눌 것인가? | 공유 GPU 노드에 과도한 권한을 주지 않는 인증·자격 증명 관리 방식 |
| 대형 모델의 정본은 어디인가? | 저장소, 해시·버전, 업로드·복사, 보존·복구와 배포 시 다운로드 경로 |
| 어떤 lineage가 필요한가? | 외부 Job ID, Git SHA, 이미지 digest, 데이터 버전, 평가 근거의 연결 |
| 공통 자산을 어떻게 공유할 것인가? | 공유 승인 주체, 버전 고정, 접근 회수, 별도 비용 귀속 |
| 공유 비용을 어떻게 배분할 것인가? | 사용량·유휴·실패 비용의 규칙과 Azure 청구 대조 방법 |
| 운영 책임은 누가 갖는가? | 인증·네트워크·DB·백업·업그레이드와 장애 복구의 책임 |

### 추가 검증의 합격 기준 예

- 서로 다른 과제의 일반 실행 주체로 자기 자산 접근과 상대 자산 거부를 모두 재현합니다.
- 실제 외부 학습 경로에서 인증 갱신·권한 회수와 Private Endpoint 접근을 확인합니다.
- 대표 크기의 모델을 등록·조회·다운로드하고 파일 해시, 데이터 이동량·시간을 대조합니다.
- 기존 Job 식별자와 데이터·코드·환경 버전으로 모델의 생성 근거를 추적할 수 있어야 합니다.
- 과제별 사용량과 공통 비용을 실제 청구 데이터에 대조하고 배분 결과를 설명할 수 있어야 합니다.

이는 추가 검증을 논의하기 위한 기준이며, 현재 충족되었다는 선언이 아닙니다.

## 공식 참고 자료

- [Azure ML에서 MLflow로 실험·모델 추적](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-mlflow-cli-runs?view=azureml-api-2)
- [MLflow Tracking Server 구성과 Artifact 저장소](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)
- [Databricks Models in Unity Catalog](https://learn.microsoft.com/en-us/azure/databricks/machine-learning/manage-model-lifecycle/)
- [Slurm Accounting](https://slurm.schedmd.com/accounting.html)

제품 기능은 공식 문서의 지원 조건에 따릅니다.
이 저장소의 학습 런타임은 MLflow 2.22.2이며, 최신 MLflow 문서의 모든 기능을 검증한 것은 아닙니다.
