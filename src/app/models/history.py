from sqlalchemy import Column, Integer, String, Float, Date, UniqueConstraint
from app.core.db import Base

class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uix_ticker_date'),
    )

    def __repr__(self):
        return f"<DailyPrice {self.ticker} {self.date} C:{self.close}>"
