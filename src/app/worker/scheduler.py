import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.sources.pool import DataPool
from app.sources.oyak import OyakSource
from app.sources.aa import AASource
from app.sources.aa_market import AAMarketSummarySource

logger = logging.getLogger(__name__)

_scheduler = None
_pool = None


def build_pool() -> DataPool:
    """Kaynak zincirlerini tanımlar ve pool'u döner."""
    pool = DataPool()

    # Enstrüman listesi: Oyak primary, AA fallback
    pool.register(
        "instruments",
        primary=OyakSource(),
        fallbacks=[AASource()],
    )

    # BIST hisseleri: AA primary, Oyak fallback
    pool.register(
        "bist_stocks",
        primary=AASource(),
        fallbacks=[OyakSource()],
    )

    # Piyasa özeti (navbar ticker): sadece AA sağlıyor
    pool.register(
        "market_summary",
        primary=AAMarketSummarySource(),
    )

    # İleride eklenecek:
    # pool.register("forex", primary=IsYatirimSource(), fallbacks=[OyakSource()])
    # pool.register("indices", primary=AASource(), fallbacks=[IsYatirimSource()])

    return pool


def get_pool() -> DataPool:
    """Mevcut pool instance'ını döner."""
    return _pool


def sync_history_task():
    """Wrapper to run the async sync_all_history in the background scheduler."""
    import asyncio
    from app.worker.historical import sync_all_history
    try:
        logger.info("Starting scheduled historical OHLCV data sync...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(sync_all_history())
        loop.close()
        logger.info("Scheduled historical sync completed successfully.")
    except Exception as e:
        logger.error(f"Failed to run scheduled historical sync: {e}")

def start_scheduler():
    global _scheduler, _pool

    _pool = build_pool()

    # İlk çekimi arka planda asenkron olarak başlat (non-blocking)
    import threading
    threading.Thread(target=_pool.refresh_all, name="InitialDataFetchThread", daemon=True).start()
    logger.info("İlk veri çekimi arka planda başlatıldı.")

    # Periyodik job
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _pool.refresh_all,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-17",
        minute="0,30",
        timezone="Europe/Istanbul",
        id="refresh_all",
        replace_existing=True,
    )
    
    # Her gece 00:05'te historical veriyi çek (Ultimate Level Auto-Sync)
    _scheduler.add_job(
        sync_history_task,
        trigger="cron",
        hour="0",
        minute="5",
        timezone="Europe/Istanbul",
        id="sync_historical",
        replace_existing=True,
    )
    
    _scheduler.start()
    logger.info(
        "Scheduler başlatıldı. Cron: Hafta içi 09:00-17:00 anlık fiyatlar, her gece 00:05 tarihsel veri.",
    )


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler durduruldu.")
