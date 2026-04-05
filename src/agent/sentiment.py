"""Social sentiment — X/Twitter, Telegram, DexScreener."""
import asyncio, logging
from datetime import datetime, timezone
import aiohttp

logger = logging.getLogger("perphunter.sentiment")

class SentimentScraper:
    def __init__(self): self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed: self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed: await self._session.close()

    async def search_twitter_mentions(self, symbol, name):
        return {"query": f"${symbol}", "mention_count": 0, "kol_mentions": [], "trending": False, "sentiment_ratio": 0.5, "source": "twitter"}

    async def search_telegram_mentions(self, symbol):
        return {"query": f"${symbol}", "mention_count": 0, "sentiment_ratio": 0.5, "source": "telegram"}

    async def get_dexscreener_data(self, token_address):
        session = await self._get_session()
        try:
            async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        p = pairs[0]
                        return {"price_usd": float(p.get("priceUsd",0)), "volume_24h": float(p.get("volume",{}).get("h24",0)), "liquidity_usd": float(p.get("liquidity",{}).get("usd",0)), "source": "dexscreener"}
            return {"source": "dexscreener", "error": "No pairs"}
        except Exception as e: return {"source": "dexscreener", "error": str(e)}

    async def aggregate_signals(self, token_address, symbol, name):
        tw, tg, dex = await asyncio.gather(self.search_twitter_mentions(symbol, name), self.search_telegram_mentions(symbol), self.get_dexscreener_data(token_address))
        total = tw.get("mention_count",0) + tg.get("mention_count",0)
        score = min(100, total * 5 + (20 if tw.get("kol_mentions") else 0) + (30 if tw.get("trending") else 0))
        return {"twitter": tw, "telegram": tg, "dexscreener": dex, "composite_social_score": score, "total_mentions": total}
