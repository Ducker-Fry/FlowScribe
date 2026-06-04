from pathlib import Path


def test_release_workflow_uses_create_or_update_release_flow() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "Inspect GitHub release state" in workflow
    assert "Create GitHub release record" in workflow
    assert "Update GitHub release metadata" in workflow
    assert "Upload or overwrite release assets" in workflow
    assert "--clobber" in workflow
    assert "Verify release tag checkout" in workflow
    assert "doctor -o release-smoke-test --model small --skip-model-access" in workflow


def test_release_docs_match_create_or_update_behavior() -> None:
    release_docs = Path("docs/release-automation.md").read_text(encoding="utf-8")
    packaging_docs = Path("docs/packaging.md").read_text(encoding="utf-8")

    assert "create-or-update" in release_docs
    assert "upload --clobber" in release_docs
    assert "create-or-update" in packaging_docs
    assert "updates the existing" in packaging_docs
    assert "release metadata" in packaging_docs
    assert "--skip-model-access" in release_docs
    assert "--skip-model-access" in packaging_docs
