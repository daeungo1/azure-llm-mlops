---
title: Azure ML MLOps
description: Azure ML의 주요 기능과 실제 자산·실행 근거를 정리한 MLOps 기술 문서
hide:
  - toc
---

<div class="session-hero" markdown>

<p class="eyebrow">TRACK · VERSION · SERVE</p>

## Azure ML로 연결하는 MLOps

데이터에서 실험과 모델로, 그리고 인증된 CPU 서빙으로.
Azure ML의 주요 기능과 실제 자산·실행 근거를 도식으로 정리한 기술 문서입니다.

[MLOps 개요 보기](01-overview.md){ .md-button .md-button--primary }
[실제 검증 기록](deployment-status.md){ .md-button }

<p class="session-meta">Azure Machine Learning · Korea Central · 합성 데이터</p>

</div>

## 한 장으로 보는 데모

![Azure ML Workspace 중심의 학습·MLflow·HF 서빙과 연결 리소스](images/azure-architecture.svg)

[도식 원본 크게 보기](images/azure-architecture.svg)

Workspace는 실행과 자산을 연결하고, Storage와 ACR은 데이터·모델 파일과 실행 이미지를 보관합니다.
학습한 churn 모델의 등록 경로와 **별도의 사전학습 MiniLM CPU 서빙 경로**를 구분해 살펴봅니다.

<div class="session-stats" markdown>

**11** 개념 챕터 · **3** 팀별 RG · **1** 공용 ML Registry

</div>

## MLOps의 세 가지 관리 축

<div class="grid cards" markdown>

- **01 / Track**

    동일한 데이터·평가 조건에서 실험을 비교하고 실행 출처를 남깁니다.

- **02 / Version**

    Data, Model, Environment를 각각 버전이 있는 자산으로 관리합니다.

- **03 / Serve**

    Endpoint와 Deployment를 나누고 인증·정상 추론·입력 오류를 확인합니다.

</div>

## Azure ML 주요 기능 11개 챕터

데이터·환경·실험에서 Pipeline과 모델로, 외부 학습과 CPU 서빙으로 이어집니다.
개념과 도식을 중심으로 살펴보고, 필요한 항목에서는 아래의 짧은 코드 예제를 참고합니다.

<div class="grid cards chapter-cards" markdown>

<!-- SESSION_CHAPTERS -->

</div>

## 팀별 격리와 공용 자산

![독립된 팀 RG 세 개와 공용 Registry의 자산 공유 및 비용 경계](images/multi-team-architecture.svg)

[도식 원본 크게 보기](images/multi-team-architecture.svg)

약 10개 팀 확장 논의를 3개 팀으로 축소했습니다.
기존 검증 Workspace를 유지하면서 팀별 RG·Workspace·Storage·Compute를 별도로 배포했습니다.
공용 자산을 소비한 세 팀의 Job에서 자기 Blob 200과 다른 팀 Blob 403을 확인했습니다.
이는 실행 identity의 순환 3개 경로 검증이며, 팀 사용자 그룹 전체의 격리 검증은 아닙니다.
Registry에는 Data·Model·Environment·Component를 공유하고,
별도의 팀별 HF CPU Endpoint 세 개에서 인증·정상 추론·입력 오류를 확인했습니다.

## 확인한 범위와 다음 과제

!!! success "실행 근거가 있는 항목"

    두 클라우드 학습·MLflow 비교, Data·Model 버전, Custom 이미지 빌드,
    외부 PC 추적, HF Endpoint 200·401·424, 세 팀의 Registry 소비와 Blob 권한 경계를 확인했습니다.
    실행 시점과 세부 조건은 검증 기록에 구분했습니다.

!!! warning "운영 완성으로 해석하지 않기"

    자동 재학습·품질 승인·승격·롤백, Drift·SLO, 실제 Slurm 통합은 구현 범위 밖입니다.
    로그인 후 Studio 탭별 시각적 검증은 완료되지 않았습니다.
    HF는 영어 임베딩 모델이며 추가 학습하거나 한국어 품질을 검증한 구성이 아닙니다.

[배포·검증 기록](deployment-status.md) ·
[코드와 재실행 참고](https://github.com/daeungo1/azure-llm-mlops#12-재실행개발-참고)

## Appendix · 배경 시나리오와 설계 대안

공유 GPU·Slurm 환경에서 팀별 격리와 비용 배분을 논의할 때 참고할 수 있습니다.
Azure ML, 자체 MLflow·DVC, Databricks·Unity Catalog의 설계 대안과 현재 데모의 검증 범위를 비교합니다.

[Appendix · Discussion 열기](appendix-discussion.md){ .md-button }
