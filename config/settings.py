"""PerpHunter configuration — loads from .env"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
load_dotenv()

@dataclass
class WalletConfig:
    private_key: str = os.getenv("WALLET_PRIVATE_KEY", "")
    address: str = os.getenv("WALLET_ADDRESS", "")

@dataclass
class BSCConfig:
    rpc_url: str = os.getenv("BSC_RPC_URL", "https://bsc-dataseed1.binance.org")
    wss_url: str = os.getenv("BSC_WSS_URL", "wss://bsc-ws-node.nariox.org:443")
    chain_id: int = 56

@dataclass
class FourMemeConfig:
    api_base: str = os.getenv("FOUR_MEME_API_BASE", "https://four.meme/meme-api/v1")
    token_manager_v2: str = "0x5c952063c7fc8610FFDB798152D69F0B9550762b"

@dataclass
class AIConfig:
    provider: str = os.getenv("AI_PROVIDER", "anthropic")
    anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("AI_MODEL", "claude-sonnet-4-20250514")

@dataclass
class PerpConfig:
    dex: str = os.getenv("PERP_DEX", "myx")
    max_leverage: int = int(os.getenv("PERP_MAX_LEVERAGE", "5"))
    max_position_usd: float = float(os.getenv("PERP_MAX_POSITION_USD", "500"))
    stop_loss_pct: float = float(os.getenv("PERP_STOP_LOSS_PCT", "15"))
    take_profit_pct: float = float(os.getenv("PERP_TAKE_PROFIT_PCT", "50"))

@dataclass
class LPConfig:
    max_bnb: float = float(os.getenv("LP_MAX_BNB", "0.5"))
    auto_remove_hours: int = int(os.getenv("LP_AUTO_REMOVE_HOURS", "24"))

@dataclass
class MarketingConfig:
    twitter_api_key: str = os.getenv("TWITTER_API_KEY", "")
    twitter_api_secret: str = os.getenv("TWITTER_API_SECRET", "")
    twitter_access_token: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
    twitter_access_secret: str = os.getenv("TWITTER_ACCESS_SECRET", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

@dataclass
class AgentConfig:
    monitor_interval: int = int(os.getenv("MONITOR_INTERVAL_SECONDS", "10"))
    min_score: int = int(os.getenv("MIN_SCORE_TO_ACT", "75"))
    profit_recycle_pct: float = float(os.getenv("PROFIT_RECYCLE_PCT", "20"))
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"

@dataclass
class Settings:
    wallet: WalletConfig = field(default_factory=WalletConfig)
    bsc: BSCConfig = field(default_factory=BSCConfig)
    four_meme: FourMemeConfig = field(default_factory=FourMemeConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    perp: PerpConfig = field(default_factory=PerpConfig)
    lp: LPConfig = field(default_factory=LPConfig)
    marketing: MarketingConfig = field(default_factory=MarketingConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

settings = Settings()
