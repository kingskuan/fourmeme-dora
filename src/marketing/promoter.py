"""Auto marketing — X/Twitter + Telegram."""
import asyncio, logging
import aiohttp
from config.settings import settings

logger = logging.getLogger("perphunter.marketing")

class Promoter:
    def __init__(self): self.dry_run = settings.agent.dry_run; self.tg_token = settings.marketing.telegram_bot_token; self.tg_channel = settings.marketing.telegram_channel_id

    async def post_tweet(self, text):
        if self.dry_run: logger.info(f"[DRY] Tweet: {text[:80]}..."); return {"status": "dry_run"}
        try:
            import tweepy
            client = tweepy.Client(consumer_key=settings.marketing.twitter_api_key, consumer_secret=settings.marketing.twitter_api_secret, access_token=settings.marketing.twitter_access_token, access_token_secret=settings.marketing.twitter_access_secret)
            r = client.create_tweet(text=text); return {"status": "posted", "id": r.data["id"]}
        except Exception as e: return {"status": "error", "error": str(e)}

    async def post_telegram(self, text):
        if self.dry_run: logger.info(f"[DRY] TG: {text[:80]}..."); return {"status": "dry_run"}
        if not self.tg_token: return {"status": "skipped"}
        async with aiohttp.ClientSession() as s:
            async with s.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", json={"chat_id": self.tg_channel, "text": text, "parse_mode": "HTML"}) as r:
                return await r.json()

    async def promote_token(self, tweet, tg_msg):
        r = await asyncio.gather(self.post_tweet(tweet), self.post_telegram(tg_msg))
        return {"twitter": r[0], "telegram": r[1]}
