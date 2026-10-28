"""Render annotated, line-linked excerpts from the public demo implementation."""

import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from urllib.parse import quote


@dataclass(frozen=True)
class Example:
    title: str
    path: str
    start: str
    stop: str | None
    notes: tuple[tuple[str, str], ...]


EXAMPLES = {
    "01-overview": (
        Example(
            "모델 하나를 다시 만들려면 네 가지 입력이 모두 같아야 함",
            "demo/pipeline.py",
            "@dsl.pipeline(",
            "jobs = []",
            (
                ("@dsl.pipeline(", "코드와 단계 연결을 Pipeline으로 정의합니다."),
                (
                    "default_compute=COMPUTE,",
                    "Compute는 실행 자원입니다. 데이터·환경 버전과 함께 기록합니다.",
                ),
                ("prepared = prep(data=data)", "등록된 데이터가 준비 단계의 입력으로 연결됩니다."),
            ),
        ),
    ),
    "02-architecture": (
        Example(
            "Workspace = 협업·권한·추적의 경계",
            "infra/main.bicep",
            "resource workspace 'Microsoft.MachineLearningServices/workspaces@2025-06-01' = {",
            "var blobContributor = subscriptionResourceId(",
            (
                (
                    "storageAccount: storage.id",
                    "Storage는 데이터·모델·Job 파일의 실제 저장소입니다.",
                ),
                ("containerRegistry: registry.id", "ACR은 실행 환경 이미지를 보관합니다."),
                (
                    "systemDatastoresAuthMode: 'Identity'",
                    "Datastore의 접근 인증을 Identity 기반으로 구성합니다.",
                ),
                (
                    "managedNetwork: { isolationMode: managedNetworkMode }",
                    "관리형 네트워크와 public 진입점을 구분합니다.",
                ),
            ),
        ),
        Example(
            "팀마다 RG 하나, 공유는 Registry 하나",
            "demo/multiteam.py",
            "def publish(subscription: str, registry_name: str) -> None:",
            'probe_source = (ROOT / "demo" / "registry_probe" / "probe.py")'
            '.read_text(encoding="utf-8")',
            (
                (
                    "registry = MLClient(credential, registry_name=registry_name)",
                    "Workspace 클라이언트와 Registry 클라이언트를 분리합니다.",
                ),
                (
                    "model = source.models.share(",
                    "Workspace 모델을 이름·버전을 지정해 공용 Registry에 공유합니다.",
                ),
                (
                    "environment = source.environments.share(",
                    "모델뿐 아니라 실행 Environment도 공유합니다.",
                ),
            ),
        ),
    ),
    "03-data": (
        Example(
            "데이터가 바뀌면 덮어쓰지 않고 새 버전으로",
            "demo/pipeline.py",
            "def register_assets(ml: MLClient) -> None:",
            "def register_components(ml: MLClient) -> None:",
            (
                (
                    'for version, rows, seed in [("1", 1500, 42), ("2", 1800, 43)]:',
                    "v1·v2는 행 수와 seed가 다른 별도 데이터입니다.",
                ),
                (
                    'name="telco-churn",',
                    "URI_FILE 자산에 이름·버전·파일 경로를 등록합니다. "
                    "로컬 파일 등록에는 업로드가 발생합니다.",
                ),
                (
                    "type=AssetTypes.MLTABLE,",
                    "MLTable은 경로와 읽기 규칙을 함께 담습니다. 단순 파일 자산과 구분합니다.",
                ),
            ),
        ),
    ),
    "04-pipelines": (
        Example(
            "Pipeline = 독립 실행 가능한 ML 워크플로",
            "demo/pipeline.py",
            "def run_pipelines(ml: MLClient) -> None:",
            "for version, job in enumerate(jobs, start=1):",
            (
                (
                    'prep = ml.components.get("prepare_telco_data", version=TRAIN_VERSION)',
                    "준비·학습 Component의 등록 버전을 고정합니다.",
                ),
                (
                    'return {"model": trained.outputs.model}',
                    "준비 출력 → 학습 입력 → 모델 출력의 연결이 graph가 됩니다.",
                ),
                (
                    'data=Input(type=AssetTypes.URI_FILE, path="azureml:telco-churn:1"), '
                    "algorithm=algorithm",
                    "두 알고리즘이 같은 Data v1을 사용합니다.",
                ),
                (
                    'job = ml.jobs.create_or_update(pipeline, experiment_name="kt-telco-churn")',
                    "Job을 Experiment에 제출합니다. 서빙은 이 graph에 포함하지 않습니다.",
                ),
            ),
        ),
    ),
    "05-mlflow": (
        Example(
            "학습 코드에는 표준 MLflow 몇 줄만 추가",
            "demo/training.py",
            "with mlflow.start_run() as run:",
            "estimator.fit(train_data[FEATURES], train_data.churn)",
            (
                ("with mlflow.start_run() as run:", "한 번의 학습을 run으로 묶습니다."),
                (
                    "mlflow.log_params(",
                    "알고리즘·데이터 버전·seed·분할 조건을 파라미터로 남깁니다.",
                ),
                (
                    'mlflow.set_tags({"scenario": "synthetic-telco-churn", '
                    '"data_classification": "synthetic"})',
                    "태그는 실험의 맥락과 검색 조건입니다. 권한 경계는 아닙니다.",
                ),
            ),
        ),
        Example(
            "차이가 작으면 더 좋은 모델이라고 판단하지 않음",
            "demo/training.py",
            "predicted = estimator.predict(test_data[FEATURES])",
            "example = train_data[FEATURES].head(3)",
            (
                (
                    "probability = estimator.predict_proba(test_data[FEATURES])[:, 1]",
                    "ROC AUC에는 이진 분류 모델의 점수를 사용합니다.",
                ),
                (
                    "mlflow.log_metrics(metrics)",
                    "동일 holdout에서 accuracy·F1·ROC AUC를 비교합니다.",
                ),
                (
                    'mlflow.log_figure(display.figure_, "evaluation/confusion_matrix.png")',
                    "숫자뿐 아니라 confusion matrix도 Artifact로 남깁니다.",
                ),
            ),
        ),
    ),
    "06-models": (
        Example(
            "모델은 파일 하나가 아니라 배포 가능한 패키지",
            "demo/training.py",
            "example = train_data[FEATURES].head(3)",
            'mlflow.log_dict(metrics, "evaluation/metrics.json")',
            (
                (
                    "signature = infer_signature(example, estimator.predict(example))",
                    "입출력 signature와 입력 예제로 모델의 사용 계약을 남깁니다.",
                ),
                ("mlflow.sklearn.log_model(", "추적 run에 MLflow 모델 패키지를 기록합니다."),
                (
                    "mlflow.sklearn.save_model(",
                    "Pipeline 출력 경로에도 패키지를 저장합니다. "
                    "기록과 출력 저장은 다른 호출입니다.",
                ),
            ),
        ),
        Example(
            "등록 = 이름 + 버전 + 출처",
            "demo/pipeline.py",
            "model = ml.models.create_or_update(",
            'LOGGER.info("Registered %s:%s from %s.", model.name, model.version, completed.name)',
            (
                (
                    'name="telco-churn-classifier",',
                    "이름과 명시적 버전으로 모델 후보를 관리합니다.",
                ),
                (
                    'path=f"azureml://jobs/{completed.name}/outputs/model",',
                    "완료된 Job의 모델 출력을 등록해 생성 근거와 연결합니다.",
                ),
                (
                    "type=AssetTypes.MLFLOW_MODEL,",
                    "MLflow 모델과 HF 파일을 담은 CUSTOM_MODEL을 구분합니다.",
                ),
            ),
        ),
    ),
    "07-environments": (
        Example(
            "Environment = 실행 조건의 버전",
            "demo/pipeline.py",
            "env = ml.environments.create_or_update(",
            "prep = command(",
            (
                ("version=TRAIN_VERSION,", "환경 이름뿐 아니라 버전을 지정합니다."),
                ("image=BASE_IMAGE,", "기본 이미지와 의존성 정의가 실행 환경의 기반입니다."),
                (
                    'conda_file=str(ROOT / "environments" / "training.yml"),',
                    "Python·라이브러리 조건을 정의합니다. "
                    "실제 생성 이미지 digest도 함께 확인해야 합니다.",
                ),
            ),
        ),
    ),
    "08-serving": (
        Example(
            "Endpoint: Entra 인증으로 호출하는 주소",
            "demo/endpoint.py",
            "endpoint = ml.online_endpoints.begin_create_or_update(",
            "workspace = ml.workspaces.get(ml.workspace_name)",
            (
                (
                    'auth_mode="aad_token",',
                    "Entra 토큰으로 호출을 인증합니다. public 주소가 익명 호출을 뜻하지 않습니다.",
                ),
                (
                    'public_network_access="enabled",',
                    "이 Endpoint는 public 진입점을 사용합니다. 보호된 Storage 경로와 구분합니다.",
                ),
            ),
        ),
        Example(
            "Hub 모델을 Workspace 자산으로 등록한 뒤 배포",
            "demo/endpoint.py",
            'os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"',
            "env = ml.environments.create_or_update(",
            (
                ("revision=HF_REVISION,", "고정된 Hugging Face commit의 파일만 다운로드합니다."),
                ('"model.safetensors",', "허용한 모델·토크나이저 파일을 명시적으로 선택합니다."),
                (
                    "type=AssetTypes.CUSTOM_MODEL,",
                    "사전학습 파일을 등록합니다. 이 코드는 HF 모델을 추가 학습하지 않습니다.",
                ),
            ),
        ),
        Example(
            "init()은 한 번: 로컬 모델과 기준 문장 준비",
            "demo/serving/score.py",
            "def init() -> None:",
            "def run(raw_data: str):",
            (
                (
                    'root = Path(os.environ["AZUREML_MODEL_DIR"])',
                    "컨테이너에 준비된 등록 모델의 경로를 사용합니다.",
                ),
                (
                    "_tokenizer = AutoTokenizer.from_pretrained("
                    "model_dirs[0], local_files_only=True)",
                    "추론 시작 시 외부 Hub 다운로드 없이 로컬 파일을 읽습니다.",
                ),
                (
                    "model_dirs[0], local_files_only=True, "
                    "use_safetensors=True, trust_remote_code=False",
                    "safetensors를 사용하고 remote code 실행을 허용하지 않습니다.",
                ),
                (
                    "_prototypes = embed(list(CATEGORIES.values()))",
                    "분류 기준 문장의 임베딩도 초기화할 때 준비합니다.",
                ),
            ),
        ),
        Example(
            "입력 검증: 1~16개, 문장당 2,000자 이하",
            "demo/serving/score.py",
            "def parse_request(raw_data: str) -> list[str]:",
            "def embed(texts: list[str]) -> np.ndarray:",
            (
                (
                    'if not isinstance(body, dict) or set(body) != {"texts"}:',
                    "정해진 필드만 받습니다.",
                ),
                (
                    "if not isinstance(texts, list) or not 1 <= len(texts) <= 16:",
                    "빈 배열과 과도한 요청 크기를 거부합니다.",
                ),
                (
                    "if any(not isinstance(text, str) or not text.strip() "
                    "or len(text) > 2000 for text in texts):",
                    "문자열 타입·공백·길이를 검사합니다.",
                ),
            ),
        ),
        Example(
            "run()은 요청마다: 임베딩과 cosine similarity",
            "demo/serving/score.py",
            "def run(raw_data: str):",
            None,
            (
                ("texts = parse_request(raw_data)", "추론 전에 입력 계약을 검증합니다."),
                (
                    'return AMLResponse({"error": str(error)}, 400)',
                    "모델 서버의 잘못된 입력 응답은 400입니다. "
                    "실제 외부 Gateway에서는 424로 관측했습니다.",
                ),
                (
                    "similarities = embed(texts) @ _prototypes.T",
                    "정규화 임베딩의 내적입니다. 보정된 분류 확률이 아닙니다.",
                ),
                (
                    'LOGGER.info("Scored %d tickets in %.3f seconds.", '
                    "len(texts), time.perf_counter() - started)",
                    "문장 원문 없이 요청 수와 소요 시간을 기록합니다.",
                ),
            ),
        ),
        Example(
            "Endpoint는 주소·인증·트래픽, Deployment는 실행 단위",
            "demo/endpoint.py",
            "deployment = ManagedOnlineDeployment(",
            "def verify(ml: MLClient) -> dict:",
            (
                ("model=model.id,", "등록 모델과 Environment 버전으로 실행 대상을 정합니다."),
                (
                    'code=str(ROOT / "demo" / "serving"), scoring_script="score.py"',
                    "컨테이너가 호출할 scoring script를 지정합니다.",
                ),
                ('"HF_HUB_OFFLINE": "1",', "추론 시 오프라인 모델 로딩을 강제합니다."),
                (
                    'endpoint.traffic = {"blue": 100}',
                    "현재 구성은 blue 100%입니다. green·분할 트래픽은 배포하지 않았습니다.",
                ),
            ),
        ),
    ),
    "09-external": (
        Example(
            "학습은 어디서 하든, 기록과 모델 관리는 한 Workspace로",
            "demo/pipeline.py",
            "def external_tracking(ml: MLClient) -> None:",
            None,
            (
                (
                    "mlflow.set_tracking_uri(workspace.mlflow_tracking_uri)",
                    "실험을 보낼 AML tracking URI를 설정합니다.",
                ),
                (
                    'metrics = train(folder / "prepared", folder / "model", '
                    '"logistic", data_version="2")',
                    "같은 학습 함수를 외부 PC CPU에서 실행합니다. "
                    "클라우드 v1과 평가 조건은 다릅니다.",
                ),
                (
                    'registered = mlflow.register_model(f"runs:/{run.info.run_id}/model", '
                    '"telco-churn-external")',
                    "외부 run의 모델을 등록합니다. "
                    "Slurm Job·관리형 Pipeline 통합을 자동 생성하지 않습니다.",
                ),
            ),
        ),
    ),
    "10-operations": (
        Example(
            "모델은 공유, 데이터 권한은 팀 안에서",
            "demo/registry_probe/probe.py",
            "own = requests.get(args.own_blob, headers=headers, timeout=60)",
            "report = {",
            (
                (
                    "own.raise_for_status()",
                    "실제 Compute identity로 자기 Storage 접근 성공을 확인합니다.",
                ),
                (
                    "peer = requests.get(args.peer_blob, headers=headers, timeout=60)",
                    "다른 팀 Storage에도 같은 실행 주체로 요청합니다.",
                ),
                (
                    '"AuthorizationPermissionMismatch"',
                    "단순 네트워크 오류가 아니라 명시적인 RBAC 거부 403을 요구합니다.",
                ),
            ),
        ),
        Example(
            "Compute는 유휴 시 0대, 상시 비용은 별도",
            "demo/workspace.py",
            "def create_compute(ml: MLClient) -> None:",
            None,
            (
                (
                    "min_instances=0,",
                    "기존 검증 Workspace의 학습 Compute는 유휴 시 0대로 축소합니다.",
                ),
                (
                    "max_instances=2,",
                    "이 클러스터의 최대 노드 수는 2입니다. 새 팀의 최대 1대 설정과 구분합니다.",
                ),
                (
                    "idle_time_before_scale_down=120,",
                    "Compute 축소 후에도 Endpoint·ACR·네트워크·Storage 비용은 남습니다.",
                ),
            ),
        ),
    ),
    "11-workflow": (
        Example(
            "검증 자동화와 모델 운영 자동화는 다름",
            ".github/workflows/ci.yml",
            "name: Validate demo",
            None,
            (
                (
                    "- run: uv run --no-sync pytest -q",
                    "CI는 코드의 테스트를 실행합니다. Azure 학습 Job을 제출하지 않습니다.",
                ),
                (
                    "- run: az bicep build --file infra/main.bicep --stdout > /dev/null",
                    "Bicep 컴파일 검사입니다. 인프라 배포가 아닙니다.",
                ),
                (
                    "workflow_dispatch:",
                    "수동 CI 실행도 같은 검증입니다. 모델 승인·승격·롤백은 별도 구현 대상입니다.",
                ),
            ),
        ),
    ),
}

MESSAGES = {
    "01-overview": "DevOps가 기반, MLOps는 데이터·실험·모델을 추가",
    "02-architecture": "Workspace = 협업·권한·추적의 경계",
    "03-data": "Job은 이름:버전을 보고, 데이터는 Storage에서 읽음",
    "04-pipelines": "Pipeline = 독립 실행 가능한 ML 워크플로",
    "05-mlflow": "Workspace → Experiment → Run",
    "06-models": "모델은 파일 하나가 아니라 배포 가능한 패키지",
    "07-environments": "Environment = 실행 조건의 버전",
    "08-serving": "init()은 한 번, run()은 요청마다",
    "09-external": "학습은 어디서 하든, 기록과 모델 관리는 한 Workspace로",
    "10-operations": "모델은 공유, 데이터 권한·네트워크는 팀 안에서",
    "11-workflow": "Track · Version · Serve",
}


def marker_line(lines: list[str], marker: str, path: str) -> int:
    matches = [index for index, line in enumerate(lines) if line.strip() == marker]
    if len(matches) != 1:
        raise ValueError(f"Expected one source marker in {path}, found {len(matches)}: {marker}")
    return matches[0]


def read_excerpt(root: Path, example: Example) -> tuple[str, int, int]:
    lines = (root / example.path).read_text(encoding="utf-8").splitlines()
    start = marker_line(lines, example.start, example.path)
    stop = marker_line(lines, example.stop, example.path) if example.stop else len(lines)
    if stop <= start:
        raise ValueError(f"Reversed source markers in {example.path}: {example.title}")
    while not lines[stop - 1].strip():
        stop -= 1
    return dedent("\n".join(lines[start:stop])), start + 1, stop


def render_examples(root: Path, slug: str, revision: str = "main") -> str:
    if revision != "main" and not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Source revision must be main or a full commit SHA")
    cards = []
    for example in EXAMPLES[slug]:
        code, start, stop = read_excerpt(root, example)
        notes = [
            (marker_line(code.splitlines(), anchor, example.path), text)
            for anchor, text in example.notes
        ]
        highlights = " ".join(str(index + 1) for index, _ in notes)
        language = {".py": "python", ".yml": "yaml", ".bicep": "bicep"}[Path(example.path).suffix]
        url = (
            f"https://github.com/daeungo1/azure-llm-mlops/blob/{revision}/"
            f"{quote(example.path, safe='/')}#L{start}-L{stop}"
        )
        commentary = "\n\n".join(
            f"- [`L{start + index}`]({url.split('#')[0]}#L{start + index}) · {text}"
            for index, text in notes
        )
        cards.append(
            f"### {example.title}\n\n"
            f"[{example.path} · L{start}–L{stop}]({url})\n\n"
            '<div class="code-layout" markdown>\n\n'
            '<div class="code-source" markdown>\n\n'
            f'```{language} linenums="{start}" hl_lines="{highlights}"\n{code}\n```\n\n'
            '</div>\n\n<div class="code-notes" markdown>\n\n'
            f"**코드 해설**\n\n{commentary}\n\n</div>\n\n</div>"
        )
    return "\n\n".join(cards)
