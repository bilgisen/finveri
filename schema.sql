CREATE TABLE IF NOT EXISTS daily_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume REAL,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker ON daily_prices(ticker);
CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date);
