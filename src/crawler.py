from __future__ import annotations
import asyncio
from crawl4ai import AsyncWebCrawler,BrowserConfig,CrawlerRunConfig,CacheMode
from .extractor import extract_links,extract_page

async def crawl_urls(urls,settings):
    browser_config=BrowserConfig(headless=True,java_script_enabled=True)
    run_config=CrawlerRunConfig(word_count_threshold=20,excluded_tags=["script","style","noscript"],page_timeout=settings.network.get("request_timeout_seconds",30)*1000,cache_mode=CacheMode.BYPASS)
    detail_limit=int(settings.market.get("max_detail_pages_per_source",40));out=[]
    async with AsyncWebCrawler(config=browser_config) as crawler:
        sem=asyncio.Semaphore(settings.network.get("max_concurrency",3));seen=set()
        async def fetch(source_name,url,tier):
            key=url.rstrip("/")
            if key in seen:return None,None
            seen.add(key)
            async with sem:
                try:
                    res=await crawler.arun(url=url,config=run_config)
                    return res,extract_page(source_name,tier,url,res)
                except Exception as exc:
                    print(f"crawl error: {url}: {exc}");return None,None
                finally:
                    await asyncio.sleep(settings.network.get("polite_delay_seconds",1.0))
        async def crawl_detail(source_name,url,tier):
            res,vehicle=await fetch(source_name,url,tier)
            if vehicle:out.append(vehicle)
        async def one(source_name,url,tier):
            res,vehicle=await fetch(source_name,url,tier)
            if vehicle:out.append(vehicle)
            if not res:return
            html=getattr(res,"html","") or "";pattern=settings.network.get("vehicle_link_pattern")
            links=extract_links(html,getattr(res,"redirected_url",None) or url,pattern)[:detail_limit]
            await asyncio.gather(*(crawl_detail(source_name,u,tier) for u in links))
        await asyncio.gather(*(one(*item) for item in urls))
    return out
