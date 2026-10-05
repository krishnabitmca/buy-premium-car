from api.search import _planned_live_sources_unavailable


def test_no_applicable_live_source_is_not_an_outage():
    plan=[{"name":"Jaguar Demo Candidates","adapter_status":"candidate"}]
    sources=[{"name":"Jaguar Demo Candidates","status":"candidate"}]
    assert _planned_live_sources_unavailable(plan,sources) is False


def test_configured_live_source_with_no_live_response_is_an_outage():
    plan=[{"name":"CarWale Used","adapter_status":"live"}]
    sources=[{"name":"CarWale Used","status":"blocked"}]
    assert _planned_live_sources_unavailable(plan,sources) is True
