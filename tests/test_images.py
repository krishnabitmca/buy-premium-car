from src.extractor import extract_image_urls

def test_extract_image_urls_prefers_listing_images():
    html = """<html><head><meta property="og:image" content="/cars/audi-q3.jpg"></head><body>
    <img alt="dealer logo" src="/logo.png" width="80" height="80">
    <img alt="BMW vehicle gallery" data-src="/cars/bmw-side.webp" width="900" height="600">
    <img alt="car" src="/icons/car.svg">
    </body></html>"""
    urls=extract_image_urls(html,"https://example.com/detail/123")
    assert urls[0]=="https://example.com/cars/audi-q3.jpg"
    assert "https://example.com/cars/bmw-side.webp" in urls
    assert all("logo" not in u and "icon" not in u for u in urls)
