import hashlib
import importlib
import re
import shutil
from pathlib import Path
from textwrap import dedent

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
CODE_FILES = (
    "demo/pipeline.py",
    "demo/training.py",
    "demo/endpoint.py",
    "demo/serving/score.py",
    "demo/workspace.py",
    "demo/multiteam.py",
    "demo/registry_probe/probe.py",
    "infra/main.bicep",
    ".github/workflows/ci.yml",
)


def test_generator_is_available():
    assert (ROOT / "scripts" / "build_session_site.py").is_file(), "Site generator is missing"


def test_stylesheet_url_changes_with_content():
    css = (ROOT / "docs" / "stylesheets" / "session.css").read_text(encoding="utf-8")
    digest = hashlib.sha256(css.encode("utf-8")).hexdigest()[:12]
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert f"  - stylesheets/session.css?v={digest}\n" in config, (
        "Update the stylesheet URL content digest to invalidate browser and CDN caches"
    )


@pytest.fixture
def site_builder():
    return importlib.import_module("scripts.build_session_site")


@pytest.fixture
def source_tree(tmp_path, site_builder):
    sources = ["README.md", *site_builder.PUBLIC_FILES, *CODE_FILES]
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


def test_session_content_has_no_document_production_notes():
    sources = [
        "docs/session-home.md",
        "docs/appendix-discussion.md",
        *[f"docs/images/ktc-case/{name}" for name in CASE_FIGURES],
    ]
    for source in sources:
        content = (ROOT / source).read_text(encoding="utf-8")
        for phrase in ("원문", "공개를 허용", "일반화했", "SVG 7개", "Appendix SVG"):
            assert phrase not in content, f"Production note in {source}: {phrase}"


def test_core_examples_are_short_commented_source_below_concepts(site_builder, source_tree):
    before = {name: (source_tree / name).read_bytes() for name in CODE_FILES}
    output = site_builder.build_source(source_tree)
    for chapter in site_builder.CHAPTERS:
        content = (output / f"{chapter.slug}.md").read_text(encoding="utf-8")
        assert '=== "' not in content, chapter.slug
        assert 'class="code-notes"' not in content
        links = re.findall(r"\[([^\s]+) · L(\d+)–L(\d+)\]\((https://github.com/[^)]+)\)", content)
        blocks = re.findall(
            r'```\w+ linenums="(\d+)" hl_lines="[\d ]+"\n(.*?)\n\s*```', content, re.DOTALL
        )
        assert len(links) == len(blocks), chapter.slug
        assert len(blocks) <= (2 if chapter.slug == "08-serving" else 1)
        if chapter.slug in {"01-overview", "02-architecture", "10-operations", "11-workflow"}:
            assert not blocks
        else:
            assert blocks
            assert content.index("## 핵심 코드") > content.index(f"images/{chapter.diagram}")
        for (path, start, end, url), (first, code) in zip(links, blocks, strict=True):
            assert f"#L{start}-L{end}" in url
            assert first == start
            assert 4 <= int(end) - int(start) + 1 <= 12
            assert "  # " in code
            without_comments = "\n".join(line.partition("  # ")[0] for line in code.splitlines())
            actual = (source_tree / path).read_text(encoding="utf-8").splitlines()
            assert dedent(without_comments).rstrip() == dedent(
                "\n".join(actual[int(start) - 1 : int(end)])
            )
    assert before == {name: (source_tree / name).read_bytes() for name in CODE_FILES}


def test_changed_source_marker_blocks_site_build(site_builder, source_tree):
    score = source_tree / "demo" / "serving" / "score.py"
    score.write_text(
        score.read_text(encoding="utf-8").replace(
            "_model = AutoModel.from_pretrained(", "_model = renamed_loader("
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="marker"):
        site_builder.build_source(source_tree)


def test_source_links_are_pinned_to_build_commit(site_builder, source_tree):
    revision = "a" * 40
    output = site_builder.build_source(source_tree, revision=revision)
    for chapter in site_builder.CHAPTERS:
        content = (output / f"{chapter.slug}.md").read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+ · L\d+–L\d+\]\(([^)]+)\)", content)
        assert all(f"/blob/{revision}/" in link for link in links)


def test_navigation_and_page_numbers_follow_topic_order(site_builder, source_tree):
    output = site_builder.build_source(source_tree)
    home = (output / "index.md").read_text(encoding="utf-8")
    navigation = (ROOT / "mkdocs.yml").read_text(encoding="utf-8").split("nav:", 1)[1]
    slugs = [site_builder.CHAPTERS[number - 1].slug for number in site_builder.CHAPTER_ORDER]
    assert [home.index(f"({slug}.md)") for slug in slugs] == sorted(
        home.index(f"({slug}.md)") for slug in slugs
    )
    assert [navigation.index(f"{slug}.md") for slug in slugs] == sorted(
        navigation.index(f"{slug}.md") for slug in slugs
    )
    for position, slug in enumerate(slugs, 1):
        content = (output / f"{slug}.md").read_text(encoding="utf-8")
        assert f'title: "{position}. ' in content


def test_duplicate_source_marker_blocks_site_build(site_builder, source_tree):
    score = source_tree / "demo" / "serving" / "score.py"
    score.write_text(
        score.read_text(encoding="utf-8") + "\n_model = AutoModel.from_pretrained(\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="found 2"):
        site_builder.build_source(source_tree)


def test_invalid_source_revision_is_rejected(site_builder, source_tree):
    with pytest.raises(ValueError, match="revision"):
        site_builder.build_source(source_tree, revision="../private")


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
