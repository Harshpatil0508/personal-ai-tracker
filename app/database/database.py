from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # max persistent connections
    max_overflow=10,        # burst handling
    pool_timeout=30,        # seconds before failing
    pool_recycle=1800,      # recycle stale connections
    pool_pre_ping=True,    # avoid dead connections
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()
