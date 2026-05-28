import os
import sys
import asyncio
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.redis_client import get_redis
from app.services.ta_engine import generate_llm_summary, get_historical_dataframe

async def test():
    print("--- REDIS CHECK ---")
    r = get_redis()
    stocks_raw = r.get("pool:bist_stocks:data")
    if stocks_raw:
        stocks = json.loads(stocks_raw)
        eregl = next((item for item in stocks if item.get("code", "").upper() == "EREGL"), None)
        print("EREGL in pool:bist_stocks:data:", json.dumps(eregl, indent=2) if eregl else "NOT FOUND")
    else:
        print("pool:bist_stocks:data is empty")

    print("\n--- HISTORICAL DATAFRAME CHECK ---")
    df = await get_historical_dataframe("EREGL", limit=5)
    print(df)

    print("\n--- LLM SUMMARY CHECK ---")
    summary = await generate_llm_summary("EREGL")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    asyncio.run(test())
