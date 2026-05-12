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


def start_scheduler():
    global _scheduler, _pool

    _pool = build_pool()

    # İlk çekimi hemen yap
    logger.info("İlk veri çekimi başlatılıyor...")
    _pool.refresh_all()

    # Periyodik job
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _pool.refresh_all,
        trigger="interval",
        seconds=settings.FETCH_INTERVAL_SECONDS,
        id="refresh_all",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler başlatıldı. Interval: %d saniye.",
        settings.FETCH_INTERVAL_SECONDS,
    )


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler durduruldu.")
