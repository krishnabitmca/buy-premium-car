from pathlib import Path

import yaml


def test_source_expansion_uses_canonical_production_inventory_database():
    """Scheduled source probes must not silently write into a disposable test DB."""
    workflow_path = Path('.github/workflows/source-expansion.yml')
    workflow_text = workflow_path.read_text(encoding='utf-8')
    workflow = yaml.safe_load(workflow_text)
    steps = workflow['jobs']['discover']['steps']
    probe = next(step for step in steps if step.get('name') == 'Discover and promote validated sources')
    assert probe['env']['SOURCE_INTELLIGENCE_DATABASE_URL'] == '${{ secrets.SOURCE_INTELLIGENCE_DATABASE_URL }}'
    assert 'CARSCANNER_FREE_TEST_DATABASE_URL' not in workflow_text
    assert 'test -n "$SOURCE_INTELLIGENCE_DATABASE_URL"' in probe['run']
    assert 'scripts/discover_and_promote_sources.py' in probe['run']
