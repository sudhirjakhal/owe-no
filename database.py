from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./owe_no.db"
engine = create_engine(
    DATABASE_URL,
    pool_size=10, max_overflow=20, pool_timeout=30
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)