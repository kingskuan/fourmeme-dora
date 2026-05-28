"""API Server with HTML dashboard."""
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
_ws_clients = set()

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PerpHunter Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020617;color:#e2e8f0;font-family:-apple-system,system-ui,sans-serif;min-height:100vh}
.header{border-bottom:1px solid #1e293b;padding:16px;display:flex;align-items:center;gap:12px;background:linear-gradient(180deg,#0f172a,#020617)}
.logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#f59e0b,#dc2626);display:flex;align-items:center;justify-content:center;font-size:20px}
.title{font-size:18px;font-weight:800;letter-spacing:-0.5px}
.subtitle{font-size:11px;color:#475569}
.badge{padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700;display:inline-flex;align-items:center;gap:6px}
.live{background:#052e16;border:1px solid #166534;color:#4ade80}
.dot{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 8px #22c55e;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.stats{padding:16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.stat{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:14px 16px}
.stat-label{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.stat-value{font-size:24px;font-weight:800;font-family:'Courier New',monospace}
.stat-sub{font-size:11px;color:#475569;margin-top:2px}
.section{padding:0 16px 16px}
.section-title{font-size:14px;font-weight:700;margin-bottom:10px;color:#94a3b8}
.card{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:14px;margin-bottom:8px}
.score-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.score-num{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;font-family:monospace}
.score-green{background:#22c55e1a;border:1px solid #22c55e33;color:#22c55e}
.score-yellow{background:#f59e0b1a;border:1px solid #f59e0b33;color:#f59e0b}
.score-red{background:#ef44441a;border:1px solid #ef444433;color:#ef4444}
.tag{padding:2px 8px;border-radius:5px;font-size:9px;font-weight:800;letter-spacing:.5px}
.tag-green{background:#16a34a1a;color:#4ade80;border:1px solid #16a34a33}
.tag-yellow{background:#d976061a;color:#fbbf24;border:1px solid #d9760633}
.tag-gray{background:#6b72801a;color:#9ca3af;border:1px solid #6b728033}
.bar-wrap{height:5px;background:#1e293b;border-radius:3px;overflow:hidden;margin:3px 0}
.bar{height:100%;border-radius:3px;transition:width .8s}
.bar-row{display:flex;align-items:center;gap:8px;font-size:11px;margin-bottom:2px}
.bar-label{color:#64748b;width:64px;flex-shrink:0}
.bar-val{width:24px;text-align:right;font-weight:700;font-family:monospace;font-size:11px}
.event{padding:10px 12px;border-bottom:1px solid #0f172a;display:flex;align-items:center;gap:8px;font-size:12px}
.event-time{font-family:monospace;color:#334155;font-size:10px;width:32px;text-align:right;flex-shrink:0}
.event-name{font-weight:700;color:#94a3b8;min-width:100px}
.event-data{color:#475569;font-family:monospace;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.footer{padding:16px;text-align:center;color:#1e293b;font-size:10px;letter-spacing:1px;border-top:1px solid #0f172a}
.pnl-pos{color:#22c55e}.pnl-neg{color:#ef4444}
.flex{display:flex;align-items:center;gap:8px}
.tabs{display:flex;padding:0 16px;border-bottom:1px solid #1e293b}
.tab{padding:10px 16px;font-size:12px;font-weight:700;color:#475569;background:none;border:none;cursor:pointer;border-bottom:2px solid transparent}
.tab.active{color:#f8fafc;border-bottom-color:#f59e0b}
#scores-tab,#positions-tab,#events-tab{display:none}
#scores-tab.active-content,#positions-tab.active-content,#events-tab.active-content{display:block}
</style>
</head>
<body>
<div class="header">
<div class="logo">&#127919;</div>
<div><div class="title">PerpHunter</div><div class="subtitle">AI Perp Hunt + Auto Liquidity Agent</div></div>
<div style="margin-left:auto" class="badge live"><div class="dot"></div>LIVE</div>
</div>
<div class="stats" id="stats"></div>
<div class="tabs">
<button class="tab active" onclick="showTab('scores')">&#128269; Scores</button>
<button class="tab" onclick="showTab('positions')">&#128200; Perps</button>
<button class="tab" onclick="showTab('events')">&#128203; Log</button>
</div>
<div class="section" style="padding-top:16px">
<div id="scores-tab" class="active-content"></div>
<div id="positions-tab"></div>
<div id="events-tab"></div>
</div>
<div class="footer">PERPHUNTER &middot; FOUR.MEME AI SPRINT &middot; BNB CHAIN &middot; 2026</div>
<script>
const API = window.location.origin;
function scoreClass(s){return s>=80?'green':s>=60?'yellow':'red'}
function timeAgo(ts){const s=Math.floor((Date.now()-new Date(ts).getTime())/1000);return s<60?s+'s':s<3600?Math.floor(s/60)+'m':Math.floor(s/3600)+'h'}
function actionLabel(a){return{perp_long:'PERP LONG',buy_lp:'BUY+LP',watch:'WATCH',skip:'SKIP'}[a]||'SKIP'}
function actionClass(a){return{perp_long:'green',buy_lp:'green',watch:'yellow'}[a]||'gray'}
function showTab(name){
document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
document.querySelectorAll('[id$="-tab"]').forEach(t=>t.classList.remove('active-content'));
document.getElementById(name+'-tab').classList.add('active-content');
event.target.classList.add('active');
}
function renderStats(s){
document.getElementById('stats').innerHTML=
[['&#128225;','Scanned',s.launches_seen,'tokens'],['&#9889;','Acted',s.launches_acted,((s.launches_acted/Math.max(s.launches_seen,1))*100).toFixed(1)+'% rate'],['&#128200;','Positions',s.active_positions,'active'],['&#128176;','P&L (BNB)',s.total_pnl_bnb?.toFixed(2)||'0.00','~$'+(s.total_pnl_bnb*600).toFixed(0)],['&#128172;','Posts',s.total_posts,'X+TG']].map(([i,l,v,sub])=>`<div class="stat"><div class="stat-label">${i} ${l}</div><div class="stat-value">${v}</div><div class="stat-sub">${sub}</div></div>`).join('');
}
function renderScores(scores){
document.getElementById('scores-tab').innerHTML=scores.length?scores.map(t=>{
const sc=scoreClass(t.overall_score);
return`<div class="card"><div class="score-header"><div class="flex"><div class="score-num score-${sc}">${t.overall_score}</div><div><div style="font-weight:800">$${t.symbol} <span style="color:#475569;font-weight:400;font-size:12px">${t.name||''}</span></div><div style="font-size:10px;color:#334155;font-family:monospace">${(t.address||'').slice(0,12)}... &middot; ${t.timestamp?timeAgo(t.timestamp)+'ago':''}</div></div></div><div class="flex"><span class="tag tag-${actionClass(t.recommended_action)}">${actionLabel(t.recommended_action)}</span></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:2px 16px">${[['Virality',t.meme_virality],['Community',t.community_signal],['Metrics',t.token_metrics],['Sentiment',t.sentiment_score]].map(([l,v])=>`<div class="bar-row"><span class="bar-label">${l}</span><div style="flex:1"><div class="bar-wrap"><div class="bar" style="width:${v}%;background:${v>=80?'#22c55e':v>=60?'#f59e0b':'#ef4444'}"></div></div></div><span class="bar-val" style="color:${v>=80?'#22c55e':v>=60?'#f59e0b':'#ef4444'}">${v}</span></div>`).join('')}</div></div>`}).join(''):'<div style="text-align:center;padding:32px;color:#334155">Waiting for token launches...</div>';
}
function renderPositions(p){
const positions=p.positions||[];
document.getElementById('positions-tab').innerHTML=positions.length?positions.map(pos=>{
const pnl=pos.pnl_pct||0;const usd=(pnl*pos.size_usd/100).toFixed(2);
return`<div class="card"><div class="score-header"><div class="flex"><span style="font-size:17px;font-weight:900">$${pos.symbol}</span><span class="tag tag-green">${(pos.side||'long').toUpperCase()} ${pos.leverage}x</span></div><div style="text-align:right"><div style="font-size:22px;font-weight:900;font-family:monospace" class="${pnl>=0?'pnl-pos':'pnl-neg'}">${pnl>=0?'+':''}${pnl.toFixed(1)}%</div><div style="font-size:11px;color:#64748b">${pnl>=0?'+':''}$${usd}</div></div></div></div>`}).join(''):'<div style="text-align:center;padding:32px;color:#334155">No active positions</div>';
}
function renderEvents(events){
const icons={token_scored:'&#128269;',position_opened:'&#128200;',marketing_posted:'&#128227;'};
document.getElementById('events-tab').innerHTML=events.length?'<div class="card" style="padding:0">'+events.map(e=>`<div class="event"><span>${icons[e.event]||'&#128204;'}</span><span class="event-time">${e.timestamp?timeAgo(e.timestamp):''}</span><span class="event-name">${(e.event||'').replace(/_/g,' ')}</span><span class="event-data">${JSON.stringify(e.data||{})}</span></div>`).join('')+'</div>':'<div style="text-align:center;padding:32px;color:#334155">No events yet</div>';
}
async function refresh(){
try{
const r=await fetch(API+'/api/dashboard');
const d=await r.json();
renderStats(d.stats||{});
renderScores(d.scores||[]);
renderPositions(d.positions||{});
renderEvents(d.events||[]);
}catch(e){console.error(e)}
}
refresh();
setInterval(refresh,5000);
</script>
</body>
</html>"""

async def broadcast(data):
    msg = json.dumps(data)
    dead = set()
    for ws in _ws_clients:
        try: await ws.send_str(msg)
        except: dead.add(ws)
    _ws_clients.difference_update(dead)

async def handle_index(req):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")

async def handle_health(req):
    return web.json_response({"status": "ok"})

async def handle_dashboard(req):
    m, p, e = _state["memory"], _state["perp"], _state["events"]
    return web.json_response({"stats": m.get_stats() if m else {}, "scores": m.get_recent_scores(20) if m else [], "positions": p.get_portfolio_summary() if p else {}, "events": e.get_log(50) if e else []})

async def handle_ws(req):
    ws = web.WebSocketResponse()
    await ws.prepare(req)
    _ws_clients.add(ws)
    m, p = _state.get("memory"), _state.get("perp")
    if m and p:
        await ws.send_json({"type": "snapshot", "data": {"stats": m.get_stats(), "scores": m.get_recent_scores(20), "positions": p.get_portfolio_summary()}})
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    if json.loads(msg.data).get("action") == "ping":
                        await ws.send_json({"type": "pong"})
                except Exception as e: logger.warning(f"WS message parse error: {e}")
    finally:
        _ws_clients.discard(ws)
    return ws

@web.middleware
async def cors(req, handler):
    resp = web.Response() if req.method == "OPTIONS" else await handler(req)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

def create_app(memory=None, perp=None, events=None, **kw):
    _state.update({"memory": memory or AgentMemory(), "perp": perp or PerpTrader(), "events": events or EventBus()})
    app = web.Application(middlewares=[cors])
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/dashboard", handle_dashboard)
    app.router.add_get("/ws", handle_ws)
    return app

async def start_server(host="0.0.0.0", port=8420, **kw):
    app = create_app(**kw)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    logger.info(f"Server at http://{host}:{port}")
    return runner
