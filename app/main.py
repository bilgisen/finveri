import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.redis_client import ping_redis
from app.core.ticker_store import load_tickers
from app.worker.scheduler import start_scheduler, stop_scheduler, get_pool
from app.routers import instruments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Finansal enstrüman verilerini gerçek zamanlı olarak sunan API.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # production'da daraltın
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(instruments.router)


@app.on_event("startup")
def on_startup():
    load_tickers()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


@app.get("/", tags=["system"])
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
def health():
    redis_ok = ping_redis()
    pool = get_pool()
    source_status = pool.get_status() if pool else {}

    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "unreachable",
        "sources": source_status,
        "fetch_interval_seconds": settings.FETCH_INTERVAL_SECONDS,
    }


@app.post("/admin/reload-tickers", tags=["admin"])
def reload_tickers():
    """tickers.json'ı yeniden yükler. Restart gerektirmez."""
    count = load_tickers()
    return {"loaded": count}


@app.post("/admin/refresh", tags=["admin"])
def manual_refresh():
    """Tüm kaynakları manuel olarak günceller."""
    pool = get_pool()
    if not pool:
        return {"status": "pool henüz başlatılmadı"}
    pool.refresh_all()
    return {"status": "ok"}
