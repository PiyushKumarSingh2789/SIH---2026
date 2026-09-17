"""
DB engine + session factory. DATABASE_URL example for local MySQL 8:
mysql+pymysql://sih_user:sih_pass@localhost:3306/sih26102
"""
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env so every entrypoint (uvicorn, alembic, seed scripts) sees DATABASE_URL

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://sih_user:sih_pass@localhost:3306/sih26102")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency — use as `db: Session = Depends(get_db)` in every route."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
