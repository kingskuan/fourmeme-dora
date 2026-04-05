"""Four.meme REST API client — monitors launches, fetches token data."""
import logging
from datetime import datetime, timezone
import aiohttp
from config.settings import settings
from src.four_meme.auth import FourMemeAuth

logger = logging.getLogger("perphunter.api")
API_BASE = settings.four_meme.api_base
BITQUERY_URL = "https://streaming.bitquery.io/graphql"

class FourMemeAPI:
    def __init__(self, auth: FourMemeAuth):
        self.auth = auth
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_trending_tokens(self, limit=20):
        session = await self._get_session()
        async with session.get(f"{API_BASE}/public/token/list", params={"pageSize": limit, "pageNo": 1, "orderBy": "createTime"}) as resp:
            data = await resp.json()
            return data.get("data", {}).get("list", [])

    async def get_token_detail(self, token_address):
        session = await self._get_session()
        async with session.get(f"{API_BASE}/public/token/detail", params={"address": token_address}) as resp:
            data = await resp.json()
            return data.get("data", {})

    async def get_token_trades(self, token_address, limit=50):
        session = await self._get_session()
        async with session.get(f"{API_BASE}/public/token/trade/list", params={"address": token_address, "pageSize": limit}) as resp:
            data = await resp.json()
            return data.get("data", {}).get("list", [])

    async def get_token_metrics(self, token_address):
        detail = await self.get_token_detail(token_address)
        trades = await self.get_token_trades(token_address, limit=100)
        buy_count = sum(1 for t in trades if t.get("type") == "buy")
        sell_count = sum(1 for t in trades if t.get("type") == "sell")
        unique_buyers = len(set(t.get("user", "") for t in trades if t.get("type") == "buy"))
        total_volume_bnb = sum(float(t.get("bnbAmount", 0)) for t in trades)
        bonding_progress = float(detail.get("raisedAmount", 0)) / max(float(detail.get("targetAmount", 1)), 0.001)
        return {
            "address": token_address, "name": detail.get("name", "Unknown"), "symbol": detail.get("symbol", "???"),
            "description": detail.get("description", ""), "creator": detail.get("creator", ""),
            "created_at": detail.get("createTime", ""), "bonding_progress_pct": round(bonding_progress * 100, 2),
            "raised_bnb": float(detail.get("raisedAmount", 0)), "target_bnb": float(detail.get("targetAmount", 0)),
            "total_trades": len(trades), "buy_count": buy_count, "sell_count": sell_count,
            "buy_sell_ratio": round(buy_count / max(sell_count, 1), 2), "unique_buyers": unique_buyers,
            "total_volume_bnb": round(total_volume_bnb, 4), "is_graduated": detail.get("status") == "graduated",
            "holder_count": int(detail.get("holderCount", 0)),
        }

    async def upload_image(self, image_path):
        session = await self._get_session()
        headers = self.auth.auth_headers()
        del headers["Content-Type"]
        with open(image_path, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("file", f, filename="logo.png", content_type="image/png")
            async with session.post(f"{API_BASE}/private/tool/upload", data=form, headers=headers) as resp:
                data = await resp.json()
                return data["data"]["url"]

    async def create_token_request(self, name, symbol, description, image_url, raise_bnb=0.5):
        session = await self._get_session()
        async with session.post(f"{API_BASE}/private/token/create", json={"name": name, "symbol": symbol, "description": description, "imageUrl": image_url, "raiseBnb": str(raise_bnb)}, headers=self.auth.auth_headers()) as resp:
            data = await resp.json()
            return data.get("data", {})
