import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import instruments, ta, ta_advanced, sync

# Workers ortaminda calismayan modulleri sartli import et
try:
    from app.core.redis_client import ping_redis
    from app.worker.scheduler import start_scheduler, stop_scheduler, get_pool
    from app.core.ticker_store import load_tickers
    _HAS_WORKER_DEPS = True
except ImportError:
    _HAS_WORKER_DEPS = False

try:
    from app.core.workers_cache import cache_set
    _HAS_KV = True
except ImportError:
    _HAS_KV = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def is_market_open() -> bool:
    """BIST: hafta içi 09:00-17:00 İstanbul (UTC+3)"""
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 17


def compute_etag(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return '"' + hashlib.sha256(raw.encode()).hexdigest()[:16] + '"'


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

    @app.middleware("http")
    async def conditional_cache_middleware(request: Request, call_next):
        response = await call_next(request)

        if request.method == "GET" and response.status_code < 400 and response.status_code != 304:
            import json as _json
            from starlette.responses import JSONResponse

            cc = "public, max-age=10, stale-while-revalidate=30" if is_market_open() else "public, max-age=86400"
            response.headers["Cache-Control"] = cc

            if hasattr(response, "body"):
                try:
                    data = _json.loads(response.body)
                    if isinstance(data, dict):
                        etag = compute_etag(data)
                        if_none_match = request.headers.get("if-none-match")
                        if if_none_match and if_none_match == etag:
                            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cc})
                        response.headers["ETag"] = etag
                except (_json.JSONDecodeError, TypeError, AttributeError):
                    pass

        return response

    app.include_router(instruments.router)
    app.include_router(ta.router)
    app.include_router(ta_advanced.router)
    app.include_router(sync.router)

    # Frontend uyumluluk alias'ları (hono.jetborsa.com)
    import json
    from app.core.redis_client import get_redis

    @app.get("/api/market/summary", tags=["compat"])
    def market_summary_compat():
        r = get_redis()
        raw = r.get("pool:market_summary:data")
        if not raw:
            from fastapi.responses import JSONResponse
            return JSONResponse({"total": 0, "data": [], "last_updated": None})
        data = json.loads(raw)
        last_updated = r.get("pool:market_summary:last_updated")
        return {"total": len(data), "last_updated": last_updated, "data": data}

    @app.get("/api/market/stocks", tags=["compat"])
    def market_stocks_compat():
        r = get_redis()
        raw = r.get("pool:bist_stocks:data")
        if not raw:
            from fastapi.responses import JSONResponse
            return JSONResponse({"total": 0, "data": [], "last_updated": None})
        data = json.loads(raw)
        last_updated = r.get("pool:bist_stocks:last_updated")
        return {"total": len(data), "last_updated": last_updated, "data": data}

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
