import importlib
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_generator_is_available():
    assert (ROOT / "scripts" / "build_session_site.py").is_file(), "Site generator is missing"


@pytest.fixture
def site_builder():
    return importlib.import_module("scripts.build_session_site")


@pytest.fixture
def source_tree(tmp_path, site_builder):
    sources = [
        "README.md",
        "docs/session-home.md",
        "docs/session-guide.md",
        "docs/deployment-status.md",
        "docs/stylesheets/session.css",
        *[f"docs/images/{name}" for name in site_builder.SVG_FILES],
    ]
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
    private.parent.mkdir()
    private.write_text("PRIVATE", encoding="utf-8")
    (source_tree / "kt-mlops.pptx").write_bytes(b"PRIVATE")
    site_builder.build_source(source_tree)
    site_builder.build_source(source_tree)
    output = source_tree / ".site-content"
    assert len(list(output.glob("[0-9][0-9]-*.md"))) == 11
    assert {file.name for file in (output / "images").iterdir()} == set(site_builder.SVG_FILES)
    assert not list(output.rglob("*.pptx"))
    assert not list(output.rglob("ktc-case"))
    assert "PRIVATE" not in "\n".join(
        file.read_text(encoding="utf-8") for file in output.rglob("*") if file.is_file()
    )
    assert "[발표자 가이드](session-guide.md)" in (output / "index.md").read_text(encoding="utf-8")
    first = (output / "01-overview.md").read_text(encoding="utf-8")
    assert "images/mlops-overview.svg" in first
    assert "Studio 체크포인트" in first


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
