import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/app/data/scribe.db")
    SESSION_EXPIRE_DAYS: int = 30

settings = Settings()
