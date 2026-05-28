import asyncio
from app.services.ta_engine import generate_llm_summary
import json

async def main():
    res = await generate_llm_summary("XAUUSD")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
