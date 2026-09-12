import os
import json
import logging
import asyncio
import re

from google import genai

log = logging.getLogger("market-bot")

# =========================================================
# GEMINI CONFIG
# =========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

if not GEMINI_API_KEY:
    log.warning("GEMINI_API_KEY is not configured.")

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# HELPERS
# =========================================================

def _snapshot_to_dict(snapshot):
    return {
        "price": getattr(snapshot, "price", None),
        "change_pct": getattr(snapshot, "change_pct", None),
        "sma20": getattr(snapshot, "sma20", None),
        "sma50": getattr(snapshot, "sma50", None),
        "rsi14": getattr(snapshot, "rsi14", None),
        "volatility_pct": getattr(
            snapshot,
            "volatility_pct",
            None
        ),
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
                or item.get("summary")
                or str(item)
            )

            lines.append(f"- {title}")

        else:
            lines.append(f"- {str(item)}")

    return "\n".join(lines)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_json_response(text):
    """
    Gemini kabhi-kabhi JSON ko markdown code block
    ke andar return kar deta hai.
    """

    if not text:
        return ""

    text = text.strip()

    # ```json ... ```
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    # ``` ... ```
    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    # Agar extra text ke saath JSON aaya ho,
    # first { aur last } ke beech ka part try karo.
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            text = text[start:end + 1]

    return text.strip()


def _clean_summary(text):
    """
    Telegram HTML parse mode ke saath conflict na ho.
    """

    if not text:
        return "No additional analysis available."

    text = str(text)

    text = (
        text.replace("&", "and")
        .replace("<", "")
        .replace(">", "")
    )

    return text[:1000]


# =========================================================
# MAIN AI ANALYSIS
# =========================================================

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

    # Maximum money exposed according to user's
    # selected risk percentage.
    risk_amount = budget * risk_pct / 100

    active_trade = getattr(
        session,
        "trade",
        None
    )

    # =====================================================
    # ACTIVE TRADE
    # =====================================================

    if active_trade:

        trade_info = f"""
ACTIVE TRADE IS CURRENTLY OPEN.

Direction:
{getattr(active_trade, "direction", "UNKNOWN")}

Entry:
{getattr(active_trade, "entry", "UNKNOWN")}

Stop Loss:
{getattr(active_trade, "stop_loss", "UNKNOWN")}

Target:
{getattr(active_trade, "target", "UNKNOWN")}

IMPORTANT:
The existing trade has priority over finding a new signal.

Analyze whether the current trade should:
- HOLD
- WATCH
- EXIT-WATCH

Do not suggest opening another trade while this
trade is being monitored.
"""

    else:

        trade_info = """
NO ACTIVE TRADE.

Look for a new high-quality setup.

If the available evidence is insufficient,
return WAIT.
"""

    # =====================================================
    # GEMINI PROMPT
    # =====================================================

    prompt = f"""
You are SPARKS FOREX, an AI-assisted market
analysis engine.

Your job is to analyze the supplied market data
and available news/reports.

You DO NOT execute trades.
You DO NOT connect to MT5.
You DO NOT place orders.
You DO NOT guarantee profits.

Only analyze the information actually supplied.
Never invent prices, news, indicators or market data.

==================================================
SESSION
==================================================

Asset:
{asset}

Session Budget:
{budget:.2f} INR

Maximum Risk:
{risk_pct:.2f}%

Maximum Risk Amount:
{risk_amount:.2f} INR

==================================================
MARKET DATA
==================================================

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

==================================================
NEWS / REPORTS
==================================================

{news_text}

==================================================
TRADE STATUS
==================================================

{trade_info}

==================================================
ANALYSIS
==================================================

Evaluate:

1. Overall market trend
2. Momentum
3. SMA20 vs SMA50
4. RSI
5. Volatility
6. News/report impact
7. Potential support/resistance
8. Risk/reward
9. Signal quality
10. Existing trade conditions, if applicable

Only produce BUY or SELL when the available
evidence supports a reasonably strong setup.

Otherwise use WAIT.

==================================================
RESPONSE
==================================================

Return ONLY valid JSON.

Do not use Markdown.
Do not add explanations outside the JSON.

Use exactly:

{{
  "action": "BUY",
  "confidence": 75,
  "risk_level": "MEDIUM",
  "entry_reference": 0,
  "stop_loss_reference": 0,
  "target_reference": 0,
  "suggested_amount": 0,
  "trade_management": "WATCH",
  "summary": "Short explanation."
}}

==================================================
RULES
==================================================

action:
BUY, SELL or WAIT

confidence:
Integer from 0 to 100.

risk_level:
LOW, MEDIUM or HIGH.

entry_reference:
Use the supplied market information.
Use 0 if there is no reliable setup.

stop_loss_reference:
Use 0 if no reliable setup.

target_reference:
Use 0 if no reliable setup.

suggested_amount:
Must NEVER exceed:
{risk_amount:.2f} INR

If there is no valid BUY or SELL setup,
use 0.

trade_management:

If there is NO active trade:
NO-TRADE or WATCH

If there IS an active trade:
HOLD, WATCH or EXIT-WATCH

summary:
Short, factual explanation of why the AI reached
the decision.

Do not claim certainty.
"""


    # =====================================================
    # GEMINI REQUEST
    # =====================================================

    try:

        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is missing."
            )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
        )

        if response is None:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        raw = getattr(
            response,
            "text",
            ""
        )

        raw = _clean_json_response(raw)

        if not raw:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        log.info(
            "Gemini response received for %s",
            asset
        )

        # =================================================
        # PARSE JSON
        # =================================================

        try:

            result = json.loads(raw)

        except json.JSONDecodeError:

            log.error(
                "Invalid Gemini JSON: %s",
                raw
            )

            raise RuntimeError(
                "Gemini returned invalid JSON."
            )

        if not isinstance(result, dict):
            raise RuntimeError(
                "Gemini response is not a JSON object."
            )

        # =================================================
        # ACTION
        # =================================================

        action = str(
            result.get(
                "action",
                "WAIT"
            )
        ).upper().strip()

        if action not in (
            "BUY",
            "SELL",
            "WAIT"
        ):
            action = "WAIT"

        result["action"] = action

        # =================================================
        # CONFIDENCE
        # =================================================

        confidence = _safe_float(
            result.get(
                "confidence",
                0
            )
        )

        confidence = max(
            0,
            min(
                100,
                confidence
            )
        )

        result["confidence"] = confidence

        # =================================================
        # RISK LEVEL
        # =================================================

        risk_level = str(
            result.get(
                "risk_level",
                "UNKNOWN"
            )
        ).upper().strip()

        if risk_level not in (
            "LOW",
            "MEDIUM",
            "HIGH"
        ):
            risk_level = "UNKNOWN"

        result["risk_level"] = risk_level

        # =================================================
        # PRICE REFERENCES
        # =================================================

        result["entry_reference"] = _safe_float(
            result.get(
                "entry_reference",
                0
            )
        )

        result["stop_loss_reference"] = _safe_float(
            result.get(
                "stop_loss_reference",
                0
            )
        )

        result["target_reference"] = _safe_float(
            result.get(
                "target_reference",
                0
            )
        )

        # =================================================
        # SUGGESTED AMOUNT
        # =================================================

        suggested_amount = _safe_float(
            result.get(
                "suggested_amount",
                0
            )
        )

        # Never allow AI to exceed user's risk amount.
        suggested_amount = max(
            0,
            min(
                risk_amount,
                suggested_amount
            )
        )

        # WAIT means no suggested trade amount.
        if action == "WAIT":
            suggested_amount = 0

        result["suggested_amount"] = suggested_amount

        # =================================================
        # TRADE MANAGEMENT
        # =================================================

        trade_management = str(
            result.get(
                "trade_management",
                "WATCH"
            )
        ).upper().strip()

        allowed_management = (
            "NO-TRADE",
            "WATCH",
            "HOLD",
            "EXIT-WATCH"
        )

        if trade_management not in allowed_management:
            trade_management = "WATCH"

        result["trade_management"] = (
            trade_management
        )

        # =================================================
        # SUMMARY
        # =================================================

        result["summary"] = _clean_summary(
            result.get(
                "summary",
                "No additional analysis available."
            )
        )

        return result

    # =====================================================
    # JSON ERROR
    # =====================================================

    except json.JSONDecodeError:

        log.exception(
            "Gemini JSON parsing failed."
        )

        raise RuntimeError(
            "Gemini returned invalid JSON."
        )

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception as e:

        log.exception(
            "Gemini analysis failed for %s: %s",
            asset,
            e
        )

        raise
