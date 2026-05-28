import httpx

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://aafinans.com/",
    "Origin": "https://aafinans.com",
    "X-Requested-With": "XMLHttpRequest",
}

variants = [
    "https://aafinans.com/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    "http://aafinans.com/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    "https://www.aafinans.com/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    "http://www.aafinans.com/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    "https://aafinans.com.tr/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    "http://aafinans.com.tr/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    "https://finans.anadoluajansi.com.tr/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
]

for url in variants:
    print(f"\nTesting: {url}")
    try:
        with httpx.Client(timeout=10, verify=False, headers=_HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  Final URL: {resp.url}")
            print(f"  ContentType: {resp.headers.get('content-type', 'unknown')}")
            snippet = resp.text[:150].strip()
            print(f"  Snippet: {snippet}")
    except Exception as e:
        print(f"  Error: {e}")
