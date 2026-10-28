import importlib
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASE_FIGURES = (
    "01-shared-isolation.svg",
    "02-plan-a-architecture.svg",
    "03-plan-a-project-isolation.svg",
    "04-plan-b-architecture.svg",
    "05-plan-b-project-isolation.svg",
    "06-plan-c-architecture.svg",
    "07-plan-c-project-isolation.svg",
)


def test_generator_is_available():
    assert (ROOT / "scripts" / "build_session_site.py").is_file(), "Site generator is missing"


@pytest.fixture
def site_builder():
    return importlib.import_module("scripts.build_session_site")


@pytest.fixture
def source_tree(tmp_path, site_builder):
    sources = ["README.md", *site_builder.PUBLIC_FILES]
    for name in sources:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def test_readme_has_exactly_eleven_illustrated_chapters(site_builder):
    chapters = site_builder.split_chapters((ROOT / "README.md").read_text(encoding="utf-8"))
    assert list(chapters) == list(range(1, 12))
    for number, chapter in enumerate(site_builder.CHAPTERS, 1):
        assert f"docs/images/{chapter.diagram}" in chapters[number][1]


@pytest.mark.parametrize("heading", ["## 5. MLflow:", "## 7. Environments"])
def test_missing_chapter_fails_explicitly(site_builder, heading):
    text = (ROOT / "README.md").read_text(encoding="utf-8").replace(heading, "### Removed")
    with pytest.raises(ValueError, match="1 through 11"):
        site_builder.split_chapters(text)


def test_links_and_github_callouts_are_converted(site_builder):
    text = (
        "[proof](docs/deployment-status.md#확인)\n"
        "[code](demo/pipeline.py)\n"
        "![image](docs/images/mlops-overview.svg)\n\n"
        "> [!WARNING]\n> 모델을 추가 학습하지 않습니다.\n"
    )
    converted = site_builder.public_markdown(Path("README.md"), text)
    assert "(deployment-status.md#확인)" in converted
    assert "(images/mlops-overview.svg)" in converted
    assert "(https://github.com/daeungo1/azure-llm-mlops/blob/main/demo/pipeline.py)" in converted
    assert "!!! warning" in converted
    assert "    모델을 추가 학습하지 않습니다." in converted
    assert "[!WARNING]" not in converted


@pytest.mark.parametrize(
    "target", ["ktc-mlops.md", "docs/images/ktc-case/source.svg", "local/run.json"]
)
def test_unapproved_local_link_is_rejected(site_builder, target):
    with pytest.raises(ValueError, match="Unapproved"):
        site_builder.public_markdown(Path("README.md"), f"[private]({target})")


def test_source_generation_is_repeatable_and_allowlisted(site_builder, source_tree):
    private = source_tree / "docs" / "images" / "ktc-case" / "source.svg"
    private.parent.mkdir(exist_ok=True)
    private.write_text("PRIVATE", encoding="utf-8")
    (source_tree / "kt-mlops.pptx").write_bytes(b"PRIVATE")
    site_builder.build_source(source_tree)
    site_builder.build_source(source_tree)
    output = source_tree / ".site-content"
    assert len(list(output.glob("[0-9][0-9]-*.md"))) == 11
    assert {
        file.relative_to(output / "images").as_posix()
        for file in (output / "images").rglob("*.svg")
    } == set(site_builder.SVG_FILES)
    assert not list(output.rglob("*.pptx"))
    assert not list(output.rglob("source.svg"))
    assert not (output / "ktc-mlops.md").exists()
    assert "PRIVATE" not in "\n".join(
        file.read_text(encoding="utf-8") for file in output.rglob("*") if file.is_file()
    )
    assert not (output / "session-guide.md").exists()
    content = "\n".join(file.read_text(encoding="utf-8") for file in output.rglob("*.md"))
    for removed in ("session-guide.md", "발표자 가이드", "Studio 체크포인트", "발표 당일"):
        assert removed not in content
    first = (output / "01-overview.md").read_text(encoding="utf-8")
    assert "images/mlops-overview.svg" in first


def test_discussion_appendix_includes_only_approved_case_figures(site_builder, source_tree):
    output = site_builder.build_source(source_tree)
    appendix = output / "appendix-discussion.md"
    assert appendix.is_file(), "Discussion appendix must be published"
    content = appendix.read_text(encoding="utf-8")
    for name in CASE_FIGURES:
        target = f"images/ktc-case/{name}"
        assert target in content
        assert (output / target).read_bytes() == (
            ROOT / "docs" / "images" / "ktc-case" / name
        ).read_bytes()
    assert "(appendix-discussion.md)" in (output / "index.md").read_text(encoding="utf-8")
    assert "appendix-discussion.md" in (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "(docs/appendix-discussion.md)" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_starts_with_site_link():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    body = readme.split("---", 2)[2].lstrip()
    assert body.startswith(
        "[Azure ML MLOps 문서 사이트](https://daeungo1.github.io/azure-llm-mlops/)"
    )


def test_workflow_diagram_has_no_presentation_plan():
    svg = (ROOT / "docs" / "images" / "demo-workflow.svg").read_text(encoding="utf-8")
    assert 'id="presentation"' not in svg
    assert "발표" not in svg
    assert "세션 시연" not in svg


def test_unexpected_output_file_blocks_publication(site_builder, source_tree):
    output = source_tree / ".site-content"
    output.mkdir()
    private = output / "private.txt"
    private.write_text("PRIVATE", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected"):
        site_builder.build_source(source_tree)
    assert private.read_text(encoding="utf-8") == "PRIVATE"


def test_missing_approved_diagram_blocks_publication(site_builder, source_tree):
    (source_tree / "docs" / "images" / "mlops-overview.svg").unlink()
    with pytest.raises(FileNotFoundError):
        site_builder.build_source(source_tree)
