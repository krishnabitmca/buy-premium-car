from datetime import datetime,timedelta,timezone
from src.coverage_operations import summarize,markdown_report

NOW=datetime(2026,10,18,tzinfo=timezone.utc)


def source(**kwargs):
    return dict(source='A',url='https://fixture.invalid/catalog',enabled=True,verified=True,
        adapter_status='live',target_minutes=360,parser='fixture',conditions=['used','demo'],**kwargs)


def fact(n=1,**kwargs):
    row=dict(source='A',url='https://fixture.invalid/car/'+str(n),status='active',listing_condition='used',
        condition='used',brand='BMW',model='X5',seller_location_label='Delhi',vehicle_id='vehicle-1',
        price_basis='unspecified',last_verified_at=NOW-timedelta(hours=8),eligible=True,
        renewal_status='queued',due_at=NOW-timedelta(hours=2),last_outcome=None)
    row.update(kwargs);return row


def test_sparse_matrix_deduplicates_vehicles_and_keeps_unknown_location_and_coverage():
    result=summarize([fact(),fact(2),fact(3,eligible=False,seller_location_label=None)],
        [source()],[],[],now=NOW)
    cells=result['coverage_matrix']
    delhi=next(r for r in cells if r['seller_location_label']=='Delhi')
    assert delhi['eligible_offers']==2 and delhi['eligible_vehicles']==1
    missing=next(r for r in cells if r['seller_location_label'] is None)
    assert missing['status']=='no_current_eligible_observation'
    assert all(r['market_coverage_percent'] is None for r in cells)
    assert len(cells)==2 and not result['complete_market_coverage']


def test_capacity_distinguishes_overdue_policy_from_retry_ready_and_unknown_classification():
    result=summarize([fact(due_at=NOW+timedelta(hours=1)),fact(2,listing_condition='unknown',condition='unknown')],
        [source()],[],[],now=NOW)
    used=result['capacity']['conditions'][0]
    assert used['renewable_offers']==1 and used['overdue_offers']==1 and used['ready_jobs']==0
    assert used['individual_check_demand_per_hour']==0.17 and used['reserved_attempt_capacity_per_hour']==20
    assert result['source_priorities'][0]['needs_classification']==1
    assert 'purchase recommendation' in ' '.join(result['capacity']['assumptions'])


def test_catalogue_urls_shared_stock_and_cross_origin_do_not_inflate_individual_demand():
    rows=[fact(url='https://fixture.invalid/catalog'),fact(2,url='https://fixture.invalid/shared'),
        fact(3,url='https://fixture.invalid/shared'),fact(4,url='https://unapproved.invalid/car')]
    result=summarize(rows,[source()],[],[],now=NOW)
    assert result['capacity']['conditions'][0]['renewable_offers']==0
    assert result['source_priorities'][0]['catalogue_or_origin_review_only']==4


def test_source_targets_are_stricter_than_default_and_zero_slot_scenario_is_explicit():
    configured=source();configured['target_minutes']=30
    result=summarize([fact()],[configured],[],[],now=NOW,renewal_limit=1)
    used=result['capacity']['conditions'][0]
    assert used['individual_check_demand_per_hour']==2
    assert used['reserved_attempt_capacity_per_hour']==0
    assert used['minimum_backlog_hours_at_reserved_budget'] is None


def test_advertised_scopes_and_counts_never_become_market_completeness_or_city_completion():
    jobs=[dict(source='A',brand='',model='',condition='both',status='queued',started_at=NOW,
        completed_at=NOW,last_error=None,continuation={'visited_urls':['https://fixture.invalid/delhi']},
        scan_evidence={'coverage_state':'partial_traversal','pending_page_count':2,'pages_this_batch':2,
            'listings_this_batch':40,'advertised_counts':{'https://fixture.invalid/delhi':100},
            'catalog_scopes':[{'url':'https://fixture.invalid/delhi','kind':'city','label':'Delhi'},
                {'url':'https://fixture.invalid/pune','kind':'city','label':'Pune'}]})]
    result=summarize([], [source()],jobs,[],now=NOW)
    city=[r for r in result['declared_scopes'] if r['scope_kind']=='city']
    assert city[0]['traversal_status']=='page_visited_completeness_unknown'
    assert city[0]['advertised_count']==100 and not city[0]['advertised_count_is_verified_stock']
    assert city[1]['traversal_status']=='discovered_unvisited'
    priority=result['source_priorities'][0]
    assert priority['last_batch_yield']['offers_per_page']==20
    assert 'resume_advertised_catalogues' in priority['actions']
    assert 'No market-wide percentage' in markdown_report(result)


def test_no_batch_page_measurement_means_no_invented_yield_and_recorded_runs_are_not_scheduler_sla():
    jobs=[dict(source='A',brand='BMW',model='X5',condition='demo',status='failed',started_at=NOW,
        last_error='blocked',scan_evidence={'visited_page_count':30,'listings_this_batch':40})]
    configured=source();configured['conditions']=['used']
    runs=[dict(started_at=NOW-timedelta(seconds=12),completed_at=NOW,summary={'inconclusive':3,'available':1})]
    result=summarize([], [configured],jobs,runs,now=NOW)
    assert result['source_priorities'][0]['last_batch_yield'] is None
    assert result['declared_scopes'][1]['traversal_status']=='condition_not_declared'
    assert result['declared_scopes'][1]['job_status']=='failed'
    assert result['declared_scopes'][1]['last_attempt_failed']
    assert result['capacity']['recorded_outcomes_last24h']['inconclusive']==3
    assert result['capacity']['mean_completed_run_seconds']==12


def test_disabled_or_unverified_sources_do_not_create_renewal_capacity_demand():
    configured=source();configured['verified']=False
    result=summarize([fact(eligible=False)],[configured],[],[],now=NOW)
    assert result['capacity']['conditions'][0]['renewable_offers']==0
    assert 'review_adapter_or_provider_feed' in result['source_priorities'][0]['actions']


def test_failed_attempt_cannot_retimestamp_previous_successful_batch():
    measured=NOW-timedelta(days=1)
    jobs=[dict(source='A',brand='',model='',condition='both',status='failed',started_at=NOW,
        completed_at=NOW,last_error='failed latest attempt',batch_observed_at=measured.isoformat(),
        scan_evidence={'coverage_state':'partial_traversal','pages_this_batch':2,'listings_this_batch':40})]
    result=summarize([], [source()],jobs,[],now=NOW)
    assert result['source_priorities'][0]['last_batch_yield']['measured_at']==measured.isoformat()
    assert result['declared_scopes'][1]['traversal_status']=='partial_traversal'
    assert result['declared_scopes'][1]['last_attempt_failed']


def test_case_variant_scope_duplicates_report_the_latest_attempt():
    old=dict(source='A',brand='bmw',model='x5',condition='used',status='failed',
        started_at=NOW-timedelta(days=1),last_error='old failure')
    new={**old,'brand':'BMW','model':'X5','started_at':NOW,'status':'completed','last_error':None}
    result=summarize([], [source()],[old,new],[],now=NOW)
    scopes=[r for r in result['declared_scopes'] if r['scope_kind']=='model']
    assert len(scopes)==1 and scopes[0]['job_status']=='completed' and not scopes[0]['last_attempt_failed']
