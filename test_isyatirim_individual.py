import httpx

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.isyatirim.com.tr/",
}

symbols = ["THYAO", "GARAN", "XU100"]

for symbol in symbols:
    url = f"https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={symbol}"
    print(f"\nTesting IsYatirim individual: {url}")
    try:
        with httpx.Client(timeout=10, verify=False, headers=_HEADERS) as client:
            resp = client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  ContentType: {resp.headers.get('content-type', 'unknown')}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"  Success JSON! Data: {data}")
                except Exception as je:
                    print(f"  Failed to parse JSON: {je}")
                    print(f"  Body: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
