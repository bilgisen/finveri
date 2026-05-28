import sqlite3
import asyncio
from datetime import datetime
from sqlalchemy import select, func
from app.core.db import AsyncSessionLocal, engine
from app.models.history import DailyPrice

async def migrate_data():
    print("Connecting to SQLite database (finveri.db)...")
    sqlite_conn = sqlite3.connect("finveri.db")
    cursor = sqlite_conn.cursor()
    
    try:
        cursor.execute("SELECT ticker, date, open, high, low, close, volume FROM daily_prices")
        rows = cursor.fetchall()
        print(f"Total rows found in SQLite: {len(rows)}")
    except Exception as e:
        print(f"Error reading SQLite daily_prices table: {e}")
        sqlite_conn.close()
        return

    if not rows:
        print("No historical data to migrate.")
        sqlite_conn.close()
        return

    print("Preparing data for PostgreSQL bulk insert...")
    records = []
    for row in rows:
        ticker, date_str, open_p, high_p, low_p, close_p, volume = row
        # Parse 'YYYY-MM-DD' date string to datetime.date
        try:
            date_val = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception as date_err:
            print(f"Date parsing failed for {ticker} on {date_str}: {date_err}")
            continue

        records.append({
            "ticker": ticker,
            "date": date_val,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume
        })

    sqlite_conn.close()
    print(f"Successfully processed {len(records)} records for migration.")

    print("Writing records to PostgreSQL in batches...")
    batch_size = 1000
    total_written = 0
    
    async with AsyncSessionLocal() as session:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            # Map dictionaries to DailyPrice model instances
            db_objects = [DailyPrice(**rec) for rec in batch]
            
            try:
                # Add all to session and commit batch
                session.add_all(db_objects)
                await session.commit()
                total_written += len(batch)
                print(f"Migrated batch: {total_written}/{len(records)} records...")
            except Exception as db_err:
                await session.rollback()
                print(f"Error inserting batch starting at index {i}: {db_err}")
                print("Aborting migration.")
                return

    print("=" * 50)
    print("MIGRATION COMPLETED!")
    print(f"Total records processed: {len(records)}")
    print(f"Total records successfully written to Postgres: {total_written}")
    print("=" * 50)
    
    # Run a count query on PostgreSQL to double check
    async with AsyncSessionLocal() as session:
        stmt = select(func.count(DailyPrice.id))
        result = await session.execute(stmt)
        count = result.scalar()
        print(f"Verified rows in PostgreSQL daily_prices table: {count}")

if __name__ == "__main__":
    asyncio.run(migrate_data())
