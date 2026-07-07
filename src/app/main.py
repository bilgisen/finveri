import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import instruments, ta, ta_advanced

# Workers ortaminda calismayan modulleri sartli import et
try:
    from app.core.redis_client import ping_redis
    from app.worker.scheduler import start_scheduler, stop_scheduler, get_pool
    from app.core.ticker_store import load_tickers
    _HAS_WORKER_DEPS = True
except ImportError:
    _HAS_WORKER_DEPS = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def create_app() -> FastAPI:
    """Factory function — Worker icin FastAPI app olusturur."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Finansal enstrüman verilerini gerçek zamanlı olarak sunan API.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(instruments.router)
    app.include_router(ta.router)
    app.include_router(ta_advanced.router)

    @app.on_event("startup")
    def on_startup():
        if _HAS_WORKER_DEPS:
            load_tickers()
            start_scheduler()

    @app.on_event("shutdown")
    def on_shutdown():
        if _HAS_WORKER_DEPS:
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
        from app.core.d1 import get_db
        d1_ok = get_db() is not None

        if not _HAS_WORKER_DEPS:
            return {"status": "ok", "mode": "workers", "d1": d1_ok}

        redis_ok = ping_redis()
        pool = get_pool()
        source_status = pool.get_status() if pool else {}

        return {
            "status": "ok" if redis_ok else "degraded",
            "redis": "connected" if redis_ok else "unreachable",
            "d1": d1_ok,
            "sources": source_status,
            "fetch_interval_seconds": settings.FETCH_INTERVAL_SECONDS,
        }

    @app.post("/admin/reload-tickers", tags=["admin"])
    def reload_tickers():
        if not _HAS_WORKER_DEPS:
            return {"status": "not available in workers mode"}
        count = load_tickers()
        return {"loaded": count}

    @app.post("/admin/refresh", tags=["admin"])
    def manual_refresh():
        if not _HAS_WORKER_DEPS:
            return {"status": "not available in workers mode"}
        pool = get_pool()
        if not pool:
            return {"status": "pool henüz başlatılmadı"}
        pool.refresh_all()
        return {"status": "ok"}

    return app


# Local development icin varsayilan app
app = create_app()
