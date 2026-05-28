import urllib.request
import json

try:
    response = urllib.request.urlopen("http://127.0.0.1:8000/instruments/stocks/EREGL/header-summary")
    data = json.loads(response.read().decode('utf-8'))
    print("API SUCCESS:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print("API ERROR:", e)
