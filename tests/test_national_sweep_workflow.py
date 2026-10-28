"""National inventory sweep must not silently write to a test database."""
from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/national-inventory-sweep.yml")


def test_national_sweep_requires_canonical_inventory_database():
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    job = workflow["jobs"]["sweep"]
    assert job["env"]["SOURCE_INTELLIGENCE_DATABASE_URL"] == (
        "${{ secrets.SOURCE_INTELLIGENCE_DATABASE_URL }}"
    )
    assert "CARSCANNER_FREE_TEST_DATABASE_URL" not in text

    schedule = next(
        step for step in job["steps"]
        if step.get("name") == "Schedule every supported make"
    )
    commands = schedule["run"].strip().splitlines()
    assert commands[0].strip() == 'test -n "$SOURCE_INTELLIGENCE_DATABASE_URL"'
    assert "src.source_runtime_config" in commands[1]
    assert "src.inventory_refresh_planner" in commands[2]


def test_national_sweep_keeps_bounded_worker_and_coverage_audit():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["sweep"]
    assert job["timeout-minutes"] == 45
    assert workflow["concurrency"]["cancel-in-progress"] is False

    worker = next(
        step for step in job["steps"]
        if step.get("name") == "Sweep reviewed national marketplace adapters"
    )
    assert "--baseline-only" in worker["run"]
    assert "--limit 100" in worker["run"]

    coverage = next(
        step for step in job["steps"]
        if step.get("name") == "Audit used and demo coverage across every make"
    )
    assert coverage["if"] == "always()"
