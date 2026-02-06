"""
LISA FOREX - Display Debug
Run: python test_display.py

Tests why display.html is not updating:
  1. Check if git pull was done (display.html version)
  2. Check server /api/signal response
  3. Check data.json content
  4. Check if display.html has new code or old code
"""

import os
import json
import sys

os.system("")  # Enable ANSI on Windows

G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
B = "\033[94m"
W = "\033[0m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_DIR = os.path.join(BASE_DIR, "update(tuan)")


def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# 1. Check display.html version
sep("1. display.html version check")
display_path = os.path.join(UPDATE_DIR, "display.html")
if os.path.exists(display_path):
    with open(display_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "const SERVER = 'http://localhost:8000'" in content:
        print(f"  {G}NEW version - reads from server API{W}")
    elif "data.json?" in content and "localhost" not in content:
        print(f"  {R}OLD version - reads from local file (will fail in Chrome){W}")
        print(f"  {R}>>> Run: git pull{W}")
    else:
        print(f"  {Y}Unknown version{W}")

    if "Feb 02, 2026" in content:
        print(f"  {R}OLD hardcoded date 'Feb 02, 2026' found{W}")
        print(f"  {R}>>> Run: git pull{W}")
    elif 'id="reportDate">---' in content:
        print(f"  {G}Placeholder '---' OK (no hardcoded date){W}")
    else:
        print(f"  {Y}Could not detect date placeholder{W}")

    if "BUY LIMIT</span>" in content and "4916.5" in content:
        print(f"  {R}OLD hardcoded signals found (BUY LIMIT 4916.5){W}")
    elif "Loading..." in content:
        print(f"  {G}Placeholder 'Loading...' OK (no hardcoded signals){W}")
else:
    print(f"  {R}display.html NOT FOUND at {display_path}{W}")


# 2. Check git status
sep("2. Git status")
try:
    import subprocess
    r = subprocess.run(["git", "log", "--oneline", "-3"], capture_output=True, text=True, cwd=BASE_DIR)
    if r.returncode == 0:
        for line in r.stdout.strip().split("\n"):
            print(f"  {B}{line}{W}")

    r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=BASE_DIR)
    if r.returncode == 0:
        status = r.stdout.strip()
        if status:
            print(f"\n  Modified files:")
            for line in status.split("\n")[:10]:
                print(f"    {line}")
        else:
            print(f"  {G}Clean - no local changes{W}")
except FileNotFoundError:
    print(f"  {R}git not found{W}")


# 3. Check data.json
sep("3. data.json content")
data_path = os.path.join(UPDATE_DIR, "data.json")
if os.path.exists(data_path):
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"  updated_at: {data.get('updated_at', '?')}")
        print(f"  current_price: {data.get('current_price', '?')}")

        sig = data.get("current_signal")
        if sig:
            print(f"  signal: {sig.get('signal')} @ {sig.get('entry')} [{sig.get('status')}]")

        report = data.get("yesterday_report")
        if report:
            print(f"  {G}yesterday_report:{W}")
            print(f"    date: {report.get('date', '?')}")
            print(f"    date_display: {report.get('date_display', '?')}")
            print(f"    TP: {report.get('tp_count', 0)} ({report.get('tp_pips', 0)}p)")
            print(f"    SL: {report.get('sl_count', 0)} ({report.get('sl_pips', 0)}p)")
            print(f"    NET: {report.get('net_pips', 0)}p")
        else:
            print(f"  {R}yesterday_report: null{W}")

        prev = data.get("previous_signals", [])
        print(f"  previous_signals: {len(prev)}")
    except Exception as e:
        print(f"  {R}Error reading data.json: {e}{W}")
else:
    print(f"  {R}data.json NOT FOUND{W}")


# 4. Check server
sep("4. Server /api/signal")
try:
    import httpx
except ImportError:
    print(f"  {R}httpx not installed{W}")
    httpx = None

if httpx:
    try:
        r = httpx.get("http://localhost:8000/api/signal", timeout=5.0)
        if r.status_code == 200:
            api_data = r.json()
            report = api_data.get("yesterday_report")
            if report:
                print(f"  {G}API returns date_display: {report.get('date_display', '?')}{W}")
                print(f"  TP: {report.get('tp_count')} SL: {report.get('sl_count')} NET: {report.get('net_pips')}p")
            else:
                print(f"  {R}API yesterday_report is null{W}")

            sig = api_data.get("current_signal")
            if sig:
                print(f"  Signal: {sig.get('signal')} @ {sig.get('entry')}")
        else:
            print(f"  {R}Status {r.status_code}{W}")
    except httpx.ConnectError:
        print(f"  {R}Cannot connect to localhost:8000 - server not running{W}")
    except Exception as e:
        print(f"  {R}Error: {e}{W}")

    # 5. Check /display route
    sep("5. Server /display route")
    try:
        r = httpx.get("http://localhost:8000/display", timeout=5.0)
        if r.status_code == 200:
            if "const SERVER = 'http://localhost:8000'" in r.text:
                print(f"  {G}/display serves NEW version{W}")
            else:
                print(f"  {R}/display serves OLD version (server needs restart after git pull){W}")
            print(f"  {G}Open: http://localhost:8000/display{W}")
        else:
            print(f"  {R}Status {r.status_code} (server may need git pull + restart){W}")
    except httpx.ConnectError:
        print(f"  {R}Server not running{W}")
    except Exception as e:
        print(f"  {R}Error: {e}{W}")


# Summary
sep("SUMMARY")
print(f"""
  {B}To fix display.html on machine 2:{W}

  1. Open CMD in Lisaforex folder:
     {Y}cd C:\\Users\\KG\\Desktop\\Project\\Lisaforex{W}
     {Y}git pull{W}

  2. Restart server (close bat, reopen):
     {Y}Double-click START_LISA_FOREX.bat{W}

  3. Open display via SERVER (not file://):
     {G}http://localhost:8000/display{W}

  Do NOT open: file:///C:/.../display.html
  (Chrome blocks XHR from file:// protocol)
""")

input("Press Enter to exit...")
