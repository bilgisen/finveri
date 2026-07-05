"""Sync historical prices for all comp tickers - Production Ready"""
import asyncio
import logging
import sys
from datetime import datetime

# Add app to path
sys.path.insert(0, '/app')

from app.worker.historical import sync_all_history
from app.core.ticker_store import load_tickers, get_all_tickers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main sync function"""
    logger.info("="*70)
    logger.info("HISTORICAL PRICE SYNC FOR COMP - STARTED")
    logger.info("="*70)
    
    start_time = datetime.now()
    
    # Load tickers
    logger.info("\n📊 Step 1: Loading tickers from tickers.json...")
    count = load_tickers()
    logger.info(f"  Loaded {count} tickers into Redis")
    
    # Get ticker details
    tickers = get_all_tickers()
    logger.info(f"\n📊 Step 2: Starting historical sync for {len(tickers)} tickers...")
    logger.info(f"  Estimated time: {len(tickers) * 2 / 60:.1f} minutes (with 2s delay per ticker)")
    logger.info(f"  This will fetch OHLCV data from yfinance/TradingView/IsYatirim")
    
    # Run sync
    try:
        await sync_all_history()
        logger.info("\n✅ Historical sync completed successfully!")
    except Exception as e:
        logger.error(f"\n❌ Historical sync failed: {e}", exc_info=True)
        return 1
    
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n⏱️  Total time: {elapsed/60:.1f} minutes")
    logger.info("="*70)
    logger.info("NEXT: Run populate_company_metrics.py in comp to sync prices")
    logger.info("="*70)
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
