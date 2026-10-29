"""Render short source-linked reference examples with explanatory comments."""

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
    lines: int
    notes: tuple[tuple[str, str], ...]
    before: int = 0


EXAMPLES = {
    "03-data": (
        Example(
            "데이터에 이름과 버전 부여",
            "demo/pipeline.py",
            'name="telco-churn",',
            10,
            (
                ("version=version,", "변경된 데이터는 새 버전으로 등록"),
                ('path=str(folder / "telco.csv"),', "이 로컬 파일은 Storage에 업로드"),
            ),
            before=2,
        ),
    ),
    "04-pipelines": (
        Example(
            "준비 출력과 학습 입력 연결",
            "demo/pipeline.py",
            "def telco_pipeline(data, algorithm: str):",
            6,
            (
                ("prepared = prep(data=data)", "데이터 준비 단계"),
                ('return {"model": trained.outputs.model}', "학습 모델을 Pipeline 출력으로 연결"),
            ),
        ),
    ),
    "05-mlflow": (
        Example(
            "Train Run에 Metrics·Artifacts 기록",
            "demo/training.py",
            "metrics = {",
            8,
            (
                ("mlflow.log_metrics(metrics)", "동일 평가 조건의 Metrics를 Run에 기록"),
                (
                    'mlflow.log_figure(display.figure_, "evaluation/confusion_matrix.png")',
                    "오류 분포도 함께 보관",
                ),
            ),
        ),
    ),
    "06-models": (
        Example(
            "signature와 입력 예제를 포함한 모델 패키지",
            "demo/training.py",
            "example = train_data[FEATURES].head(3)",
            5,
            (
                (
                    "signature = infer_signature(example, estimator.predict(example))",
                    "입출력 계약",
                ),
                ("mlflow.sklearn.log_model(", "모델·환경·signature·예제를 기록"),
            ),
        ),
    ),
    "07-environments": (
        Example(
            "기본 이미지와 의존성을 버전으로 관리",
            "demo/pipeline.py",
            "env = ml.environments.create_or_update(",
            9,
            (
                ("version=TRAIN_VERSION,", "환경 버전 고정"),
                ("image=BASE_IMAGE,", "기본 컨테이너 이미지"),
                (
                    'conda_file=str(ROOT / "environments" / "training.yml"),',
                    "Python·라이브러리 조건",
                ),
            ),
        ),
    ),
    "08-serving": (
        Example(
            "init(): 컨테이너 시작 시 모델 로딩",
            "demo/serving/score.py",
            "_model = AutoModel.from_pretrained(",
            5,
            (
                ("_model = AutoModel.from_pretrained(", "등록된 로컬 모델 사용"),
                (").eval()", "추론 모드로 전환"),
                ("_prototypes = embed(list(CATEGORIES.values()))", "기준 문장도 한 번만 임베딩"),
            ),
            before=1,
        ),
        Example(
            "run(): 요청 검증과 유사도 계산",
            "demo/serving/score.py",
            "def run(raw_data: str):",
            10,
            (
                ("texts = parse_request(raw_data)", "1~16개, 문장당 2,000자 이하"),
                ('return AMLResponse({"error": str(error)}, 400)', "잘못된 입력은 거부"),
                (
                    "similarities = embed(texts) @ _prototypes.T",
                    "cosine similarity, 보정 확률 아님",
                ),
            ),
        ),
    ),
    "09-external": (
        Example(
            "외부 학습의 기록 목적지를 AML로 지정",
            "demo/pipeline.py",
            "def external_tracking(ml: MLClient) -> None:",
            4,
            (
                (
                    "mlflow.set_tracking_uri(workspace.mlflow_tracking_uri)",
                    "연산은 PC, 기록은 AML",
                ),
                ('mlflow.set_experiment("kt-external-mlflow")', "외부 run을 별도 실험으로 관리"),
            ),
        ),
    ),
}

MESSAGES = {
    "01-overview": "DevOps가 기반, MLOps는 데이터·실험·모델을 추가",
    "02-architecture": "Workspace = 협업·권한·추적의 경계",
    "03-data": "Job은 이름:버전을 보고, 데이터는 Storage에서 읽음",
    "04-pipelines": "Pipeline = 독립 실행 가능한 ML Workflow",
    "05-mlflow": "Experiment로 묶고, Job으로 실행하고, MLflow로 근거를 기록",
    "06-models": "모델은 파일 하나가 아니라 배포 가능한 패키지",
    "07-environments": "Environment = 실행 조건의 버전",
    "08-serving": "init()은 한 번, run()은 요청마다",
    "09-external": "학습은 어디서 하든, 기록과 모델 관리는 한 Workspace로",
    "10-operations": "권한·서비스 상태·비용을 관리하고 Private 구성도 지원",
    "11-workflow": "Track · Version · Serve",
}


def marker_line(lines: list[str], marker: str, path: str) -> int:
    matches = [index for index, line in enumerate(lines) if line.strip() == marker]
    if len(matches) != 1:
        raise ValueError(f"Expected one source marker in {path}, found {len(matches)}: {marker}")
    return matches[0]


def render_examples(root: Path, slug: str, revision: str = "main") -> str:
    if revision != "main" and not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Source revision must be main or a full commit SHA")
    cards = []
    for example in EXAMPLES.get(slug, ()):
        lines = (root / example.path).read_text(encoding="utf-8").splitlines()
        start = marker_line(lines, example.start, example.path) - example.before
        stop = start + example.lines
        if start < 0 or stop > len(lines) or not 4 <= example.lines <= 12:
            raise ValueError(f"Invalid excerpt range in {example.path}: {example.title}")
        code = dedent("\n".join(lines[start:stop])).splitlines()
        highlights = []
        for marker, comment in example.notes:
            index = marker_line(code, marker, example.path)
            code[index] += f"  # {comment}"
            highlights.append(str(index + 1))
        url = (
            f"https://github.com/daeungo1/azure-llm-mlops/blob/{revision}/"
            f"{quote(example.path, safe='/')}#L{start + 1}-L{stop}"
        )
        cards.append(
            f"### {example.title}\n\n"
            '<div class="code-source" markdown>\n\n'
            f'```python linenums="{start + 1}" hl_lines="{" ".join(highlights)}"\n'
            + "\n".join(code)
            + "\n```\n\n</div>\n\n"
            f"[{example.path} · L{start + 1}–L{stop}]({url})"
        )
    return "## 핵심 코드\n\n" + "\n\n".join(cards) if cards else ""
