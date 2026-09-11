# AI Market Analyzer — Telegram Bot

Telegram-only market analysis assistant. It does NOT connect to MT5 and does NOT place trades.

Features:
- Password authentication
- Session budget
- Main-asset selection
- Risk percentage
- Free market data via yfinance
- Free news via Google News RSS
- OpenRouter AI analysis
- BUY / SELL / WAIT
- Suggested amount based on session budget and risk
- Automatic Telegram update every 60 seconds
- TRADE TAKEN / TRADE NOT TAKEN
- Active-trade monitoring priority
- English-only UI

Important: this is an analysis/recommendation tool, not guaranteed financial advice. Data can be delayed or unavailable. No trade execution is included.

## Install

Windows PowerShell:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/make_password_hash.py

Linux/macOS:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/make_password_hash.py

Put the generated hash into .env, then add your Telegram bot token and OpenRouter API key.

Run:
python -m bot.main
