"""
D1 Repository — Cloudflare D1 database operations.
Replaces SQLAlchemy for Workers environment.
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global D1 reference — set by Worker entry point
_db = None


def set_db(db):
    """Set the global D1 database binding."""
    global _db
    _db = db


def get_db():
    """Get the global D1 database binding."""
    return _db


class D1Repository:
    """D1 database wrapper for Worker environment."""

    def __init__(self, db):
        self.db = db

    async def execute(self, sql: str, *args) -> Dict[str, Any]:
        """Execute a single SQL statement."""
        stmt = self.db.prepare(sql)
        if args:
            stmt = stmt.bind(*args)
        return await stmt.run()

    async def fetch_one(self, sql: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        stmt = self.db.prepare(sql)
        if args:
            stmt = stmt.bind(*args)
        result = await stmt.first()
        return result

    async def fetch_all(self, sql: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        stmt = self.db.prepare(sql)
        if args:
            stmt = stmt.bind(*args)
        result = await stmt.all()
        return result.results if result else []

    async def batch_insert_prices(self, records: List[Dict[str, Any]]) -> None:
        """Batch insert OHLCV records with upsert."""
        if not records:
            return

        statements = []
        for r in records:
            stmt = self.db.prepare(
                "INSERT INTO daily_prices (ticker, date, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(ticker, date) DO UPDATE SET "
                "open=excluded.open, high=excluded.high, low=excluded.low, "
                "close=excluded.close, volume=excluded.volume"
            ).bind(
                r["ticker"], str(r["date"]),
                r["open"], r["high"], r["low"], r["close"], r["volume"]
            )
            statements.append(stmt)

        await self.db.batch(statements)

    async def get_prices(self, ticker: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch historical prices for a ticker."""
        return await self.fetch_all(
            "SELECT date, open, high, low, close, volume "
            "FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            ticker, limit
        )

    async def get_price_count(self, ticker: str) -> int:
        """Get count of price records for a ticker."""
        result = await self.fetch_one(
            "SELECT COUNT(*) as cnt FROM daily_prices WHERE ticker = ?",
            ticker
        )
        return result["cnt"] if result else 0
