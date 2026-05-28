import httpx

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.isyatirim.com.tr/",
}

endpoints = [
    "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseYuzdeselDegisim",
    "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTeknikAnaliz",
]

for url in endpoints:
    print(f"\nTesting IsYatirim bulk: {url}")
    try:
        with httpx.Client(timeout=10, verify=False, headers=_HEADERS) as client:
            resp = client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  ContentType: {resp.headers.get('content-type', 'unknown')}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"  Success JSON! Keys: {list(data.keys()) if isinstance(data, dict) else 'List of ' + str(len(data))}")
                    if isinstance(data, dict) and "value" in data:
                        print(f"  value length: {len(data['value'])}")
                        if len(data['value']) > 0:
                            print(f"  First item: {data['value'][0]}")
                    elif isinstance(data, list) and len(data) > 0:
                        print(f"  First item: {data[0]}")
                except Exception as je:
                    print(f"  Failed to parse JSON: {je}")
                    print(f"  Body snippet: {resp.text[:150]}")
    except Exception as e:
        print(f"  Error: {e}")
