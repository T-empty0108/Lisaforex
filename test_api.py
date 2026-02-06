"""
LISA FOREX - APISed & WebSocket Debug
Run: python test_api.py

Tests:
  1. APISed API direct call (bypass server)
  2. Server /api/price endpoint
  3. Server /api/health endpoint
  4. WebSocket connection to server
"""

import json
import time
import sys
import os
import threading

os.system("")  # Enable ANSI colors on Windows

APISED_KEY = "sk_c27869e90912e2A4f32E104A77Ad9dFC02bb47B5e489f4cE"
APISED_URL = "https://gold.g.apised.com/v1/latest?metals=XAU&base_currency=USD&currencies=USD&weight_unit=TOZ"
SERVER = "http://localhost:8000"

G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
W = "\033[0m"   # reset


def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ──────────────────────────────────────────────
# 1. APISed Direct Test
# ──────────────────────────────────────────────
def test_apised_direct():
    sep("1. APISed API - Direct Call")
    try:
        import httpx
    except ImportError:
        print(f"  {R}httpx not installed{W}")
        return

    print(f"  {B}URL:{W} {APISED_URL}")
    print(f"  {B}Key:{W} {APISED_KEY[:8]}...{APISED_KEY[-4:]}")
    print()

    client = httpx.Client(timeout=10.0)

    for i in range(3):
        try:
            t1 = time.time()
            resp = client.get(APISED_URL, headers={"x-api-key": APISED_KEY})
            latency = round((time.time() - t1) * 1000)

            print(f"  Call {i+1}/3: status={resp.status_code} latency={latency}ms")

            if resp.status_code == 200:
                data = resp.json()
                print(f"    status: {data.get('status')}")

                if data.get("status") == "success":
                    price = data["data"]["metal_prices"]["XAU"]["price"]
                    ts = data["data"].get("timestamp", "?")
                    print(f"    {G}price: {price}{W}")
                    print(f"    timestamp: {ts}")
                else:
                    print(f"    {R}API returned non-success status{W}")
                    print(f"    response: {json.dumps(data, indent=2)[:500]}")
            elif resp.status_code == 401:
                print(f"    {R}401 Unauthorized - API key invalid or expired{W}")
            elif resp.status_code == 429:
                print(f"    {Y}429 Rate Limited - too many requests{W}")
            else:
                print(f"    {R}Unexpected status: {resp.status_code}{W}")
                print(f"    body: {resp.text[:300]}")

        except httpx.ConnectError as e:
            print(f"  Call {i+1}/3: {R}Connection error - {e}{W}")
        except httpx.TimeoutException:
            print(f"  Call {i+1}/3: {R}Timeout (>10s){W}")
        except Exception as e:
            print(f"  Call {i+1}/3: {R}Error - {e}{W}")

        if i < 2:
            time.sleep(1.5)

    client.close()


# ──────────────────────────────────────────────
# 2. Server /api/health
# ──────────────────────────────────────────────
def test_server_health():
    sep("2. Server /api/health")
    try:
        import httpx
    except ImportError:
        return

    try:
        r = httpx.get(f"{SERVER}/api/health", timeout=5.0)
        if r.status_code == 200:
            h = r.json()
            print(f"  {G}Server is running{W}")
            print(f"  ticks:   {h.get('ticks', 0)}")
            print(f"  clients: {h.get('clients', 0)}")
            print(f"  price:   {h.get('price', 'None')}")

            if h.get('ticks', 0) == 0:
                print(f"\n  {Y}WARNING: ticks=0 means APISed poller hasn't received any data{W}")
                print(f"  {Y}This is likely the cause of 'Connecting...' on the chart{W}")
            if h.get('price') is None:
                print(f"\n  {R}No price data - APISed is not returning data{W}")
        else:
            print(f"  {R}Status {r.status_code}{W}")
    except httpx.ConnectError:
        print(f"  {R}Cannot connect to {SERVER} - server not running{W}")
    except Exception as e:
        print(f"  {R}Error: {e}{W}")


# ──────────────────────────────────────────────
# 3. Server /api/price
# ──────────────────────────────────────────────
def test_server_price():
    sep("3. Server /api/price")
    try:
        import httpx
    except ImportError:
        return

    try:
        r = httpx.get(f"{SERVER}/api/price", timeout=5.0)
        data = r.json()
        if r.status_code == 200:
            print(f"  {G}Price: {data.get('price')}{W}")
            print(f"  Ticks: {data.get('ticks')}")
        elif r.status_code == 503:
            print(f"  {R}503 - No data yet{W}")
            print(f"  {Y}Server started but APISed hasn't returned any price{W}")
        else:
            print(f"  {R}Status {r.status_code}: {data}{W}")
    except httpx.ConnectError:
        print(f"  {R}Cannot connect to {SERVER}{W}")
    except Exception as e:
        print(f"  {R}Error: {e}{W}")


# ──────────────────────────────────────────────
# 4. WebSocket Test
# ──────────────────────────────────────────────
def test_websocket():
    sep("4. WebSocket ws://localhost:8000/ws/price")
    try:
        import websocket as ws_lib
    except ImportError:
        print(f"  {R}websocket-client not installed{W}")
        return

    print(f"  Connecting and waiting up to 10s for ticks...")

    ticks = []
    errors = []
    connected = [False]

    def on_open(ws):
        connected[0] = True
        print(f"  {G}WebSocket connected{W}")

    def on_msg(ws, msg):
        try:
            d = json.loads(msg)
            if d.get("type") == "tick":
                ticks.append(d)
                price = d.get("price", "?")
                lat = d.get("latency", "?")
                tick = d.get("tick", "?")
                print(f"  {G}Tick #{tick}: price={price} latency={lat}ms{W}")
                if len(ticks) >= 5:
                    ws.close()
            elif d.get("type") == "pong":
                pass
            else:
                print(f"  {B}Received: {msg[:200]}{W}")
        except:
            print(f"  {Y}Non-JSON: {msg[:100]}{W}")

    def on_err(ws, err):
        errors.append(str(err))

    def on_close(ws, code, reason):
        pass

    ws_app = ws_lib.WebSocketApp(
        "ws://localhost:8000/ws/price",
        on_open=on_open,
        on_message=on_msg,
        on_error=on_err,
        on_close=on_close,
    )

    t = threading.Thread(target=ws_app.run_forever, daemon=True)
    t.start()
    t.join(timeout=10)
    if t.is_alive():
        ws_app.close()

    print()
    if not connected[0]:
        print(f"  {R}Could not connect to WebSocket{W}")
        print(f"  {R}Server may not be running on port 8000{W}")
    elif len(ticks) == 0:
        print(f"  {R}Connected but received 0 ticks in 10s{W}")
        print(f"  {R}APISed is not returning price data to the server{W}")
        print(f"  {Y}This is why the chart shows 'Connecting...'{W}")
    else:
        print(f"  {G}Received {len(ticks)} ticks OK{W}")

    if errors:
        print(f"  Errors: {errors}")


# ──────────────────────────────────────────────
# 5. Server console log check
# ──────────────────────────────────────────────
def test_diagnosis():
    sep("5. Diagnosis")

    # Check if both machines might be using the same API key
    print(f"  {B}Common causes of 'Connecting...':{W}")
    print(f"  1. APISed API key expired or rate-limited")
    print(f"  2. APISed returning errors (check server CMD window for warnings)")
    print(f"  3. Network/firewall blocking HTTPS to gold.g.apised.com")
    print(f"  4. Two machines using same API key simultaneously (rate limit)")
    print()
    print(f"  {Y}Check the CMD window where START_LISA_FOREX.bat is running.{W}")
    print(f"  {Y}Look for lines like:{W}")
    print(f"    [APISed] ▶ Poller started (1s)")
    print(f"    [APISed] ⚠ <error message>")
    print()
    print(f"  If you see repeated ⚠ warnings, APISed is failing.")
    print(f"  The chart shows 'Connecting...' until the first WebSocket tick arrives.")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("=" * 60)
    print("   LISA FOREX - APISed & WebSocket Debug")
    print("=" * 60)

    test_apised_direct()
    test_server_health()
    test_server_price()
    test_websocket()
    test_diagnosis()

    print()
    input("Press Enter to exit...")
