import os
import json
import logging
import asyncio

from google import genai

log = logging.getLogger("market-bot")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    log.warning("GEMINI_API_KEY is not configured.")

client = genai.Client(
    api_key=GEMINI_API_KEY
)


def _snapshot_to_dict(snapshot):
    return {
        "price": getattr(snapshot, "price", None),
        "change_pct": getattr(snapshot, "change_pct", None),
        "sma20": getattr(snapshot, "sma20", None),
        "sma50": getattr(snapshot, "sma50", None),
        "rsi14": getattr(snapshot, "rsi14", None),
        "volatility_pct": getattr(snapshot, "volatility_pct", None),
    }


def _news_to_text(news):
    if not news:
        return "No current news/reports available."

    lines = []

    for item in news[:10]:
        if isinstance(item, str):
            lines.append(f"- {item}")

        elif isinstance(item, dict):
            title = (
                item.get("title")
                or item.get("headline")
                or item.get("name")
                or str(item)
            )

            lines.append(f"- {title}")

        else:
            lines.append(f"- {str(item)}")

    return "\n".join(lines)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


async def analyze(snapshot, news, session):

    market = _snapshot_to_dict(snapshot)
    news_text = _news_to_text(news)

    budget = _safe_float(
        getattr(session, "budget", 0)
    )

    risk_pct = _safe_float(
        getattr(session, "risk_pct", 0)
    )

    asset = getattr(
        session,
        "asset",
        "UNKNOWN"
    )

    risk_amount = budget * risk_pct / 100

    active_trade = getattr(
        session,
        "trade",
        None
    )

    if active_trade:

        trade_info = f"""
ACTIVE TRADE:

Direction: {getattr(active_trade, "direction", "UNKNOWN")}
Entry: {getattr(active_trade, "entry", "UNKNOWN")}
Stop Loss: {getattr(active_trade, "stop_loss", "UNKNOWN")}
Target: {getattr(active_trade, "target", "UNKNOWN")}

The active trade has priority.
Focus on whether the trade should be:
HOLD, WATCH or EXIT-WATCH.
"""

    else:

        trade_info = """
No active trade.

Focus on discovering a new potential setup.
"""

    prompt = f"""
You are SPARKS FOREX, an AI-assisted financial
market analysis engine.

You analyze market data and available news/reports.

You DO NOT execute trades.
You DO NOT connect to MT5.
You DO NOT guarantee profits.
You must clearly communicate uncertainty.

========================
SESSION
========================

Asset:
{asset}

Session Budget:
{budget:.2f} INR

Maximum Risk:
{risk_pct:.2f}%

Maximum Risk Amount:
{risk_amount:.2f} INR

========================
MARKET DATA
========================

Current Price:
{market["price"]}

Recent Change:
{market["change_pct"]}%

SMA20:
{market["sma20"]}

SMA50:
{market["sma50"]}

RSI14:
{market["rsi14"]}

Volatility:
{market["volatility_pct"]}%

========================
NEWS / REPORTS
========================

{news_text}

========================
TRADE STATUS
========================

{trade_info}

========================
TASK
========================

Analyze the available information.

Consider:

1. Market trend
2. Momentum
3. RSI
4. SMA20 vs SMA50
5. Volatility
6. News/report sentiment
7. Potential support/resistance
8. Risk/reward
9. Existing trade if present

A BUY or SELL should only be returned when
there is a reasonably supported setup.

Otherwise return WAIT.

Do NOT invent market data.

========================
RESPONSE FORMAT
========================

Return ONLY valid JSON.

Use exactly this structure:

{{
  "action": "BUY",
  "confidence": 75,
  "risk_level": "MEDIUM",
  "entry_reference": 0,
  "stop_loss_reference": 0,
  "target_reference": 0,
  "suggested_amount": 0,
  "trade_management": "HOLD",
  "summary": "Short explanation."
}}

Rules:

action:
BUY, SELL or WAIT

confidence:
0 to 100

risk_level:
LOW, MEDIUM or HIGH

entry_reference:
Use 0 when no valid setup.

stop_loss_reference:
Use 0 when no valid setup.

target_reference:
Use 0 when no valid setup.

suggested_amount:
Never exceed the session budget.
Keep the amount consistent with the stated risk.

trade_management:
For no active trade:
NO-TRADE or WATCH

For active trade:
HOLD, WATCH or EXIT-WATCH

summary:
Keep it concise and explain the reasoning.
"""

    try:

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
        )

        if not response:
            raise RuntimeError(
                "Gemini returned no response."
            )

        raw = response.text or ""

        raw = raw.strip()

        # Remove markdown JSON fences if Gemini adds them
        if raw.startswith("```"):
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")
            raw = raw.strip()

        result = json.loads(raw)

        action = str(
            result.get("action", "WAIT")
        ).upper()

        if action not in ("BUY", "SELL", "WAIT"):
            action = "WAIT"

        result["action"] = action

        result["confidence"] = max(
            0,
            min(
                100,
                _safe_float(
                    result.get("confidence", 0)
                )
            )
        )

        result["risk_level"] = str(
            result.get(
                "risk_level",
                "UNKNOWN"
            )
        ).upper()

        result["entry_reference"] = _safe_float(
            result.get("entry_reference", 0)
        )

        result["stop_loss_reference"] = _safe_float(
            result.get("stop_loss_reference", 0)
        )

        result["target_reference"] = _safe_float(
            result.get("target_reference", 0)
        )

        result["suggested_amount"] = max(
            0,
            min(
                budget,
                _safe_float(
                    result.get(
                        "suggested_amount",
                        risk_amount
                    )
                )
            )
        )

        result["trade_management"] = str(
            result.get(
                "trade_management",
                "WATCH"
            )
        )

        result["summary"] = str(
            result.get(
                "summary",
                "No additional analysis available."
            )
        )

        return result

    except json.JSONDecodeError as e:

        log.error(
            "Gemini returned invalid JSON: %s",
            e
        )

        log.error(
            "Gemini raw response: %s",
            raw if "raw" in locals() else "EMPTY"
        )

        raise RuntimeError(
            "Gemini returned an invalid analysis format."
        )

    except Exception as e:

        log.exception(
            "Gemini analysis failed: %s",
            e
        )

        raise
