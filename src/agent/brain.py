"""AI Brain — scores meme coins and makes trading decisions."""
import json, logging
from dataclasses import dataclass
from datetime import datetime, timezone
import aiohttp
from config.settings import settings

logger = logging.getLogger("perphunter.brain")

@dataclass
class TokenScore:
    address: str; symbol: str; name: str; overall_score: int; meme_virality: int
    community_signal: int; token_metrics: int; sentiment_score: int; reasoning: str
    recommended_action: str; confidence: float; suggested_size_bnb: float
    risk_level: str; timestamp: str

SCORING_PROMPT = """You are PerpHunter, an elite AI agent scoring meme coin launches on Four.meme (BNB Chain).

TOKEN DATA:
{token_data}

SOCIAL SIGNALS:
{social_data}

Score across 4 dimensions (0-100):
1. Meme Virality: trend alignment, name appeal, cultural relevance
2. Community Signal: unique buyers, buy/sell ratio, holder distribution
3. Token Metrics: bonding curve, volume, liquidity, momentum
4. Sentiment: X/TG mentions, KOL attention

RESPOND IN STRICT JSON (no markdown):
{{"overall_score":<0-100>,"meme_virality":<0-100>,"community_signal":<0-100>,"token_metrics":<0-100>,"sentiment_score":<0-100>,"reasoning":"<2-3 sentences>","recommended_action":"<buy_lp|perp_long|watch|skip>","confidence":<0.0-1.0>,"suggested_size_bnb":<0.01-1.0>,"risk_level":"<low|medium|high|extreme>"}}

Score>=80: buy_lp or perp_long. 60-79: watch. <60: skip. Be honest, most tokens are trash."""

class AgentBrain:
    def __init__(self):
        self.provider = settings.ai.provider
        self.model = settings.ai.model

    async def _call_llm(self, prompt):
        async with aiohttp.ClientSession() as session:
            if self.provider == "anthropic":
                headers = {"x-api-key": settings.ai.anthropic_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
                payload = {"model": self.model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
                async with session.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers) as resp:
                    data = await resp.json()
                    return data["content"][0]["text"]
            else:
                headers = {"Authorization": f"Bearer {settings.ai.openai_key}", "Content-Type": "application/json"}
                payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}
                async with session.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as resp:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]

    async def score_token(self, token_metrics, social_data=None):
        prompt = SCORING_PROMPT.format(token_data=json.dumps(token_metrics, indent=2), social_data=json.dumps(social_data or {}, indent=2))
        try:
            response = (await self._call_llm(prompt)).strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"): response = response[4:]
            r = json.loads(response)
            return TokenScore(address=token_metrics["address"], symbol=token_metrics["symbol"], name=token_metrics["name"], overall_score=r["overall_score"], meme_virality=r["meme_virality"], community_signal=r["community_signal"], token_metrics=r["token_metrics"], sentiment_score=r["sentiment_score"], reasoning=r["reasoning"], recommended_action=r["recommended_action"], confidence=r["confidence"], suggested_size_bnb=r["suggested_size_bnb"], risk_level=r["risk_level"], timestamp=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            logger.error(f"Scoring failed for {token_metrics.get('symbol')}: {e}")
            return TokenScore(address=token_metrics["address"], symbol=token_metrics.get("symbol","???"), name=token_metrics.get("name","Unknown"), overall_score=0, meme_virality=0, community_signal=0, token_metrics=0, sentiment_score=0, reasoning=f"Failed: {e}", recommended_action="skip", confidence=0.0, suggested_size_bnb=0.0, risk_level="extreme", timestamp=datetime.now(timezone.utc).isoformat())

    async def generate_marketing_copy(self, token_name, token_symbol, score):
        prompt = f'Generate viral marketing for: {token_name} (${token_symbol}), Score: {score.overall_score}/100. Create: 1) tweet (280 chars max, $ticker, emojis) 2) telegram msg. Strict JSON: {{"tweet":"...","telegram_msg":"..."}}'
        try:
            response = (await self._call_llm(prompt)).strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"): response = response[4:]
            return json.loads(response)
        except:
            return {"tweet": f"${token_symbol} launched on @four_meme_! AI score: {score.overall_score}/100 #BNBChain", "telegram_msg": f"{token_name} (${token_symbol})\nScore: {score.overall_score}/100\n{score.reasoning}"}
