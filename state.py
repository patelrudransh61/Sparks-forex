from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

@dataclass
class Trade:
    asset: str
    direction: str
    entry: float
    stop_loss: float
    target: float
    taken_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class Session:
    budget: float
    asset: str
    risk_pct: float
    active: bool = True
    trade: Optional[Trade] = None
    last_ai_at: Optional[datetime] = None

SESSIONS: dict[int, Session] = {}
AUTHENTICATED: set[int] = set()
