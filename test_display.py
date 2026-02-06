"""
LISA FOREX - Display Debug Tool
================================
Run:  python test_display.py

Kiem tra tai sao display.html hien thi sai data
"""

import os, json, sys

os.system("")
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; W = "\033[0m"
BASE = os.path.dirname(os.path.abspath(__file__))
UPDATE = os.path.join(BASE, "update(tuan)")

try:
    print(f"\n{'='*60}")
    print(f"  LISA FOREX - Display Debug")
    print(f"  Base: {BASE}")
    print(f"{'='*60}")

    # ===== 1. GIT PULL STATUS =====
    print(f"\n{B}[1] Git status{W}")
    import subprocess
    r = subprocess.run(["git", "log", "--oneline", "-5"], capture_output=True, text=True, cwd=BASE)
    if r.returncode == 0:
        for line in r.stdout.strip().split("\n"):
            has_fix = "display" in line.lower() or "fix" in line.lower()
            color = G if has_fix else W
            print(f"  {color}{line}{W}")

    # ===== 2. DISPLAY.HTML VERSION =====
    print(f"\n{B}[2] display.html version{W}")
    dp = os.path.join(UPDATE, "display.html")
    if os.path.exists(dp):
        with open(dp, "r", encoding="utf-8") as f:
            html = f.read()

        checks = [
            ("localhost:8000" in html, "Reads from SERVER API", "Reads from LOCAL file (OLD!)"),
            ("Feb 02, 2026" not in html, "No hardcoded date", "Has OLD hardcoded 'Feb 02, 2026'"),
            ("4916.5" not in html, "No hardcoded signals", "Has OLD hardcoded signals"),
            ("Loading..." in html, "Has Loading placeholder", "Missing Loading placeholder"),
        ]
        for ok, good, bad in checks:
            if ok:
                print(f"  {G}PASS{W} {good}")
            else:
                print(f"  {R}FAIL{W} {bad} --> Run: git pull")
    else:
        print(f"  {R}NOT FOUND: {dp}{W}")

    # ===== 3. DATA.JSON =====
    print(f"\n{B}[3] data.json{W}")
    djp = os.path.join(UPDATE, "data.json")
    if os.path.exists(djp):
        with open(djp, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"  updated_at:    {data.get('updated_at', '?')}")
        print(f"  current_price: {data.get('current_price', '?')}")

        sig = data.get("current_signal")
        if sig:
            print(f"  current_signal: {G}{sig.get('signal')} @ {sig.get('entry')} [{sig.get('status')}]{W}")
        else:
            print(f"  current_signal: {R}null{W}")

        report = data.get("yesterday_report")
        if report:
            print(f"  yesterday_report:")
            print(f"    date_display: {G}{report.get('date_display', '?')}{W}")
            print(f"    TP: {report.get('tp_count', 0)} ({report.get('tp_pips', 0)}p)")
            print(f"    SL: {report.get('sl_count', 0)} ({report.get('sl_pips', 0)}p)")
            print(f"    NET: {report.get('net_pips', 0)}p")
        else:
            print(f"  yesterday_report: {R}null{W}")

        prev = data.get("previous_signals", [])
        print(f"  previous_signals: {len(prev)}")
        for i, p in enumerate(prev):
            print(f"    [{i}] {p.get('signal')} @ {p.get('entry')} [{p.get('status')}] {p.get('profit_formatted')}")
    else:
        print(f"  {R}NOT FOUND{W}")

    # ===== 4. SERVER API =====
    print(f"\n{B}[4] Server http://localhost:8000{W}")
    try:
        import httpx
    except:
        try:
            import requests as httpx
        except:
            httpx = None

    if httpx:
        # /api/signal
        try:
            r = httpx.get("http://localhost:8000/api/signal", timeout=5)
            if hasattr(r, 'status_code'):
                status = r.status_code
            else:
                status = r.status

            if status == 200:
                api = r.json()
                sig = api.get("current_signal")
                report = api.get("yesterday_report")
                print(f"  {G}/api/signal OK{W}")
                if sig:
                    print(f"    signal: {sig.get('signal')} @ {sig.get('entry')} [{sig.get('status')}]")
                if report:
                    print(f"    report: {report.get('date_display')} NET={report.get('net_pips')}p")
            else:
                print(f"  {R}/api/signal -> {status}{W}")
        except Exception as e:
            print(f"  {R}/api/signal FAIL: {e}{W}")

        # /display
        try:
            r = httpx.get("http://localhost:8000/display", timeout=5)
            if hasattr(r, 'status_code'):
                status = r.status_code
            else:
                status = r.status

            if status == 200:
                txt = r.text if hasattr(r, 'text') else r.content.decode()
                if "localhost:8000" in txt:
                    print(f"  {G}/display OK (new version){W}")
                else:
                    print(f"  {R}/display serves OLD version -> restart server after git pull{W}")
            else:
                print(f"  {R}/display -> {status} (need git pull + restart server){W}")
        except Exception as e:
            print(f"  {R}/display FAIL: {e}{W}")
    else:
        print(f"  {R}httpx/requests not installed, skip API test{W}")

    # ===== 5. PORT CHECK =====
    print(f"\n{B}[5] Port 8000{W}")
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", 8000))
        print(f"  {G}Port 8000 OPEN (server running){W}")
        s.close()
    except:
        print(f"  {R}Port 8000 CLOSED (server NOT running){W}")

    # ===== SUMMARY =====
    print(f"\n{'='*60}")
    print(f"  {Y}HOW TO FIX:{W}")
    print(f"  1. git pull")
    print(f"     del test_api.py (neu bi loi conflict)")
    print(f"     del test_system.py")
    print(f"     git pull")
    print(f"  2. Restart server (tat bat, mo lai)")
    print(f"  3. Mo display qua SERVER:")
    print(f"     {G}http://localhost:8000/display{W}")
    print(f"  {R}KHONG mo: file:///C:/.../display.html{W}")
    print(f"{'='*60}")

except Exception as e:
    print(f"\n{R}ERROR: {e}{W}")
    import traceback
    traceback.print_exc()

input("\nPress Enter to exit...")
