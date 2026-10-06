from src.source_intelligence import plan_sources


def test_demo_search_fans_out_to_used_and_demo_capable_sources():
    registry = [
        {"name":"OEM","adapter_status":"live","brands":["BMW"],"conditions":["used"],"segments":["premium"],"priority":90},
        {"name":"Marketplace","adapter_status":"live","brands":["all"],"conditions":["used"],"segments":["premium"],"priority":80},
        {"name":"Dealer","adapter_status":"live","brands":["BMW"],"conditions":["demo"],"segments":["premium"],"priority":70},
    ]
    names={x["name"] for x in plan_sources(brand="BMW",model="X1",condition="demo",registry=registry,live_only=True)}
    assert names == {"OEM","Marketplace","Dealer"}


def test_used_search_also_fans_out_and_filters_after_extraction():
    registry = [
        {"name":"Mixed OEM","adapter_status":"live","brands":["BMW"],"conditions":["demo"],"segments":["premium"],"priority":90},
        {"name":"Mixed Dealer","adapter_status":"live","brands":["BMW"],"conditions":["used"],"segments":["premium"],"priority":80},
    ]
    names={x["name"] for x in plan_sources(brand="BMW",model="X1",condition="used",registry=registry,live_only=True)}
    assert names == {"Mixed OEM","Mixed Dealer"}
