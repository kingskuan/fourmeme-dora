"""PerpHunter Agent — main loop."""
import asyncio, logging, sys
from pathlib import Path
from datetime import datetime, timezone
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

class PerpHunterAgent:
    def __init__(self):
        self.auth = FourMemeAuth(); self.api = FourMemeAPI(self.auth); self.chain = BSCChain()
        self.brain = AgentBrain(); self.memory = AgentMemory(); self.sentiment = SentimentScraper()
        self.perp = PerpTrader(); self.promoter = Promoter(); self.events = EventBus()
        self.monitor = LaunchMonitor(self.api, settings.agent.monitor_interval)
        self.monitor.on_new_launch(self._handle_new_launch)

    async def _handle_new_launch(self, token):
        addr, symbol, name = token.get("address",""), token.get("symbol","???"), token.get("name","Unknown")
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
        except Exception as e: logger.error(f"Failed for {symbol}: {e}")

    async def _execute(self, metrics, score):
        addr, symbol = metrics["address"], metrics["symbol"]
        if score.recommended_action in ("buy_lp","perp_long"):
            if settings.agent.dry_run: logger.info(f"[DRY] LP ${symbol} ({score.suggested_size_bnb} BNB)")
            else:
                try:
                    tx = await self.chain.buy_token(addr, score.suggested_size_bnb)
                    self.memory.record_trade({"type":"buy","address":addr,"symbol":symbol,"bnb":score.suggested_size_bnb,"tx":tx})
                except Exception as e: logger.error(f"Buy failed: {e}")
        if score.recommended_action == "perp_long":
            pos = await self.perp.open_position(addr, symbol, 0.0001, score.confidence, score.suggested_size_bnb, side=PositionSide.LONG)
            if pos: self.memory.record_position(pos.to_dict()); await self.events.emit("position_opened", pos.to_dict())
        if score.overall_score >= 85:
            copy = await self.brain.generate_marketing_copy(metrics["name"], symbol, score)
            result = await self.promoter.promote_token(copy["tweet"], copy["telegram_msg"])
            self.memory.record_marketing({"symbol":symbol, "result":result})
            await self.events.emit("marketing_posted", {"symbol":symbol})

    async def run(self):
        logger.info("=" * 50)
        logger.info(f"PerpHunter | {'DRY RUN' if settings.agent.dry_run else 'LIVE'} | min_score={settings.agent.min_score}")
        logger.info("=" * 50)
        runner = await start_server(memory=self.memory, perp=self.perp, events=self.events)
        try: await self.auth.login(); logger.info("Four.meme auth OK")
        except Exception as e: logger.warning(f"Auth failed: {e}")
        asyncio.create_task(self.monitor.start())
    try:
            while True:
                await broadcast({"type": "update", "data": {"stats": self.memory.get_stats(), "positions": self.perp.get_portfolio_summary()}})
                await asyncio.sleep(5)
        except KeyboardInterrupt:
            self.monitor.stop(); await self.api.close(); await runner.cleanup(); self.memory.save()


if __name__ == "__main__": asyncio.run(PerpHunterAgent().run())
