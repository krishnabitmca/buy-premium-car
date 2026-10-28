"""Guard the reviewed Volkswagen Certified Pre-Owned source URL.

The production registry is PostgreSQL-backed and is intentionally not rewritten
by this config-only change. Deployment requires a separately reviewed rollout.
"""
from pathlib import Path
from urllib.parse import urlsplit

import yaml


def test_vw_certified_source_uses_oem_linked_https_host():
    config = yaml.safe_load(Path("config/sources.yaml").read_text(encoding="utf-8"))
    sources = [s for s in config["known_sources"] if s["name"] == "Das WeltAuto"]
    assert len(sources) == 1
    source = sources[0]

    url = urlsplit(source["url"])
    assert url.scheme == "https"
    assert url.hostname == "www.vwcertifiedpreowned.co.in"
    assert url.path == "/buy-used-cars"
    assert source["adapter_status"] == "live"
    assert source["conditions"] == ["used"]
    assert source["source_type"] == "oem_certified"
