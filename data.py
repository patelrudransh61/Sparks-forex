from dataclasses import dataclass
import math
import yfinance as yf
from .assets import ticker_for

@dataclass
class MarketSnapshot:
    asset: str
    price: float
    change_pct: float
    high: float
    low: float
    volume: float
    sma20: float
    sma50: float
    rsi14: float
    volatility_pct: float

def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))

def get_snapshot(asset: str) -> MarketSnapshot:
    ticker = ticker_for(asset)
    df = yf.download(ticker, period="3mo", interval="1h", progress=False,
                     auto_adjust=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError(f"No market data available for {asset}")

    if hasattr(df.columns, "levels"):
        try:
            df = df.xs(ticker, axis=1, level=-1)
        except Exception:
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass

    close = df["Close"].dropna()
    high = df["High"].dropna()
    low = df["Low"].dropna()
    volume = df["Volume"].dropna() if "Volume" in df else None

    if len(close) < 55:
        raise RuntimeError(f"Not enough candles available for {asset}")

    returns = close.pct_change().dropna()
    price = float(close.iloc[-1])
    previous = float(close.iloc[-2])
    change_pct = ((price - previous) / previous) * 100
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    rsi = float(_rsi(close, 14).iloc[-1])
    volatility_pct = float(returns.tail(20).std() * math.sqrt(20) * 100)

    return MarketSnapshot(
        asset=asset, price=price, change_pct=change_pct,
        high=float(high.iloc[-1]), low=float(low.iloc[-1]),
        volume=float(volume.iloc[-1]) if volume is not None and len(volume) else 0.0,
        sma20=sma20, sma50=sma50, rsi14=rsi,
        volatility_pct=volatility_pct
    )
