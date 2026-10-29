"""Regression tests for source-expansion outcome reporting.

A successful scheduled workflow with zero staged sources is not proof of
increased PAN-India used/demo inventory coverage.
"""
from scripts.discover_and_promote_sources import summarize_probe_outcomes


def test_all_rejected_reports_no_new_sources_without_claiming_coverage():
    rows = [
        {"status": "rejected", "url": "https://dealer.example/used", "error": "HTTP 404"},
        {"status": "rejected", "url": "https://oem.example/demo", "error": "HTTP 429"},
    ]
    summary = summarize_probe_outcomes(rows, selected=2)
    assert summary["outcome"] == "no_sources_staged"
    assert summary["selected_candidates"] == 2
    assert summary["probe_status_counts"]["rejected"] == 2
    assert summary["probe_status_counts"]["staged"] == 0
    assert summary["new_live_sources_verified"] is False
    assert "dealer.example" not in str(summary)
    assert "HTTP 429" not in str(summary)


def test_staged_candidate_is_explicitly_not_a_live_source():
    summary = summarize_probe_outcomes(
        [{"status": "staged"}, {"status": "rejected"}, {"status": "deferred"}],
        selected=3,
    )
    assert summary["outcome"] == "staged_for_review"
    assert summary["probe_status_counts"]["staged"] == 1
    assert summary["probe_status_counts"]["deferred"] == 1
    assert summary["new_live_sources_verified"] is False


def test_no_candidates_is_not_misreported_as_rejection():
    summary = summarize_probe_outcomes([], selected=0)
    assert summary["outcome"] == "no_candidates_selected"
    assert sum(summary["probe_status_counts"].values()) == 0


def test_plan_only_does_not_claim_any_probes_or_new_inventory():
    summary = summarize_probe_outcomes([], selected=8, plan_only=True)
    assert summary["outcome"] == "plan_only"
    assert summary["selected_candidates"] == 8
    assert summary["new_live_sources_verified"] is False


def test_superseded_and_validated_without_staging_are_not_promotions():
    summary = summarize_probe_outcomes(
        [{"status": "superseded"}, {"status": "validated"}], selected=2
    )
    assert summary["outcome"] == "no_sources_staged"
    assert summary["probe_status_counts"]["superseded"] == 1
    assert summary["probe_status_counts"]["validated"] == 1
