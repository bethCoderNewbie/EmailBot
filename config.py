"""Central configuration loaded from .env"""
import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val

def _list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default).strip()
    return [v.strip() for v in raw.split(",") if v.strip()]

# Gmail
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials/credentials.json")
GMAIL_TOKEN_PATH        = os.getenv("GMAIL_TOKEN_PATH",        "credentials/token.json")
GMAIL_LABELS            = _list("GMAIL_LABELS", "INBOX")
GMAIL_SENDER_FILTER     = _list("GMAIL_SENDER_FILTER")   # empty = no filter

# OpenRouter
OPENROUTER_API_KEY = _require("OPENROUTER_API_KEY")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

# SMTP
SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = _require("SMTP_USERNAME")
SMTP_PASSWORD = _require("SMTP_PASSWORD")
SMTP_FROM     = os.getenv("SMTP_FROM", SMTP_USERNAME)
SMTP_TO       = _list("SMTP_TO")

# Newsletter
NEWSLETTER_SUBJECT = os.getenv("NEWSLETTER_SUBJECT", "Your Email Digest")
SCHEDULE_DAYS      = [int(d) for d in _list("SCHEDULE_DAYS", "0,3")]  # Mon & Thu
SCHEDULE_TIME      = os.getenv("SCHEDULE_TIME", "08:00")
