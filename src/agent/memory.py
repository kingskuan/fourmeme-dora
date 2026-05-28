"""Agent memory — persistent state."""
import json, logging, tempfile, os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("perphunter.memory")

class AgentMemory:
    def __init__(self, path=Path("data/agent_memory.json")):
        self.path = path; self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"launches_seen":0,"launches_acted":0,"total_pnl_bnb":0.0,"positions":[],"scored_tokens":[],"trade_history":[],"marketing_posts":[]}

    def save(self):
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        closed = False
        try:
            os.write(fd, json.dumps(self.data, indent=2).encode())
            os.fsync(fd); os.close(fd); closed = True
            os.replace(tmp, self.path)
        except BaseException:
            if not closed:
                try: os.close(fd)
                except OSError: pass
            try: os.unlink(tmp)
            except OSError: pass
            raise

    def record_score(self, d):
        self.data["launches_seen"] += 1
        self.data["scored_tokens"].append({**d, "recorded_at": datetime.now(timezone.utc).isoformat()})
        self.data["scored_tokens"] = self.data["scored_tokens"][-500:]
        self.save()

    def record_trade(self, d):
        self.data["launches_acted"] += 1
        self.data["trade_history"].append({**d, "recorded_at": datetime.now(timezone.utc).isoformat()})
        self.save()

    def record_position(self, p): self.data["positions"].append(p); self.save()

    def close_position(self, addr, pnl):
        self.data["positions"] = [p for p in self.data["positions"] if p.get("address") != addr]
        self.data["total_pnl_bnb"] += pnl; self.save()

    def record_marketing(self, d):
        self.data["marketing_posts"].append({**d, "posted_at": datetime.now(timezone.utc).isoformat()}); self.save()

    def get_stats(self): return {k: self.data[k] for k in ("launches_seen","launches_acted","total_pnl_bnb")} | {"active_positions": len(self.data["positions"]), "total_trades": len(self.data["trade_history"]), "total_posts": len(self.data["marketing_posts"])}
    def get_active_positions(self): return self.data["positions"]
    def get_recent_scores(self, n=20): return self.data["scored_tokens"][-n:]
