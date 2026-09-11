import asyncio
import hashlib
import hmac
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .assets import ASSETS
from .config import TELEGRAM_BOT_TOKEN, BOT_PASSWORD_HASH, UPDATE_INTERVAL_SECONDS, AI_COOLDOWN_SECONDS
from .data import get_snapshot
from .news import get_news
from .ai import analyze
from .state import AUTHENTICATED, SESSIONS, Session, Trade
from .ui import main_menu, asset_menu, trade_signal_menu, trade_monitor_menu

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO)
log = logging.getLogger("market-bot")
WAITING = {}
PASSWORD_ATTEMPTS = {}

def password_matches(password: str) -> bool:
    try:
        salt_hex, hash_hex = BOT_PASSWORD_HASH.split(":", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 210_000)
        return hmac.compare_digest(actual, bytes.fromhex(hash_hex))
    except Exception:
        return False

def money(value: float) -> str:
    return f"{value:,.2f}"

def session_text(s: Session) -> str:
    return (
        "📊 <b>ACTIVE SESSION</b>\n\n"
        f"Asset: <b>{s.asset}</b>\n"
        f"Session Budget: <b>₹{money(s.budget)}</b>\n"
        f"Risk: <b>{s.risk_pct:.2f}%</b>\n"
        f"Active Trade: <b>{'YES' if s.trade else 'NO'}</b>"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in AUTHENTICATED:
        await update.message.reply_text("🔓 <b>Authentication already active.</b>\n\nChoose an option below.",
                                        parse_mode="HTML", reply_markup=main_menu())
        return
    WAITING[uid] = "password"
    PASSWORD_ATTEMPTS[uid] = 0
    await update.message.reply_text("🔐 <b>Authentication Required</b>\n\nEnter the access password to unlock the market analyzer.",
                                    parse_mode="HTML")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    state = WAITING.get(uid)

    if state == "password":
        PASSWORD_ATTEMPTS[uid] = PASSWORD_ATTEMPTS.get(uid, 0) + 1
        if password_matches(text):
            AUTHENTICATED.add(uid)
            WAITING.pop(uid, None)
            PASSWORD_ATTEMPTS.pop(uid, None)
            await update.message.reply_text("✅ <b>Authentication successful.</b>\n\nWelcome to AI Market Analyzer.",
                                            parse_mode="HTML", reply_markup=main_menu())
        elif PASSWORD_ATTEMPTS[uid] >= 5:
            WAITING.pop(uid, None)
            PASSWORD_ATTEMPTS.pop(uid, None)
            await update.message.reply_text("❌ Too many incorrect attempts. Send /start to try again.")
        else:
            await update.message.reply_text("❌ Incorrect password. Try again.")
        return

    if uid not in AUTHENTICATED:
        await update.message.reply_text("🔒 Please send /start and authenticate first.")
        return

    if state == "budget":
        try:
            budget = float(text.replace(",", ""))
            if budget <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Enter a valid positive session budget, e.g. 10000.")
            return
        context.user_data["budget"] = budget
        WAITING[uid] = "asset"
        await update.message.reply_text("🎯 <b>Select the main asset for this session:</b>",
                                        parse_mode="HTML", reply_markup=asset_menu(ASSETS.keys()))
        return

    if state == "risk":
        try:
            risk = float(text.replace("%", "").strip())
            if not 0 < risk <= 10:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Enter a risk rate between 0.1% and 10%, e.g. 1.")
            return
        SESSIONS[uid] = Session(context.user_data["budget"], context.user_data["asset"], risk)
        WAITING.pop(uid, None)
        await update.message.reply_text(session_text(SESSIONS[uid]) +
                                        "\n\n🔎 <b>Signal scanning started.</b>\nAutomatic market updates will arrive every minute.",
                                        parse_mode="HTML", reply_markup=main_menu())
        await run_analysis_and_send(uid, context, force=True)
        return

    if state == "trade_details":
        parts = text.replace(",", " ").split()
        if len(parts) != 3:
            await update.message.reply_text("Send three numbers: <code>entry stop_loss target</code>", parse_mode="HTML")
            return
        try:
            entry, sl, target = map(float, parts)
        except ValueError:
            await update.message.reply_text("All three values must be numbers.")
            return
        s = SESSIONS.get(uid)
        if not s:
            await update.message.reply_text("No active session.")
            return
        last = context.user_data.get("last_signal", {})
        direction = last.get("action", "BUY")
        if direction not in ("BUY", "SELL"):
            direction = "BUY"
        s.trade = Trade(s.asset, direction, entry, sl, target)
        WAITING.pop(uid, None)
        await update.message.reply_text("💼 <b>Trade monitoring activated.</b>\n\nMonitoring will now get priority over new signal discovery.",
                                        parse_mode="HTML", reply_markup=trade_monitor_menu())
        return

    await update.message.reply_text("Use the buttons below.", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if uid not in AUTHENTICATED:
        await query.message.reply_text("🔒 Authenticate first with /start.")
        return

    data = query.data

    if data == "start_session":
        WAITING[uid] = "budget"
        await query.message.reply_text("💰 <b>Session Budget</b>\n\nEnter the total budget for this session in INR.",
                                        parse_mode="HTML")
        return

    if data == "stop_session":
        SESSIONS.pop(uid, None)
        WAITING.pop(uid, None)
        await query.message.reply_text("⏹ <b>Session stopped.</b>\nNo further automatic analysis will be sent.",
                                        parse_mode="HTML", reply_markup=main_menu())
        return

    if data == "status":
        s = SESSIONS.get(uid)
        await query.message.reply_text(session_text(s) if s else "No active session.",
                                        parse_mode="HTML" if s else None, reply_markup=main_menu())
        return

    if data == "active_trade":
        s = SESSIONS.get(uid)
        if not s or not s.trade:
            await query.message.reply_text("There is no active trade being monitored.")
        else:
            await query.message.reply_text(
                "💼 <b>ACTIVE TRADE</b>\n\n"
                f"Asset: <b>{s.trade.asset}</b>\nDirection: <b>{s.trade.direction}</b>\n"
                f"Entry: <code>{s.trade.entry}</code>\nStop Loss: <code>{s.trade.stop_loss}</code>\n"
                f"Target: <code>{s.trade.target}</code>",
                parse_mode="HTML", reply_markup=trade_monitor_menu())
        return

    if data == "help":
        await query.message.reply_text(
            "ℹ️ <b>How it works</b>\n\n"
            "1. Authenticate\n2. Set session budget\n3. Select a main asset\n"
            "4. Set maximum risk\n5. Market + news analysis\n6. AI returns BUY / SELL / WAIT\n"
            "7. Updates every minute\n8. Mark a trade as taken to prioritize monitoring\n\n"
            "⚠️ No MT5 connection and no trade execution.",
            parse_mode="HTML")
        return

    if data.startswith("asset:"):
        asset = data.split(":", 1)[1]
        if asset not in ASSETS:
            await query.message.reply_text("Invalid asset.")
            return
        context.user_data["asset"] = asset
        WAITING[uid] = "risk"
        await query.message.reply_text("⚠️ <b>Risk Rate</b>\n\nEnter the maximum risk per trade as a percentage. Example: <code>1</code>",
                                        parse_mode="HTML")
        return

    if data == "trade_taken":
        if not SESSIONS.get(uid):
            await query.message.reply_text("No active session.")
            return
        WAITING[uid] = "trade_details"
        await query.message.reply_text("💼 <b>Enter actual trade levels</b>\n\nSend: <code>entry stop_loss target</code>",
                                        parse_mode="HTML")
        return

    if data == "trade_not_taken":
        await query.message.reply_text("🔎 <b>Understood.</b>\nContinuing to look for the next setup.",
                                        parse_mode="HTML")
        return

    if data == "stop_trade":
        s = SESSIONS.get(uid)
        if s:
            s.trade = None
        WAITING.pop(uid, None)
        await query.message.reply_text("🛑 <b>Trade monitoring stopped.</b>\nReturning to new-signal scanning.",
                                        parse_mode="HTML", reply_markup=main_menu())
        return

    if data == "refresh":
        await run_analysis_and_send(uid, context, force=True)

async def run_analysis_and_send(uid: int, context: ContextTypes.DEFAULT_TYPE, force=False):
    s = SESSIONS.get(uid)
    if not s or not s.active:
        return

    now = datetime.now(timezone.utc)
    if not force and s.last_ai_at and (now - s.last_ai_at).total_seconds() < AI_COOLDOWN_SECONDS:
        return

    try:
        snapshot = await asyncio.to_thread(get_snapshot, s.asset)
        news = await asyncio.to_thread(get_news, s.asset)
        result = await analyze(snapshot, news, s)
        s.last_ai_at = now
        context.user_data["last_signal"] = result

        if s.trade:
            text = (
                "💼 <b>ACTIVE TRADE UPDATE</b>\n\n"
                f"Asset: <b>{s.asset}</b>\nDirection: <b>{s.trade.direction}</b>\n"
                f"Entry: <code>{s.trade.entry}</code>\nStop Loss: <code>{s.trade.stop_loss}</code>\n"
                f"Target: <code>{s.trade.target}</code>\n\n"
                f"Current Price: <b>{snapshot.price:.6g}</b>\n"
                f"Recent Change: <b>{snapshot.change_pct:+.2f}%</b>\n"
                f"Risk Level: <b>{result.get('risk_level','UNKNOWN')}</b>\n"
                f"AI Decision: <b>{result.get('action','HOLD')}</b>\n"
                f"Confidence: <b>{result.get('confidence',0):.0f}%</b>\n\n"
                f"🧠 {result.get('summary','No summary available.')}\n\n"
                f"Management: {result.get('trade_management','Monitor conditions.')}"
            )
            await context.bot.send_message(uid, text, parse_mode="HTML", reply_markup=trade_monitor_menu())
        else:
            action = result.get("action", "WAIT")
            if action in ("BUY", "SELL"):
                amount = min(max(0, result.get("suggested_amount", s.budget * s.risk_pct / 100)), s.budget)
                text = (
                    "🚨 <b>SIGNAL DETECTED</b>\n\n"
                    f"Asset: <b>{s.asset}</b>\nDirection: <b>{action}</b>\n"
                    f"Entry Reference: <code>{result.get('entry_reference',0)}</code>\n"
                    f"Stop Loss Reference: <code>{result.get('stop_loss_reference',0)}</code>\n"
                    f"Target Reference: <code>{result.get('target_reference',0)}</code>\n"
                    f"Risk: <b>{s.risk_pct:.2f}%</b>\nSuggested Amount: <b>₹{money(amount)}</b>\n"
                    f"Risk Level: <b>{result.get('risk_level','UNKNOWN')}</b>\n"
                    f"Confidence: <b>{result.get('confidence',0):.0f}%</b>\n\n"
                    f"🧠 {result.get('summary','No summary available.')}"
                )
                await context.bot.send_message(uid, text, parse_mode="HTML", reply_markup=trade_signal_menu())
            else:
                text = (
                    "📊 <b>MARKET UPDATE</b>\n\n"
                    f"Asset: <b>{s.asset}</b>\nSession Budget: <b>₹{money(s.budget)}</b>\n"
                    f"Risk: <b>{s.risk_pct:.2f}%</b>\nPrice: <b>{snapshot.price:.6g}</b>\n"
                    f"Recent Change: <b>{snapshot.change_pct:+.2f}%</b>\n"
                    f"Trend: <b>{'Bullish' if snapshot.sma20 > snapshot.sma50 else 'Bearish'}</b>\n"
                    f"RSI(14): <b>{snapshot.rsi14:.1f}</b>\nVolatility: <b>{snapshot.volatility_pct:.2f}%</b>\n"
                    f"News Items: <b>{len(news)}</b>\nSignal: <b>{action}</b>\n\n"
                    f"🧠 {result.get('summary','No strong setup right now.')}"
                )
                await context.bot.send_message(uid, text, parse_mode="HTML", reply_markup=main_menu())

    except Exception:
        log.exception("Analysis failed for user %s", uid)
        await context.bot.send_message(
            uid,
            "⚠️ <b>Analysis temporarily unavailable.</b>\n\n"
            "A market/news provider or AI API may be unavailable. "
            "The session remains active and the bot will retry on the next cycle.",
            parse_mode="HTML")

async def minute_job(context: ContextTypes.DEFAULT_TYPE):
    for uid in list(SESSIONS.keys()):
        try:
            await run_analysis_and_send(uid, context)
        except Exception:
            log.exception("Minute job failed for user %s", uid)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.job_queue.run_repeating(minute_job, interval=UPDATE_INTERVAL_SECONDS, first=UPDATE_INTERVAL_SECONDS)
    log.info("AI Market Analyzer started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
