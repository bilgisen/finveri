import os


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Financial Data API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Redis (OVH)
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./finveri.db")
    OVH_DATABASE_URL: str = os.getenv("OVH_DATABASE_URL", "")
    OVH_SSL_CERT: str = os.getenv("OVH_SSL_CERT", "ovh_ca.pem")

    # Gemini API Key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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




settings = Settings()
