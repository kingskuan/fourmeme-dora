"""Backtester — score historical launches."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.four_meme.auth import FourMemeAuth
from src.four_meme.api import FourMemeAPI
from src.agent.brain import AgentBrain

async def backtest(n=20):
    print(f"PerpHunter Backtester ({n} tokens)")
    auth = FourMemeAuth(); api = FourMemeAPI(auth); brain = AgentBrain()
    try: await auth.login(); print("Auth OK")
    except: print("Auth failed")
    tokens = await api.get_trending_tokens(limit=n)
    results = []
    for i, t in enumerate(tokens):
        addr, sym = t.get("address",""), t.get("symbol","???")
        try:
            m = await api.get_token_metrics(addr); s = await brain.score_token(m)
            results.append({"symbol":sym,"score":s.overall_score,"action":s.recommended_action})
            print(f"[{i+1}] ${sym}: {s.overall_score} -> {s.recommended_action}")
        except Exception as e: print(f"[{i+1}] ${sym}: FAILED {e}")
        await asyncio.sleep(1)
    Path("data").mkdir(exist_ok=True); Path("data/backtest.json").write_text(json.dumps(results, indent=2))
    acted = [r for r in results if r["action"] in ("buy_lp","perp_long")]
    print(f"\n{len(results)} scored, {len(acted)} actionable ({len(acted)/max(len(results),1)*100:.0f}%)")
    await api.close()

if __name__ == "__main__": asyncio.run(backtest(int(sys.argv[1]) if len(sys.argv)>1 else 20))
