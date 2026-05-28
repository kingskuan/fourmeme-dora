"""Perp trading engine with risk management."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from config.settings import settings

logger = logging.getLogger("perphunter.perp")

class PositionSide(str, Enum):
    LONG = "long"; SHORT = "short"

@dataclass
class PerpPosition:
    token_address: str; symbol: str; side: PositionSide; entry_price: float
    size_usd: float; leverage: int; stop_loss_price: float; take_profit_price: float
    opened_at: str; tx_hash: str = ""; current_pnl_pct: float = 0.0; status: str = "open"
    def to_dict(self):
        return {"address": self.token_address, "symbol": self.symbol, "side": self.side.value, "entry_price": self.entry_price, "size_usd": self.size_usd, "leverage": self.leverage, "stop_loss": self.stop_loss_price, "take_profit": self.take_profit_price, "opened_at": self.opened_at, "pnl_pct": self.current_pnl_pct, "status": self.status}

class RiskManager:
    def __init__(self):
        self.max_lev = settings.perp.max_leverage; self.max_pos = settings.perp.max_position_usd
        self.sl_pct = settings.perp.stop_loss_pct; self.tp_pct = settings.perp.take_profit_pct

    def calculate_position(self, confidence, suggested_bnb, bnb_usd, price, active_count):
        if active_count >= 5: return None
        size = min(suggested_bnb * bnb_usd * confidence, self.max_pos)
        lev = min(int(2 + confidence * 8), self.max_lev)
        if size < 10: return None
        return {"size_usd": round(size,2), "leverage": lev, "stop_loss_price": price*(1-self.sl_pct/100), "take_profit_price": price*(1+self.tp_pct/100)}

class PerpTrader:
    def __init__(self):
        self.risk = RiskManager(); self.positions = []; self.closed = []; self.dry_run = settings.agent.dry_run

    async def open_position(self, token_address, symbol, current_price, confidence, suggested_size_bnb, bnb_price_usd=600.0, side=PositionSide.LONG):
        calc = self.risk.calculate_position(confidence, suggested_size_bnb, bnb_price_usd, current_price, len(self.positions))
        if not calc: return None
        pos = PerpPosition(token_address=token_address, symbol=symbol, side=side, entry_price=current_price, size_usd=calc["size_usd"], leverage=calc["leverage"], stop_loss_price=calc["stop_loss_price"], take_profit_price=calc["take_profit_price"], opened_at=datetime.now(timezone.utc).isoformat(), tx_hash=f"DRY_RUN_{token_address[:10]}" if self.dry_run else "")
        logger.info(f"{'[DRY] ' if self.dry_run else ''}Opened {side.value} ${symbol} | ${calc['size_usd']} | {calc['leverage']}x")
        self.positions.append(pos); return pos

    async def check_positions(self, prices):
        for pos in list(self.positions):
            p = prices.get(pos.token_address)
            if not p: continue
            pnl = ((p - pos.entry_price) / pos.entry_price * 100 * pos.leverage) if pos.side == PositionSide.LONG else ((pos.entry_price - p) / pos.entry_price * 100 * pos.leverage)
            pos.current_pnl_pct = round(pnl, 2)
            if (pos.side == PositionSide.LONG and (p <= pos.stop_loss_price or p >= pos.take_profit_price)) or (pos.side == PositionSide.SHORT and (p >= pos.stop_loss_price or p <= pos.take_profit_price)):
                pos.status = "closed"; self.positions.remove(pos); self.closed.append(pos)

    def get_portfolio_summary(self):
        return {"active_positions": len(self.positions), "positions": [p.to_dict() for p in self.positions], "closed_count": len(self.closed), "total_realized_pnl_pct": sum(p.current_pnl_pct for p in self.closed)}
