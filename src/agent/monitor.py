"""Real-time Four.meme launch monitor."""
import asyncio, logging
from datetime import datetime, timezone
from typing import Callable
from src.four_meme.api import FourMemeAPI

logger = logging.getLogger("perphunter.monitor")

class LaunchMonitor:
    def __init__(self, api: FourMemeAPI, interval=10):
        self.api = api; self.interval = interval; self.seen_tokens = set(); self.callbacks = []; self._running = False

    def on_new_launch(self, callback): self.callbacks.append(callback)

    async def _check_new_launches(self):
        try:
            tokens = await self.api.get_trending_tokens(limit=30)
            for token in tokens:
                addr = token.get("address", "")
                if addr and addr not in self.seen_tokens:
                    self.seen_tokens.add(addr)
                    logger.info(f"New: {token.get('name')} ({token.get('symbol')})")
                    for cb in self.callbacks:
                        try: await cb(token)
                        except Exception as e: logger.error(f"Callback error: {e}")
        except Exception as e: logger.warning(f"Poll failed: {e}")

    async def start(self):
        self._running = True
        logger.info(f"Monitor started (interval={self.interval}s)")
        while self._running:
            await self._check_new_launches()
            await asyncio.sleep(self.interval)

    def stop(self): self._running = False

class EventBus:
    def __init__(self): self._handlers = {}; self._log = []
    def on(self, event, handler): self._handlers.setdefault(event, []).append(handler)
    async def emit(self, event, data):
        self._log.append({"event": event, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
        for h in self._handlers.get(event, []):
            try: await h(data)
            except Exception as e: logger.error(f"Handler error: {e}")
    def get_log(self, limit=100): return self._log[-limit:]
