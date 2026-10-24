"""Coverage telemetry must never consume the job budget."""
from unittest.mock import patch

from src.inventory_service import run_cycle


def test_coverage_metrics_do_not_consume_acquisition_slots():
    batches = [
        {'completed': 1, 'failed': 0, 'pages_fetched': 10,
         'listings_extracted': 150, 'listings_unpersisted': 5,
         'traversals_pending': 1},
        {'completed': 1, 'failed': 0, 'pages_fetched': 2,
         'listings_extracted': 20, 'listings_unpersisted': 0,
         'traversals_pending': 0},
    ]
    with patch('src.inventory_service.schedule_refreshes', return_value=3), \
         patch('src.inventory_service.run_batch', side_effect=batches) as worker, \
         patch('src.inventory_service.renew_listings', return_value={'expired': 0}):
        result = run_cycle(2)
    assert worker.call_count == 2
    assert result['completed'] == 2
    assert result['pages_fetched'] == 12
    assert result['listings_extracted'] == 170
    assert result['listings_unpersisted'] == 5
    assert result['traversals_pending'] == 1
