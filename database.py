from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./owe_no.db"
engine = create_engine(
    DATABASE_URL,
    pool_size=10,  # Default is 5
    max_overflow=20,  # Default is 10
    pool_timeout=30,  # Default is 30 seconds
    pool_recycle=1800
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)