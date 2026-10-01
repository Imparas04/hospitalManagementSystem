"""Application configuration.

All secrets and database credentials come from environment variables
(loaded from the .env file). Nothing sensitive is hardcoded here.
"""
import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()  # reads .env file (if present) into os.environ


def _build_db_uri():
    """Build the SQLAlchemy connection string from DB_* variables.

    DATABASE_URL (if set) wins - handy for tests or deployment.
    """
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    user = os.getenv("DB_USER", "")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))  # handles special chars
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "hospital_db")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


class Config:
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}  # reconnect if MySQL drops idle connection

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_EXPIRES_HOURS", "8")))

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]


class TestingConfig(Config):
    """Used by pytest: in-memory SQLite, so tests never touch the real MySQL data."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-only-secret-key-not-for-real-use-0123456789"
