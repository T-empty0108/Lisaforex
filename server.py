"""
╔══════════════════════════════════════════════════════════════════╗
║  XAU/USD Proxy Server v2                                         ║
║  TradingView OANDA (lịch sử) + APISed (realtime 1s)             ║
║  + Volumatic VIDYA Indicator [BigBeluga]                         ║
║                                                                  ║
║  Cài đặt:                                                        ║
║    pip install fastapi uvicorn websocket-client httpx numpy       ║
║                                                                  ║
║  Chạy:                                                           ║
║    python server.py                                              ║
║    → http://localhost:8000                                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import random
import string
import re
import time
import threading
import asyncio
from contextlib import asynccontextmanager

import numpy as np
import httpx
import websocket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import os

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

APISED_KEY = "sk_c27869e90912e2A4f32E104A77Ad9dFC02bb47B5e489f4cE"
APISED_URL = "https://gold.g.apised.com/v1/latest?metals=XAU&base_currency=USD&currencies=USD&weight_unit=TOZ"
APISED_INTERVAL = 1.0

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_HEADERS = {
    "Origin": "https://data.tradingview.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
TV_SYMBOL = "OANDA:XAUUSD"

TF_MAP = {
    "1":  {"tv_interval": "1",  "default_bars": 1500},
    "5":  {"tv_interval": "5",  "default_bars": 500},
    "15": {"tv_interval": "15", "default_bars": 300},
    "60": {"tv_interval": "60", "default_bars": 200},
}

# VIDYA Parameters (matching Pine Script defaults)
VIDYA_LENGTH = 10
VIDYA_MOMENTUM = 20
BAND_DISTANCE = 2.0
PIVOT_BARS = 3
ATR_LENGTH = 200

PORT = 8000


# ═══════════════════════════════════════════════════════════════
# TRADINGVIEW WEBSOCKET PROTOCOL
# ═══════════════════════════════════════════════════════════════

def _rand_id(prefix, length=12):
    return prefix + "".join(random.choice(string.ascii_lowercase) for _ in range(length))

def _pack(msg):
    return f"~m~{len(msg)}~m~{msg}"

def _tv_send(ws, method, params):
    ws.send(_pack(json.dumps({"m": method, "p": params}, separators=(",", ":"))))

def _parse_packets(raw):
    results = []
    pattern = re.compile(r"~m~(\d+)~m~")
    pos = 0
    while pos < len(raw):
        m = pattern.match(raw, pos)
        if not m:
            break
        length = int(m.group(1))
        start = m.end()
        results.append(raw[start:start + length])
        pos = start + length
    return results

def _extract_candles(params):
    candles = []
    for p in params:
        if not isinstance(p, dict):
            continue
        for key, val in p.items():
            bars = None
            if isinstance(val, dict) and "s" in val:
                bars = val["s"]
            elif isinstance(val, list):
                bars = val
            if bars:
                for bar in bars:
                    if isinstance(bar, dict) and "v" in bar:
                        v = bar["v"]
                        if len(v) >= 5:
                            candles.append({
                                "time": int(v[0]),
                                "open": round(v[1], 3),
                                "high": round(v[2], 3),
                                "low": round(v[3], 3),
                                "close": round(v[4], 3),
                                "volume": round(v[5], 2) if len(v) > 5 else 0,
                            })
    return candles

def fetch_tv_history(symbol=TV_SYMBOL, interval="1", n_bars=1500, timeout=30):
    chart = _rand_id("cs_")
    candles = []
    error = [None]
    ready = threading.Event()

    def on_message(ws, message):
        for packet in _parse_packets(message):
            if packet.startswith("~h~"):
                ws.send(_pack(packet))
                continue
            try:
                data = json.loads(packet)
            except:
                continue
            if not isinstance(data, dict) or "m" not in data:
                continue
            m = data["m"]
            p = data.get("p", [])
            if m in ("timescale_update", "du"):
                candles.extend(_extract_candles(p))
            elif m == "series_completed":
                ready.set()
            elif m in ("protocol_error", "critical_error"):
                error[0] = str(p)
                ready.set()

    def on_open(ws):
        _tv_send(ws, "set_auth_token", ["unauthorized_user_token"])
        _tv_send(ws, "chart_create_session", [chart, ""])
        _tv_send(ws, "switch_timezone", [chart, "Etc/UTC"])
        _tv_send(ws, "resolve_symbol", [
            chart, "sds_sym_1",
            f'={{"symbol":"{symbol}","adjustment":"splits","session":"regular"}}'
        ])
        _tv_send(ws, "create_series", [
            chart, "sds_1", "s1", "sds_sym_1", interval, n_bars, ""
        ])

    def on_error(ws, err):
        error[0] = str(err)
        ready.set()

    ws_app = websocket.WebSocketApp(
        TV_WS_URL,
        header=[f"{k}: {v}" for k, v in TV_HEADERS.items()],
        on_open=on_open, on_message=on_message, on_error=on_error,
    )
    t = threading.Thread(target=ws_app.run_forever, daemon=True)
    t.start()
    ready.wait(timeout=timeout)
    ws_app.close()

    if error[0]:
        print(f"[TV] ❌ {error[0]}")
        return None

    seen = set()
    unique = []
    for c in candles:
        if c["time"] not in seen:
            seen.add(c["time"])
            unique.append(c)
    unique.sort(key=lambda x: x["time"])
    return unique


# ═══════════════════════════════════════════════════════════════
# VIDYA INDICATOR — Port of Pine Script BigBeluga
# ═══════════════════════════════════════════════════════════════

def compute_vidya(candles):
    """Compute full Volumatic VIDYA indicator from candle data."""
    n = len(candles)
    if n < ATR_LENGTH + 20:
        return None

    op = np.array([c["open"]  for c in candles], dtype=np.float64)
    hi = np.array([c["high"]  for c in candles], dtype=np.float64)
    lo = np.array([c["low"]   for c in candles], dtype=np.float64)
    cl = np.array([c["close"] for c in candles], dtype=np.float64)
    vo = np.array([c.get("volume", 0) for c in candles], dtype=np.float64)
    ts = [c["time"] for c in candles]
    src = cl

    # ── ATR(200) via RMA ──
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - np.roll(cl, 1)), np.abs(lo - np.roll(cl, 1))))
    tr[0] = hi[0] - lo[0]
    atr = np.full(n, np.nan)
    if n >= ATR_LENGTH:
        atr[ATR_LENGTH - 1] = np.mean(tr[:ATR_LENGTH])
        for i in range(ATR_LENGTH, n):
            atr[i] = (atr[i-1] * (ATR_LENGTH - 1) + tr[i]) / ATR_LENGTH

    # ── VIDYA: CMO → alpha → recursive EMA → SMA(15) ──
    mom = np.zeros(n)
    mom[1:] = src[1:] - src[:-1]
    pos_m = np.where(mom >= 0, mom, 0.0)
    neg_m = np.where(mom < 0, -mom, 0.0)

    sum_pos = np.full(n, 0.0)
    sum_neg = np.full(n, 0.0)
    for i in range(VIDYA_MOMENTUM - 1, n):
        sum_pos[i] = np.sum(pos_m[i - VIDYA_MOMENTUM + 1:i + 1])
        sum_neg[i] = np.sum(neg_m[i - VIDYA_MOMENTUM + 1:i + 1])

    abs_cmo = np.zeros(n)
    denom = sum_pos + sum_neg
    valid = denom > 0
    abs_cmo[valid] = np.abs(100.0 * (sum_pos[valid] - sum_neg[valid]) / denom[valid])

    alpha = 2.0 / (VIDYA_LENGTH + 1)
    vidya_raw = np.zeros(n)
    for i in range(1, n):
        sc = alpha * abs_cmo[i] / 100.0
        vidya_raw[i] = sc * src[i] + (1.0 - sc) * vidya_raw[i-1]

    sma_len = 15
    vidya = np.full(n, np.nan)
    for i in range(sma_len - 1, n):
        vidya[i] = np.mean(vidya_raw[i - sma_len + 1:i + 1])

    # ── Bands ──
    upper = np.where(~np.isnan(vidya) & ~np.isnan(atr), vidya + atr * BAND_DISTANCE, np.nan)
    lower = np.where(~np.isnan(vidya) & ~np.isnan(atr), vidya - atr * BAND_DISTANCE, np.nan)

    # ── Trend detection ──
    trend_up = np.zeros(n, dtype=bool)
    for i in range(1, n):
        trend_up[i] = trend_up[i-1]
        if np.isnan(upper[i]) or np.isnan(upper[i-1]) or np.isnan(lower[i]) or np.isnan(lower[i-1]):
            continue
        if src[i] > upper[i] and src[i-1] <= upper[i-1]:
            trend_up[i] = True
        if src[i] < lower[i] and src[i-1] >= lower[i-1]:
            trend_up[i] = False

    # ── Smoothed line ──
    smoothed = np.full(n, np.nan)
    for i in range(1, n):
        smoothed[i] = lower[i] if trend_up[i] else upper[i]
        if trend_up[i] != trend_up[i-1]:
            smoothed[i] = np.nan  # Break on trend change

    # ── Signals ▲▼ ──
    signals = []
    for i in range(2, n):
        cross_up  = not trend_up[i-1] and trend_up[i]
        cross_dn  = trend_up[i-1] and not trend_up[i]
        if cross_up and not np.isnan(smoothed[i]):
            signals.append({"time": ts[i], "type": "up", "price": round(float(smoothed[i]), 3)})
        if cross_dn and not np.isnan(smoothed[i]):
            signals.append({"time": ts[i], "type": "down", "price": round(float(smoothed[i]), 3)})

    # ── Pivot liquidity lines ──
    pL = PIVOT_BARS
    pR = PIVOT_BARS
    liq_lines = []
    for i in range(pL + pR, n):
        idx = i - pR
        if idx < pL or idx >= n:
            continue

        # Pivot low
        is_plow = True
        for j in range(idx - pL, idx):
            if lo[j] <= lo[idx]:
                is_plow = False; break
        if is_plow:
            for j in range(idx + 1, min(idx + pR + 1, n)):
                if lo[j] <= lo[idx]:
                    is_plow = False; break

        # Pivot high
        is_phi = True
        for j in range(idx - pL, idx):
            if hi[j] >= hi[idx]:
                is_phi = False; break
        if is_phi:
            for j in range(idx + 1, min(idx + pR + 1, n)):
                if hi[j] >= hi[idx]:
                    is_phi = False; break

        sm_val = smoothed[i]
        if np.isnan(sm_val):
            continue

        if is_plow and lo[idx] > sm_val:
            liq_lines.append({"time": ts[idx], "price": round(float(lo[idx]), 3), "type": "support"})
        if is_phi and hi[idx] < sm_val:
            liq_lines.append({"time": ts[idx], "price": round(float(hi[idx]), 3), "type": "resistance"})

    # ── Volume delta per trend segment ──
    vol_delta = []
    buy_v = sell_v = 0.0
    for i in range(1, n):
        if trend_up[i] != trend_up[i-1]:
            avg_vd = (buy_v + sell_v) / 2 if (buy_v + sell_v) > 0 else 1
            vol_delta.append({
                "time": ts[i],
                "buy": round(buy_v), "sell": round(sell_v),
                "delta_pct": round((buy_v - sell_v) / avg_vd * 100, 1),
                "trend": "up" if trend_up[i] else "down",
            })
            buy_v = sell_v = 0.0
        else:
            if cl[i] > op[i]: buy_v += vo[i]
            elif cl[i] < op[i]: sell_v += vo[i]

    # ── Build output ──
    start = ATR_LENGTH + sma_len
    vidya_line = []
    for i in range(start, n):
        if not np.isnan(smoothed[i]):
            vidya_line.append({
                "time": ts[i],
                "value": round(float(smoothed[i]), 3),
                "trend": "up" if trend_up[i] else "down",
            })

    valid_set = set(ts[start:])
    return {
        "vidya_line": vidya_line,
        "signals": [s for s in signals if s["time"] in valid_set],
        "liquidity": liq_lines[-80:],
        "vol_delta": vol_delta[-20:],
    }


# ═══════════════════════════════════════════════════════════════
# APISED POLLER + CACHE + FASTAPI
# ═══════════════════════════════════════════════════════════════

class RealtimePoller:
    def __init__(self):
        self.clients: list[WebSocket] = []
        self.latest_price = None
        self.latest_time = None
        self.tick_count = 0
        self.running = False
        self._task = None

    async def start(self):
        if self.running: return
        self.running = True
        self._task = asyncio.create_task(self._poll_loop())
        print(f"[APISed] ▶ Poller started ({APISED_INTERVAL}s)")

    async def stop(self):
        self.running = False
        if self._task: self._task.cancel()

    async def _poll_loop(self):
        async with httpx.AsyncClient(timeout=5.0) as client:
            while self.running:
                try:
                    t1 = time.time()
                    resp = await client.get(APISED_URL, headers={"x-api-key": APISED_KEY})
                    data = resp.json()
                    latency = round((time.time() - t1) * 1000)
                    if data.get("status") != "success":
                        await asyncio.sleep(APISED_INTERVAL); continue
                    price = float(data["data"]["metal_prices"]["XAU"]["price"])
                    if price <= 0:
                        await asyncio.sleep(APISED_INTERVAL); continue

                    self.latest_price = price
                    self.latest_time = time.time()
                    self.tick_count += 1

                    msg = json.dumps({"type":"tick","price":price,"timestamp":int(time.time()),"latency":latency,"tick":self.tick_count})
                    dead = []
                    for ws in self.clients:
                        try: await ws.send_text(msg)
                        except: dead.append(ws)
                    for ws in dead: self.clients.remove(ws)

                except asyncio.CancelledError: break
                except Exception as e: print(f"[APISed] ⚠ {e}")
                await asyncio.sleep(APISED_INTERVAL)

    def add_client(self, ws): self.clients.append(ws); print(f"[WS] + ({len(self.clients)})")
    def remove_client(self, ws):
        if ws in self.clients: self.clients.remove(ws)
        print(f"[WS] - ({len(self.clients)})")


class Cache:
    def __init__(self, ttl=55):
        self.ttl = ttl; self.data = {}
    def get(self, k):
        e = self.data.get(k)
        return e["v"] if e and (time.time() - e["t"]) < self.ttl else None
    def set(self, k, v):
        self.data[k] = {"v": v, "t": time.time()}


poller = RealtimePoller()
cache = Cache(ttl=55)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await poller.start()
    print(f"[Server] ✅ http://localhost:{PORT}")
    yield
    await poller.stop()

app = FastAPI(title="XAU/USD + VIDYA", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/history")
async def get_history(interval: str = "1", bars: int = 1500):
    if interval not in TF_MAP:
        return JSONResponse({"error": f"Use: {list(TF_MAP.keys())}"}, 400)
    bars = min(bars, 5000)
    ck = f"h_{interval}_{bars}"
    cached = cache.get(ck)
    if cached:
        return {**cached, "source": "cache"}

    candles = await asyncio.to_thread(fetch_tv_history, TV_SYMBOL, TF_MAP[interval]["tv_interval"], bars)
    if candles is None:
        return JSONResponse({"error": "TradingView fetch failed"}, 502)

    indicator = compute_vidya(candles)
    candles_out = [{"time":c["time"],"open":c["open"],"high":c["high"],"low":c["low"],"close":c["close"]} for c in candles]
    result = {"source":"tradingview","symbol":TV_SYMBOL,"interval":interval,"count":len(candles_out),"candles":candles_out,"indicator":indicator}
    cache.set(ck, result)
    return result


@app.get("/api/price")
async def get_price():
    if poller.latest_price:
        return {"price":poller.latest_price,"timestamp":int(poller.latest_time),"ticks":poller.tick_count}
    return JSONResponse({"error":"No data"}, 503)


@app.websocket("/ws/price")
async def ws_price(ws: WebSocket):
    await ws.accept()
    poller.add_client(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping": await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect: pass
    finally: poller.remove_client(ws)


@app.get("/api/health")
async def health():
    return {"status":"ok","ticks":poller.tick_count,"clients":len(poller.clients),"price":poller.latest_price}


@app.get("/")
async def serve_chart():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>chart.html not found</h1>")


if __name__ == "__main__":
    import uvicorn
    print("""
╔══════════════════════════════════════════════════════════════╗
║  XAU/USD Proxy v2 + Volumatic VIDYA [BigBeluga]             ║
║  History:   TradingView OANDA                                ║
║  Realtime:  APISed 1s                                        ║
║  Indicator: VIDYA + Trend + Signals + Liquidity              ║
║                                                              ║
║  GET  /api/history?interval=1&bars=1500                      ║
║  GET  /api/price                                             ║
║  WS   /ws/price                                              ║
║  GET  /  (chart)                                             ║
╚══════════════════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")