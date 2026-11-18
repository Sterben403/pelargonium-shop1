from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_project_documents_exist():
    required = [
        "README.md",
        "docs/project-card.md",
        "docs/decision-log.md",
        "docs/working-agreements.md",
        "docs/release-plan.md",
        "docs/development.md",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    assert not missing, f"Missing required files: {missing}"


def test_working_agreements_include_delivery_rules():
    text = (ROOT / "docs/working-agreements.md").read_text(encoding="utf-8")
    for term in ("Definition of Ready", "Definition of Done", "WIP"):
        assert term in text, f"working-agreements.md must contain {term}"


def test_release_plan_contains_rollback_and_checklist():
    text = (ROOT / "docs/release-plan.md").read_text(encoding="utf-8").lower()
    for term in ("окно релиза", "чек-лист", "откат", "ответствен"):
        assert term in text, f"release-plan.md must contain {term}"


def test_pipeline_checks_code_and_releases_to_production():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for step in ("ruff check", "pytest", "gitleaks", "trivy-action", "docker build", "name: production"):
        assert step in workflow, f"ci.yml must contain {step!r}"


def test_dora_metrics_are_not_entered_by_hand():
    # metrics come only from GitHub Deployments; the old manual release log was removed
    assert not (ROOT / "docs/dora-manual-releases.json").exists()
