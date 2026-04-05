"""API Server — HTTP + WebSocket for dashboard."""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone
from aiohttp import web
import aiohttp
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.agent.memory import AgentMemory
from src.perp.trader import PerpTrader
from src.agent.monitor import EventBus

logger = logging.getLogger("perphunter.server")
_state = {"memory": None, "perp": None, "events": None}
ws_clients = set()

async def broadcast(data):
    msg = json.dumps(data); dead = set()
    for ws in ws_clients:
        try: await ws.send_str(msg)
        except: dead.add(ws)
    ws_clients -= dead

async def handle_health(req): return web.json_response({"status": "ok"})
async def handle_dashboard(req):
    m, p, e = _state["memory"], _state["perp"], _state["events"]
    return web.json_response({"stats": m.get_stats() if m else {}, "scores": m.get_recent_scores(20) if m else [], "positions": p.get_portfolio_summary() if p else {}, "events": e.get_log(50) if e else []})

async def handle_ws(req):
    ws = web.WebSocketResponse(); await ws.prepare(req); ws_clients.add(ws)
    m, p = _state.get("memory"), _state.get("perp")
    if m and p: await ws.send_json({"type": "snapshot", "data": {"stats": m.get_stats(), "scores": m.get_recent_scores(20), "positions": p.get_portfolio_summary()}})
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT and json.loads(msg.data).get("action") == "ping": await ws.send_json({"type": "pong"})
    finally: ws_clients.discard(ws)
    return ws

@web.middleware
async def cors(req, handler):
    resp = web.Response() if req.method == "OPTIONS" else await handler(req)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

def create_app(memory=None, perp=None, events=None, **kw):
    _state.update({"memory": memory or AgentMemory(), "perp": perp or PerpTrader(), "events": events or EventBus()})
    app = web.Application(middlewares=[cors])
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/dashboard", handle_dashboard)
    app.router.add_get("/ws", handle_ws)
    return app

async def start_server(host="0.0.0.0", port=8420, **kw):
    app = create_app(**kw); runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, host, port).start()
    logger.info(f"Server at http://{host}:{port}"); return runner
