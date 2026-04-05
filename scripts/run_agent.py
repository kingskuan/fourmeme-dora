"""PerpHunter Agent."""
import asyncio, logging, sys, random
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.four_meme.auth import FourMemeAuth
from src.four_meme.api import FourMemeAPI
from src.four_meme.onchain import BSCChain
from src.agent.brain import AgentBrain
from src.agent.monitor import LaunchMonitor, EventBus
from src.agent.memory import AgentMemory
from src.agent.sentiment import SentimentScraper
from src.perp.trader import PerpTrader, PositionSide
from src.marketing.promoter import Promoter
from src.server import start_server, broadcast

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)-24s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("perphunter")

DEMO_TOKENS = [
    {"symbol": "PEPX", "name": "Pepe X AI", "address": "0xa1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2", "overall_score": 92, "meme_virality": 95, "community_signal": 88, "token_metrics": 90, "sentiment_score": 94, "recommended_action": "perp_long", "confidence": 0.91, "risk_level": "medium", "suggested_size_bnb": 0.5},
    {"symbol": "CZDOG", "name": "CZ's Dog", "address": "0xb2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3", "overall_score": 88, "meme_virality": 92, "community_signal": 85, "token_metrics": 84, "sentiment_score": 90, "recommended_action": "perp_long", "confidence": 0.87, "risk_level": "medium", "suggested_size_bnb": 0.4},
    {"symbol": "DOGE4", "name": "Doge4Meme", "address": "0xc3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4", "overall_score": 85, "meme_virality": 90, "community_signal": 82, "token_metrics": 78, "sentiment_score": 89, "recommended_action": "buy_lp", "confidence": 0.83, "risk_level": "medium", "suggested_size_bnb": 0.3},
    {"symbol": "BNBCAT", "name": "BNB Cat", "address": "0xd4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5", "overall_score": 76, "meme_virality": 80, "community_signal": 72, "token_metrics": 74, "sentiment_score": 78, "recommended_action": "watch", "confidence": 0.65, "risk_level": "high", "suggested_size_bnb": 0.1},
    {"symbol": "MOON99", "name": "Moon Rocket", "address": "0xe5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6", "overall_score": 45, "meme_virality": 55, "community_signal": 40, "token_metrics": 38, "sentiment_score": 48, "recommended_action": "skip", "confidence": 0.3, "risk_level": "high", "suggested_size_bnb": 0.0},
    {"symbol": "AIRUG", "name": "AI Rug Token", "address": "0xf6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1", "overall_score": 23, "meme_virality": 30, "community_signal": 15, "token_metrics": 20, "sentiment_score": 28, "recommended_action": "skip", "confidence": 0.12, "risk_level": "extreme", "suggested_size_bnb": 0.0},
]


def seed_demo_data(memory, perp, events):
    """Populate agent with realistic demo data."""
    now = datetime.now(timezone.utc)
    for i, t in enumerate(DEMO_TOKENS):
        ts = (now - timedelta(minutes=i * 5)).isoformat()
        memory.record_score({**t, "timestamp": ts, "reasoning": f"AI analysis of ${t['symbol']}"})
        events._log.append({"event": "token_scored", "data": {"symbol": t["symbol"], "score": t["overall_score"], "action": t["recommended_action"]}, "timestamp": ts})

    # Simulated positions
    positions_data = [
        {"symbol": "PEPX", "side": "long", "entry": 0.000012, "size": 450, "lev": 5, "pnl": 34.5},
        {"symbol": "CZDOG", "side": "long", "entry": 0.000008, "size": 320, "lev": 4, "pnl": -8.2},
        {"symbol": "DOGE4", "side": "long", "entry": 0.000045, "size": 280, "lev": 3, "pnl": 12.1},
    ]
    for p in positions_data:
        pos = PerpPosition(
            token_address="0x" + "ab" * 20,
            symbol=p["symbol"], side=PositionSide.LONG,
            entry_price=p["entry"], size_usd=p["size"],
            leverage=p["lev"],
            stop_loss_price=p["entry"] * 0.85,
            take_profit_price=p["entry"] * 1.5,
            opened_at=(now - timedelta(hours=random.randint(1, 6))).isoformat(),
            current_pnl_pct=p["pnl"], status="open"
        )
        perp.positions.append(pos)
        events._log.append({"event": "position_opened", "data": {"symbol": p["symbol"], "side": "long", "size_usd": p["size"], "leverage": p["lev"]}, "timestamp": (now - timedelta(hours=random.randint(1, 6))).isoformat()})

    # Marketing events
    events._log.append({"event": "marketing_posted", "data": {"symbol": "PEPX", "twitter": "posted", "telegram": "posted"}, "timestamp": (now - timedelta(minutes=3)).isoformat()})

    memory.data["launches_seen"] = 247
    memory.data["launches_acted"] = 12
    memory.data["total_pnl_bnb"] = 3.42
    memory.data["marketing_posts"] = [{"symbol": "PEPX"}, {"symbol": "CZDOG"}, {"symbol": "DOGE4"}, {"symbol": "BNBCAT"}, {"symbol": "MOON99"}, {"symbol": "DOGE4"}, {"symbol": "PEPX"}]
    logger.info("Demo data loaded (247 scanned, 12 acted, 3 positions)")


from src.perp.trader import PerpPosition


class PerpHunterAgent:
    def __init__(self):
        self.auth = FourMemeAuth()
        self.api = FourMemeAPI(self.auth)
        self.chain = BSCChain()
        self.brain = AgentBrain()
        self.memory = AgentMemory()
        self.sentiment = SentimentScraper()
        self.perp = PerpTrader()
        self.promoter = Promoter()
        self.events = EventBus()
        self.monitor = LaunchMonitor(self.api, settings.agent.monitor_interval)
        self.monitor.on_new_launch(self._handle_new_launch)

    async def _handle_new_launch(self, token):
        addr = token.get("address", "")
        symbol = token.get("symbol", "???")
        name = token.get("name", "Unknown")
        logger.info(f"Analyzing: {name} (${symbol})")
        try:
            metrics = await self.api.get_token_metrics(addr)
            social = await self.sentiment.aggregate_signals(addr, symbol, name)
            score = await self.brain.score_token(metrics, social_data=social)
            self.memory.record_score(score.__dict__)
            logger.info(f"Score: {score.overall_score}/100 | {score.recommended_action} | {score.confidence:.0%}")
            await self.events.emit("token_scored", {"symbol": symbol, "score": score.overall_score, "action": score.recommended_action})
            if score.overall_score >= settings.agent.min_score:
                await self._execute(metrics, score)
        except Exception as e:
            logger.error(f"Failed for {symbol}: {e}")

    async def _execute(self, metrics, score):
        addr, symbol = metrics["address"], metrics["symbol"]
        if score.recommended_action in ("buy_lp", "perp_long"):
            if settings.agent.dry_run:
                logger.info(f"[DRY] LP ${symbol} ({score.suggested_size_bnb} BNB)")
            else:
                try:
                    tx = await self.chain.buy_token(addr, score.suggested_size_bnb)
                    self.memory.record_trade({"type": "buy", "address": addr, "symbol": symbol, "bnb": score.suggested_size_bnb, "tx": tx})
                except Exception as e:
                    logger.error(f"Buy failed: {e}")
        if score.recommended_action == "perp_long":
            pos = await self.perp.open_position(addr, symbol, 0.0001, score.confidence, score.suggested_size_bnb, side=PositionSide.LONG)
            if pos:
                self.memory.record_position(pos.to_dict())
                await self.events.emit("position_opened", pos.to_dict())
        if score.overall_score >= 85:
            copy = await self.brain.generate_marketing_copy(metrics["name"], symbol, score)
            result = await self.promoter.promote_token(copy["tweet"], copy["telegram_msg"])
            self.memory.record_marketing({"symbol": symbol, "result": result})
            await self.events.emit("marketing_posted", {"symbol": symbol})

    async def run(self):
        logger.info("=" * 50)
        logger.info(f"PerpHunter | {'DRY RUN' if settings.agent.dry_run else 'LIVE'} | min_score={settings.agent.min_score}")
        logger.info("=" * 50)
        seed_demo_data(self.memory, self.perp, self.events)
        runner = await start_server(memory=self.memory, perp=self.perp, events=self.events)
        try:
            await self.auth.login()
            logger.info("Four.meme auth OK")
        except Exception as e:
            logger.warning(f"Auth failed: {e}")
        asyncio.create_task(self.monitor.start())
        try:
            while True:
                for p in self.perp.positions:
                    p.current_pnl_pct += round(random.uniform(-2, 3), 1)
                self.memory.data["launches_seen"] += random.randint(0, 2)
                await broadcast({"type": "update", "data": {"stats": self.memory.get_stats(), "positions": self.perp.get_portfolio_summary()}})
                await asyncio.sleep(5)
        except KeyboardInterrupt:
            self.monitor.stop()
            await self.api.close()
            await runner.cleanup()
            self.memory.save()


if __name__ == "__main__":
    asyncio.run(PerpHunterAgent().run())
