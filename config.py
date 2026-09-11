import os
from dotenv import load_dotenv

load_dotenv()

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

TELEGRAM_BOT_TOKEN = required("TELEGRAM_BOT_TOKEN")
BOT_PASSWORD_HASH = required("BOT_PASSWORD_HASH")
OPENROUTER_API_KEY = required("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://example.com")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "AI Market Analyzer")
UPDATE_INTERVAL_SECONDS = int(os.getenv("UPDATE_INTERVAL_SECONDS", "60"))
NEWS_LIMIT = int(os.getenv("NEWS_LIMIT", "5"))
AI_COOLDOWN_SECONDS = int(os.getenv("AI_COOLDOWN_SECONDS", "60"))
