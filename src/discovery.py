from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
from ddgs import DDGS

@dataclass
class DiscoveryResult:
    url:str
    title:str
    snippet:str
    domain:str
    query:str

def discover(settings,known_domains):
    results=[];search=settings.search;max_n=int(search.get("max_discovery_results_per_query",8));engines=search.get("engines",["bing","duckduckgo","google"]);brands=search.get("brands",[]);cities=search.get("cities",[])
    query_bank=[]
    for brand in brands:
        for city in cities[:3]:
            query_bank.extend([f'"{brand}" "used car" "{city}"',f'"{brand}" "demo car" "{city}"'])
            if len(query_bank)>=len(brands)*2:break
        if len(query_bank)>=len(brands)*2:break
    seen_urls=set()
    for query in query_bank:
        try:
            with DDGS() as ddgs:
                for engine in engines:
                    try:rows=ddgs.text(query,max_results=max_n,backend=engine)
                    except TypeError:rows=ddgs.text(query,max_results=max_n)
                    except Exception as exc:print(f"discovery backend {engine} failed: {exc}");continue
                    for r in rows:
                        url=r.get("href") or r.get("url")
                        if not url:continue
                        domain=urlparse(url).netloc.lower().removeprefix("www.")
                        if not domain or domain in known_domains or url in seen_urls:continue
                        seen_urls.add(url);results.append(DiscoveryResult(url=url,title=r.get("title",""),snippet=r.get("body",r.get("snippet","")),domain=domain,query=query))
        except Exception as exc:print(f"discovery query failed: {query}: {exc}")
    return results
