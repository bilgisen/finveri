import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Financial Data API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "") or None
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Worker
    FETCH_INTERVAL_SECONDS: int = int(os.getenv("FETCH_INTERVAL_SECONDS", "300"))
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "600"))
    HTTP_TIMEOUT_SECONDS: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))

    # Kaynak URL'leri
    OYAK_INSTRUMENTS_URL: str = os.getenv(
        "OYAK_INSTRUMENTS_URL",
        "https://www.oyakyatirim.com.tr/Home/GetAllInstruments",
    )
    AA_BIST_URL: str = os.getenv(
        "AA_BIST_URL",
        "https://aafinans.com/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    )
    AA_MARKET_SUMMARY_URL: str = os.getenv(
        "AA_MARKET_SUMMARY_URL",
        "https://aafinans.com/Navigation/UstBarSembolListesiniAl",
    )

    # İş Yatırım — tek sembol detay (on-demand)
    ISYATIRIM_QUOTE_URL: str = os.getenv(
        "ISYATIRIM_QUOTE_URL",
        "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/OneEndeks",
    )
    # On-demand cache süresi (saniye) — kısa tutulur, veri sık değişir
    ONDEMAND_CACHE_TTL_SECONDS: int = int(os.getenv("ONDEMAND_CACHE_TTL_SECONDS", "60"))


settings = Settings()
