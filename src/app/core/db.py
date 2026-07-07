from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings
import os
import ssl

DATABASE_URL = settings.DATABASE_URL

connect_args = {}
if "postgres" in DATABASE_URL:
    cert_name = settings.OVH_SSL_CERT
    cert_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", cert_name)
    cert_path = os.path.normpath(cert_path)
    
    if not os.path.exists(cert_path):
        cert_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ca.pem")
        cert_path = os.path.normpath(cert_path)
        
    if os.path.exists(cert_path):
        ssl_context = ssl.create_default_context(cafile=cert_path)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        connect_args["ssl"] = ssl_context
    else:
        connect_args["ssl"] = True

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True if "postgres" in DATABASE_URL else False,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
