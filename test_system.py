"""
LISA FOREX - System Health Check
Run: python test_system.py

Tests all components:
  1. Python packages
  2. File structure
  3. server.py (API endpoints + WebSocket)
  4. data.json / signal pipeline
  5. Telegram bot config (.env + session)
"""

import sys
import os
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_DIR = os.path.join(BASE_DIR, "update(tuan)")

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
WARN = "\033[93m[WARN]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = {"pass": 0, "fail": 0, "warn": 0}


def ok(msg):
    results["pass"] += 1
    print(f"  {PASS} {msg}")


def fail(msg):
    results["fail"] += 1
    print(f"  {FAIL} {msg}")


def warn(msg):
    results["warn"] += 1
    print(f"  {WARN} {msg}")


def info(msg):
    print(f"  {INFO} {msg}")


def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ──────────────────────────────────────────────
# 1. PYTHON PACKAGES
# ──────────────────────────────────────────────
def test_packages():
    sep("1. Python Packages")
    info(f"Python {sys.version}")

    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "websocket": "websocket-client",
        "httpx": "httpx",
        "numpy": "numpy",
    }
    optional = {
        "telethon": "telethon",
        "dotenv": "python-dotenv",
        "requests": "requests",
    }

    for module, pip_name in required.items():
        try:
            __import__(module)
            ok(f"{pip_name}")
        except ImportError:
            fail(f"{pip_name} missing  -->  pip install {pip_name}")

    for module, pip_name in optional.items():
        try:
            __import__(module)
            ok(f"{pip_name} (for telegram bot)")
        except ImportError:
            warn(f"{pip_name} missing (needed for telegram bot)  -->  pip install {pip_name}")


# ──────────────────────────────────────────────
# 2. FILE STRUCTURE
# ──────────────────────────────────────────────
def test_files():
    sep("2. File Structure")
    info(f"Base: {BASE_DIR}")

    critical_files = [
        ("server.py", BASE_DIR),
        ("chart.html", BASE_DIR),
    ]
    bot_files = [
        ("telegram_html_bot.py", UPDATE_DIR),
        ("display.html", UPDATE_DIR),
        ("START_LISA_FOREX.bat", UPDATE_DIR),
    ]
    config_files = [
        (".env", UPDATE_DIR),
        ("telegram_session.session", UPDATE_DIR),
    ]
    runtime_files = [
        ("data.json", UPDATE_DIR),
        ("signals_state.json", UPDATE_DIR),
    ]

    for name, folder in critical_files:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            size = os.path.getsize(path)
            ok(f"{name} ({size:,} bytes)")
        else:
            fail(f"{name} NOT FOUND at {path}")

    for name, folder in bot_files:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            ok(f"update(tuan)/{name}")
        else:
            fail(f"update(tuan)/{name} NOT FOUND")

    for name, folder in config_files:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            ok(f"update(tuan)/{name}")
        else:
            fail(f"update(tuan)/{name} NOT FOUND  -->  Copy from old machine or create new")

    for name, folder in runtime_files:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))
            ok(f"update(tuan)/{name} (last modified: {mtime})")
        else:
            warn(f"update(tuan)/{name} not found (will be created when telegram bot runs)")


# ──────────────────────────────────────────────
# 3. .ENV CONFIG
# ──────────────────────────────────────────────
def test_env():
    sep("3. Telegram Bot Config (.env)")
    env_path = os.path.join(UPDATE_DIR, ".env")
    if not os.path.exists(env_path):
        fail(f".env not found at {env_path}")
        return

    required_keys = ["API_ID", "API_HASH", "SIGNAL_GROUP_ID", "REPORT_GROUP_ID", "APISED_KEY"]
    env_vars = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()

    for key in required_keys:
        if key in env_vars and env_vars[key]:
            # Mask sensitive values
            val = env_vars[key]
            masked = val[:4] + "..." + val[-4:] if len(val) > 10 else "***"
            ok(f"{key} = {masked}")
        else:
            fail(f"{key} missing or empty in .env")


# ──────────────────────────────────────────────
# 4. data.json SIGNAL DATA
# ──────────────────────────────────────────────
def test_data_json():
    sep("4. Signal Data (data.json)")
    path = os.path.join(UPDATE_DIR, "data.json")
    if not os.path.exists(path):
        warn("data.json not found (telegram bot not running yet)")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"data.json parse error: {e}")
        return

    ok("data.json is valid JSON")

    # Check required fields
    for field in ["updated_at", "current_price", "current_signal"]:
        if field in data:
            ok(f"Field '{field}' present")
        else:
            fail(f"Field '{field}' missing")

    # Check freshness
    if "updated_at" in data:
        info(f"Last update: {data['updated_at']} (GMT+7)")
        try:
            from datetime import datetime
            updated = datetime.strptime(data["updated_at"], "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            age_sec = (now - updated).total_seconds()
            # Adjust for GMT+7 (data is in GMT+7, local time may differ)
            if age_sec < 300:
                ok(f"Data is fresh ({int(age_sec)}s old)")
            elif age_sec < 3600:
                warn(f"Data is {int(age_sec/60)} minutes old (bot may have stopped)")
            else:
                warn(f"Data is {int(age_sec/3600)} hours old (bot likely not running)")
        except Exception:
            pass

    if "current_price" in data:
        info(f"Current price: {data['current_price']}")

    # Check current signal
    sig = data.get("current_signal")
    if sig:
        for field in ["signal", "entry", "tp1", "tp2", "tp3", "sl", "status"]:
            if field in sig:
                ok(f"Signal.{field} = {sig[field]}")
            else:
                fail(f"Signal.{field} missing")

    # Check previous signals
    prev = data.get("previous_signals", [])
    info(f"Previous signals: {len(prev)}")

    # Check yesterday report
    report = data.get("yesterday_report")
    if report:
        ok(f"Yesterday report: {report.get('date_display', report.get('date', '?'))} "
           f"(TP:{report.get('tp_count',0)} SL:{report.get('sl_count',0)} Net:{report.get('net_pips',0)}p)")


# ──────────────────────────────────────────────
# 5. SERVER.PY (API + WebSocket)
# ──────────────────────────────────────────────
def test_server():
    sep("5. Server (localhost:8000)")

    # Check if port 8000 is open
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    port_open = sock.connect_ex(("127.0.0.1", 8000)) == 0
    sock.close()

    if not port_open:
        fail("Port 8000 not open  -->  Start server: python -X utf8 server.py")
        return

    ok("Port 8000 is open")

    try:
        import httpx
    except ImportError:
        fail("httpx not installed, cannot test API endpoints")
        return

    # Test endpoints
    client = httpx.Client(timeout=10.0)

    # GET /
    try:
        r = client.get("http://localhost:8000/")
        if r.status_code == 200 and "chart" in r.text.lower():
            ok(f"GET / -> chart.html ({len(r.text):,} bytes)")
        else:
            fail(f"GET / -> status {r.status_code}")
    except Exception as e:
        fail(f"GET / -> {e}")

    # GET /api/health
    try:
        r = client.get("http://localhost:8000/api/health")
        if r.status_code == 200:
            h = r.json()
            ok(f"GET /api/health -> ticks:{h.get('ticks',0)} clients:{h.get('clients',0)} price:{h.get('price','?')}")
        else:
            fail(f"GET /api/health -> status {r.status_code}")
    except Exception as e:
        fail(f"GET /api/health -> {e}")

    # GET /api/price
    try:
        r = client.get("http://localhost:8000/api/price")
        if r.status_code == 200:
            p = r.json()
            ok(f"GET /api/price -> {p.get('price','?')}")
        elif r.status_code == 503:
            warn("GET /api/price -> 503 (no tick data yet, server just started)")
        else:
            fail(f"GET /api/price -> status {r.status_code}")
    except Exception as e:
        fail(f"GET /api/price -> {e}")

    # GET /api/signal
    try:
        r = client.get("http://localhost:8000/api/signal")
        if r.status_code == 200:
            sig = r.json()
            if "current_signal" in sig:
                cs = sig["current_signal"]
                ok(f"GET /api/signal -> {cs.get('signal','')} entry:{cs.get('entry','')} status:{cs.get('status','')}")
            elif "error" in sig:
                warn(f"GET /api/signal -> {sig['error']}")
            else:
                ok(f"GET /api/signal -> OK (no current signal)")
        elif r.status_code == 404:
            warn("GET /api/signal -> 404 (data.json not found, telegram bot not running)")
        else:
            fail(f"GET /api/signal -> status {r.status_code}")
    except Exception as e:
        fail(f"GET /api/signal -> {e}")

    # GET /api/history (quick test with minimal bars)
    try:
        info("Testing /api/history (fetching 10 candles, may take ~5s)...")
        r = client.get("http://localhost:8000/api/history?interval=1&bars=10", timeout=30.0)
        if r.status_code == 200:
            h = r.json()
            count = h.get("count", 0)
            source = h.get("source", "?")
            has_indicator = h.get("indicator") is not None
            ok(f"GET /api/history -> {count} candles, source:{source}, indicator:{'yes' if has_indicator else 'no'}")
        else:
            fail(f"GET /api/history -> status {r.status_code}: {r.text[:200]}")
    except httpx.TimeoutException:
        warn("GET /api/history -> timeout (TradingView may be slow, try again)")
    except Exception as e:
        fail(f"GET /api/history -> {e}")

    # Test WebSocket
    try:
        import websocket as ws_lib
        info("Testing WebSocket /ws/price (waiting 3s for tick)...")
        got_tick = [False]
        tick_data = [None]

        def on_msg(ws, msg):
            try:
                d = json.loads(msg)
                if d.get("type") == "tick":
                    got_tick[0] = True
                    tick_data[0] = d
                    ws.close()
            except:
                pass

        def on_err(ws, err):
            pass

        ws_app = ws_lib.WebSocketApp(
            "ws://localhost:8000/ws/price",
            on_message=on_msg,
            on_error=on_err,
        )

        import threading
        t = threading.Thread(target=ws_app.run_forever, daemon=True)
        t.start()
        t.join(timeout=5)
        if t.is_alive():
            ws_app.close()

        if got_tick[0]:
            td = tick_data[0]
            ok(f"WebSocket tick received -> price:{td.get('price','')} latency:{td.get('latency','')}ms")
        else:
            warn("WebSocket: no tick received in 5s (APISed may be slow)")

    except Exception as e:
        fail(f"WebSocket test -> {e}")

    client.close()


# ──────────────────────────────────────────────
# 6. GIT STATUS
# ──────────────────────────────────────────────
def test_git():
    sep("6. Git Repository")
    git_dir = os.path.join(BASE_DIR, ".git")
    if os.path.isdir(git_dir):
        ok("Git repository found")
        try:
            import subprocess
            r = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, cwd=BASE_DIR)
            if r.returncode == 0 and r.stdout.strip():
                lines = r.stdout.strip().split("\n")
                info(f"Remote: {lines[0]}")
            else:
                warn("No git remote configured")

            r = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=BASE_DIR)
            if r.returncode == 0:
                info(f"Branch: {r.stdout.strip()}")
        except FileNotFoundError:
            warn("git command not found (install Git to use auto-update)")
    else:
        fail(f"Not a git repository (no .git in {BASE_DIR})")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # Enable color output on Windows
        os.system("")

        print()
        print("=" * 60)
        print("   LISA FOREX - System Health Check")
        print("=" * 60)

        test_packages()
        test_files()
        test_env()
        test_data_json()
        test_server()
        test_git()

        # Summary
        sep("SUMMARY")
        total = results["pass"] + results["fail"] + results["warn"]
        print(f"  {PASS} {results['pass']} passed")
        print(f"  {FAIL} {results['fail']} failed")
        print(f"  {WARN} {results['warn']} warnings")
        print()

        if results["fail"] == 0:
            print(f"  \033[92m*** All critical checks passed! ***\033[0m")
        else:
            print(f"  \033[91m*** {results['fail']} issue(s) need fixing ***\033[0m")
        print()

    except Exception as e:
        print(f"\n\033[91m[CRASH] {e}\033[0m")
        import traceback
        traceback.print_exc()

    # Keep window open when double-clicked on Windows
    input("Press Enter to exit...")
