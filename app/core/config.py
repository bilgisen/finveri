import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Financial Data API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Redis (Upstash)
    UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    # Redis (OVH)
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "rediss://default:87L1Z2RDVzEv9htpofKe@valkey-d75e6cca-o033531ff.database.cloud.ovh.net:20185"
    )

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./finveri.db")
    OVH_DATABASE_URL: str = os.getenv("OVH_DATABASE_URL", "")
    OVH_SSL_CERT: str = os.getenv("OVH_SSL_CERT", "ovh_ca.pem")

    # Gemini API Key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Celery (Optional, for compatibility across platforms)
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "")

    # Worker
    FETCH_INTERVAL_SECONDS: int = int(os.getenv("FETCH_INTERVAL_SECONDS", "300"))
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "345600"))
    HISTORY_CACHE_TTL_SECONDS: int = int(os.getenv("HISTORY_CACHE_TTL_SECONDS", "86400"))
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

    # COMP API — Temel analiz rasyoları (ROE, net_margin vb.)
    COMP_API_URL: str = os.getenv(
        "COMP_API_URL",
        "https://comp-ef958063.fastapicloud.dev",
    )
    COMP_API_TIMEOUT: int = int(os.getenv("COMP_API_TIMEOUT", "10"))


settings = Settings()
