import json
import httpx
from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_SITE_URL, OPENROUTER_SITE_NAME

def build_prompt(snapshot, news, session):
    trade_context = None
    if session.trade:
        trade_context = {
            "direction": session.trade.direction,
            "entry": session.trade.entry,
            "stop_loss": session.trade.stop_loss,
            "target": session.trade.target,
        }

    payload = {
        "asset": snapshot.asset,
        "market": {
            "price": snapshot.price,
            "one_period_change_pct": snapshot.change_pct,
            "recent_high": snapshot.high,
            "recent_low": snapshot.low,
            "volume": snapshot.volume,
            "sma20": snapshot.sma20,
            "sma50": snapshot.sma50,
            "rsi14": snapshot.rsi14,
            "recent_volatility_pct": snapshot.volatility_pct,
        },
        "news": [{"title": n["title"], "published": n["published"]} for n in news],
        "session": {"budget": session.budget, "risk_pct": session.risk_pct},
        "active_trade": trade_context,
    }

    schema = {
        "action": "BUY | SELL | WAIT | HOLD | EXIT_WATCH",
        "confidence": "0-100",
        "entry_reference": "number",
        "stop_loss_reference": "number",
        "target_reference": "number",
        "risk_level": "LOW | MEDIUM | HIGH",
        "suggested_amount": "number",
        "summary": "short English explanation",
        "trade_management": "short English instruction"
    }

    rules = (
        "You are an analytical market assistant. Do not claim certainty and do not pretend you can see future prices.\n\n"
        "Analyze the supplied market snapshot and news. If an active trade exists, prioritize monitoring it rather than looking for a new setup.\n\n"
        "Return ONLY valid JSON matching this schema:\n" + json.dumps(schema) + "\n\n"
        "Rules:\n"
        "- BUY/SELL is a potential setup, never a guarantee.\n"
        "- For a new setup, suggested_amount must not exceed the session budget and should respect the stated risk percentage.\n"
        "- If evidence is insufficient, use WAIT.\n"
        "- With an active trade, use HOLD when conditions remain acceptable and EXIT_WATCH when conditions materially deteriorate.\n"
        "- Keep all text in English.\n"
        "- Do not invent news.\n"
        "- Numbers must be JSON numbers, not strings.\n\n"
        "DATA:\n"
    )
    return rules + json.dumps(payload, ensure_ascii=False)

async def analyze(snapshot, news, session):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_SITE_NAME,
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. No markdown fences."},
            {"role": "user", "content": build_prompt(snapshot, news, session)}
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post("https://openrouter.ai/api/v1/chat/completions",
                                     headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()

    result = json.loads(content)
    result["confidence"] = max(0, min(100, float(result.get("confidence", 0))))
    for key in ("entry_reference", "stop_loss_reference", "target_reference", "suggested_amount"):
        try:
            result[key] = float(result.get(key, 0))
        except Exception:
            result[key] = 0.0
    return result
