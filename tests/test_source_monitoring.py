from src.source_monitoring import crawl_queue, registered_candidates, merge_candidates
from src.source_intelligence import load_source_registry
from src.source_monitoring import plan_probes
from datetime import datetime, timedelta, timezone


def test_crawl_includes_distinct_inventory_endpoints_not_disabled_or_duplicates():
    source = {'name':'Dealer','url':'https://dealer.in/', 'endpoints':[{'url':'https://dealer.in/demo'},{'url':'https://dealer.in/'},{'url':'https://dealer.in/off','is_active':False}]}
    assert crawl_queue([source,source,{'name':'Off','url':'https://off.in/','enabled':False}]) == [('Dealer','https://dealer.in/',2),('Dealer','https://dealer.in/demo',2)]


def test_known_candidates_are_probed_without_search_engine_results():
    sources = [{'name':'Demo','url':'https://dealer.in/demo','adapter_status':'candidate','conditions':['demo'],'brands':['BMW']}, {'name':'Used','url':'https://dealer.in/used','adapter_status':'candidate','conditions':['used'],'brands':['all']}]
    probes = registered_candidates(sources)
    assert [p.url for p in merge_candidates(probes,[],.7,120)] == [s['url'] for s in sources]
    assert probes[0].condition == 'demo' and probes[0].brand_hint == 'BMW'
    assert probes[1].brand_hint is None
    assert len(merge_candidates(probes,probes,.7,120)) == 2
    assert len(merge_candidates(probes,[],.7,1)) == 1


def test_database_live_adapter_prevents_seed_revalidation():
    assert not registered_candidates([{'name':'DB Live','url':'https://dealer.in/','adapter_status':'live'}, {'name':'Seed','url':'https://dealer.in/','adapter_status':'candidate'}])


def test_researched_sources_and_bbt_demo_endpoint_are_in_scheduled_queue():
    sources = load_source_registry(from_database=False)
    queue = {url for _,url,_ in crawl_queue(sources)}
    expected = {'https://finder.porsche.com/in/en-IN','https://www.skodapreowned.in/','https://www.getonroadprice.com/demo-cars/india','https://www.discountedcarsindia.com/cars?category=demo','https://www.motodeals.co.in/','https://gurudevmotors.com/skoda-demo-cars-sale/','https://selekt.volvocars.in/en-in/store/','https://www.bigboytoyz.com/collection?demo=1'}
    assert expected <= queue
    assert all(s['adapter_status'] == 'candidate' for s in sources if s['url'] in expected - {'https://www.bigboytoyz.com/collection?demo=1'})


def probe(n):
    return registered_candidates([dict(name=str(n),url=f'https://dealer{n}.in/',adapter_status='candidate')])[0]


def test_probe_rotation_reaches_later_registered_candidates_and_reserves_web_capacity():
    now=datetime(2026,10,18,tzinfo=timezone.utc)
    seeds=[probe(n) for n in range(12)]
    web=[probe(n) for n in range(20,25)]
    history={}
    selected=[]
    for cycle in range(4):
        batch=plan_probes(seeds,web,history,.7,5,now=now+timedelta(hours=cycle*3))
        assert len(batch)==5 and any(item.url in {w.url for w in web} for item in batch)
        selected.extend(item.url for item in batch)
        for item in batch:history[item.url]={'last_probe_at':now+timedelta(hours=cycle*3),'probe_result':{'status':'rejected'}}
    assert {s.url for s in seeds} <= set(selected)
    assert len(set(selected))>=16


def test_probe_plan_borrows_idle_web_slots_and_deduplicates_across_pools():
    seeds=[probe(n) for n in range(6)]
    assert len(plan_probes(seeds,[seeds[0]],{},.7,5))==5
    assert len(plan_probes([],seeds,{},.7,5))==5


def test_running_probe_lease_and_staged_adapter_are_not_reselected():
    now=datetime(2026,10,18,tzinfo=timezone.utc)
    seeds=[probe(n) for n in range(3)]
    history={seeds[0].url:{'status':'promoted'},seeds[1].url:{'last_probe_at':now,'probe_result':{'status':'running'}}}
    assert [s.url for s in plan_probes(seeds,[],history,.7,5,now=now)]==[seeds[2].url]
    later=plan_probes(seeds,[],history,.7,5,now=now+timedelta(minutes=31))
    assert [s.url for s in later]==[seeds[2].url,seeds[1].url]
