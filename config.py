import os


def required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing Railway variable: {name}"
        )

    return value


# =========================================================
# TELEGRAM
# =========================================================

TELEGRAM_BOT_TOKEN = required(
    "TELEGRAM_BOT_TOKEN"
)


# =========================================================
# BOT AUTHENTICATION
# =========================================================

BOT_PASSWORD_HASH = required(
    "BOT_PASSWORD_HASH"
)


# =========================================================
# GEMINI AI
# =========================================================

GEMINI_API_KEY = required(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


# =========================================================
# ANALYSIS SETTINGS
# =========================================================

UPDATE_INTERVAL_SECONDS = int(
    os.getenv(
        "UPDATE_INTERVAL_SECONDS",
        "60"
    )
)

AI_COOLDOWN_SECONDS = int(
    os.getenv(
        "AI_COOLDOWN_SECONDS",
        "60"
    )
)


# =========================================================
# OPTIONAL SIGNAL CHANNEL
# =========================================================

SIGNAL_CHANNEL_ID = os.getenv(
    "SIGNAL_CHANNEL_ID",
    ""
)
