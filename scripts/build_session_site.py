"""Generate the public session pages from an explicit source allowlist."""

import json
import posixpath
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


@dataclass(frozen=True)
class Chapter:
    slug: str
    diagram: str
    description: str


CHAPTERS = (
    Chapter(
        "01-overview", "mlops-overview.svg", "DevOps 기반과 데이터·실험·모델 자산의 관리 경계."
    ),
    Chapter(
        "02-architecture", "azure-architecture.svg", "Workspace 연결 리소스, 팀 RG와 공용 Registry."
    ),
    Chapter("03-data", "data-asset-versions.svg", "Storage 연결과 데이터 경로·버전 참조의 차이."),
    Chapter(
        "04-pipelines", "mlops-pipeline.svg", "Prepare·Train Pipeline과 재현 가능한 실행 이력."
    ),
    Chapter(
        "05-mlflow",
        "mlflow-experiment-comparison.svg",
        "동일한 holdout의 파라미터·지표·산출물 비교.",
    ),
    Chapter("06-models", "model-package-lineage.svg", "MLflow 패키지와 원본 Job·등록 모델 버전."),
    Chapter(
        "07-environments", "environment-acr-build.svg", "환경 정의, AML 이미지 빌드와 ACR digest."
    ),
    Chapter(
        "08-serving", "endpoint-request-flow.svg", "Entra 인증, MiniLM CPU Deployment와 응답 코드."
    ),
    Chapter(
        "09-external",
        "external-training-tracking.svg",
        "외부 CPU 연산과 AML 추적·모델 관리 위치 분리.",
    ),
    Chapter(
        "10-operations", "operating-boundaries.svg", "접근 권한·네트워크·요청 관측·팀별 비용 경계."
    ),
    Chapter(
        "11-workflow", "demo-workflow.svg", "코드 검증 CI와 운영자 실행·모델 운영 자동화의 차이."
    ),
)
SVG_FILES = tuple(chapter.diagram for chapter in CHAPTERS) + ("multi-team-architecture.svg",)
PUBLIC_PAGES = {
    "docs/session-home.md": "index.md",
    "docs/deployment-status.md": "deployment-status.md",
}
PUBLIC_FILES = {
    **PUBLIC_PAGES,
    **{f"docs/images/{name}": f"images/{name}" for name in SVG_FILES},
    "docs/stylesheets/session.css": "stylesheets/session.css",
}
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\s)]+)(\))")
HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
GITHUB = "https://github.com/daeungo1/azure-llm-mlops/blob/main/"


def split_chapters(text: str) -> dict[int, tuple[str, str]]:
    headings = list(HEADING.finditer(text))
    if [int(match[1]) for match in headings[:11]] != list(range(1, 12)):
        raise ValueError("README must contain ordered sections 1 through 11")
    chapters = {}
    for index, match in enumerate(headings[:11]):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end() : end].strip()
        if f"docs/images/{CHAPTERS[index].diagram}" not in body:
            raise ValueError(f"Missing approved diagram in section {index + 1}")
        chapters[index + 1] = (f"{match[1]}. {match[2]}", body)
    return chapters


def public_markdown(source: Path, text: str) -> str:
    def replace_link(match: re.Match[str]) -> str:
        href = match[2]
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or href.startswith("#"):
            return match[0]
        target = posixpath.normpath(str(PurePosixPath(source.as_posix()).parent / parsed.path))
        if target in PUBLIC_FILES:
            destination = PUBLIC_FILES[target]
        elif source.as_posix() == "docs/session-home.md" and parsed.path in {
            f"{chapter.slug}.md" for chapter in CHAPTERS
        }:
            destination = parsed.path
        elif target == "README.md":
            destination = GITHUB + "README.md"
        elif PurePosixPath(target).parts[0] in {"demo", "infra", "environments", "tests"}:
            destination = GITHUB + quote(target, safe="/")
        else:
            raise ValueError(f"Unapproved local link in {source}: {href}")
        if parsed.query:
            destination += "?" + parsed.query
        if parsed.fragment:
            destination += "#" + parsed.fragment
        return match[1] + destination + match[3]

    text = LINK.sub(replace_link, text)
    return re.sub(
        r"^> \[!(WARNING|IMPORTANT|NOTE|TIP|CAUTION)\]\n((?:>[^\n]*(?:\n|$))+)",
        lambda match: (
            "!!! "
            + {"WARNING": "warning", "CAUTION": "danger", "TIP": "tip"}.get(match[1], "note")
            + "\n"
            + "".join(
                "    " + line.removeprefix(">").removeprefix(" ") + "\n"
                for line in match[2].splitlines()
            )
        ),
        text,
        flags=re.MULTILINE,
    )


def build_source(root: Path) -> Path:
    root = root.resolve()
    output = root / ".site-content"
    if output.is_symlink():
        raise ValueError("Unexpected symlink for generated site directory")
    expected = set(PUBLIC_FILES.values()) | {f"{chapter.slug}.md" for chapter in CHAPTERS}
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink() or (
                path.is_file() and path.relative_to(output).as_posix() not in expected
            ):
                raise ValueError(
                    f"Unexpected generated-site entry; review before publishing: {path}"
                )
    chapters = split_chapters((root / "README.md").read_text(encoding="utf-8"))
    for source in PUBLIC_FILES:
        if not (root / source).is_file():
            raise FileNotFoundError(f"Missing approved site source: {source}")
    for source, target in PUBLIC_FILES.items():
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.endswith(".md"):
            text = public_markdown(Path(source), (root / source).read_text(encoding="utf-8"))
            if target == "index.md":
                cards = "\n\n".join(
                    f"- **[{title}]({chapter.slug}.md)**\n\n    {chapter.description}"
                    for chapter, (title, _) in zip(CHAPTERS, chapters.values(), strict=True)
                )
                text = text.replace("<!-- SESSION_CHAPTERS -->", cards)
            destination.write_text(text, encoding="utf-8")
        else:
            shutil.copyfile(root / source, destination)
    for number, chapter in enumerate(CHAPTERS, 1):
        title, body = chapters[number]
        body = re.sub(r"^(#{3,6}) ", lambda match: match[1][1:] + " ", body, flags=re.MULTILINE)
        text = (
            f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\n"
            f"description: {json.dumps(chapter.description, ensure_ascii=False)}\n---\n\n"
        )
        text += public_markdown(Path("README.md"), body)
        (output / f"{chapter.slug}.md").write_text(text, encoding="utf-8")
    return output


def main() -> int:
    destination = build_source(Path(__file__).resolve().parents[1])
    print(f"Generated 11 public chapters and allowlisted assets: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
