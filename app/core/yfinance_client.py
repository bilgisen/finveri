import yfinance as yf

def get_ticker(symbol: str) -> yf.Ticker:
    """Returns a yfinance Ticker object (using default YF internal session)."""
    return yf.Ticker(symbol)
