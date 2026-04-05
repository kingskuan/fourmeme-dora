"""Four.meme wallet-signed authentication."""
import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct
from config.settings import settings

API_BASE = settings.four_meme.api_base

class FourMemeAuth:
    def __init__(self, private_key: str = None):
        self.private_key = private_key or settings.wallet.private_key
        self.account = Account.from_key(self.private_key)
        self.address = self.account.address
        self.access_token = None

    async def login(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/public/user/login/nonce", params={"accountAddress": self.address}) as resp:
                data = await resp.json()
                nonce = data["data"]["nonce"]
            message = f"You are sign in Meme {nonce}"
            msg = encode_defunct(text=message)
            signed = self.account.sign_message(msg)
            signature = signed.signature.hex()
            async with session.post(f"{API_BASE}/public/user/login", json={"accountAddress": self.address, "signature": f"0x{signature}"}) as resp:
                data = await resp.json()
                self.access_token = data["data"]["accessToken"]
        return self.access_token

    def auth_headers(self) -> dict:
        if not self.access_token:
            raise ValueError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
