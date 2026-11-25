"""The fast operations audit must not imply used/demo coverage was checked."""
from src.inventory_coverage import cli_summary


def _report(brands=None):
    report = {'coverage_matrix': [{}], 'declared_scopes': [{}, {}]}
    if brands is not None:
        report['brands'] = brands
    return report


def _brand(name, used, demo):
    return {'brand': name, 'conditions': {
        'used': {'indexed_results': used},
        'demo': {'indexed_results': demo},
    }}


def test_operations_only_does_not_report_empty_used_demo_gaps():
    result = cli_summary(_report(), operations_only=True)
    assert result['brands_checked'] == 0
    assert result['brand_coverage_evaluated'] is False
    assert result['used_coverage_gaps'] is None
    assert result['demo_coverage_gaps'] is None
    assert result['matrix_cells'] == 1
    assert result['declared_scopes'] == 2


def test_full_audit_reports_real_condition_gaps():
    report = _report([_brand('BMW', 4, 0), _brand('Audi', 0, 2)])
    result = cli_summary(report)
    assert result['brand_coverage_evaluated'] is True
    assert result['brands_checked'] == 2
    assert result['used_coverage_gaps'] == ['Audi']
    assert result['demo_coverage_gaps'] == ['BMW']


def test_full_audit_with_no_brands_is_unmeasured_not_clean():
    result = cli_summary(_report([]))
    assert result['brand_coverage_evaluated'] is False
    assert result['used_coverage_gaps'] is None
    assert result['demo_coverage_gaps'] is None


def test_full_audit_with_eligible_used_and_demo_has_no_gaps():
    result = cli_summary(_report([_brand('BMW', 1, 2)]))
    assert result['brand_coverage_evaluated'] is True
    assert result['used_coverage_gaps'] == []
    assert result['demo_coverage_gaps'] == []
