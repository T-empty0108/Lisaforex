# =============================================================================
# LISA FOREX - TELEGRAM HTML BOT (Telethon) - MT5 VERSION
# Refactored: Thay APISed bang MT5 EXNESS de lay gia XAUUSD
# =============================================================================

import os
import sys
import json
import re
import asyncio
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel

# === HTTP client de lay gia tu server(mt5).py ===
try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# =============================================================================
# LOAD CONFIG
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SIGNAL_GROUP_ID = int(os.getenv("SIGNAL_GROUP_ID", "2866162244"))
REPORT_GROUP_ID = int(os.getenv("REPORT_GROUP_ID", "3103146104"))
# APISED_KEY khong can nua

DATA_PATH = os.path.join(BASE_DIR, "data.json")
STATE_PATH = os.path.join(BASE_DIR, "signals_state.json")
import platform
_hostname = platform.node().replace(" ", "_").replace(".", "_")
SESSION_PATH = os.path.join(BASE_DIR, f"telegram_session_{_hostname}")

HISTORY_LIMIT = 200
UPDATE_INTERVAL = 1

# Server URL (server(mt5).py da chiem MT5, bot lay gia qua API)
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

def get_gold_price():
    """Lay gia XAUUSD tu server(mt5).py qua /api/price"""
    try:
        resp = requests.get(f"{SERVER_URL}/api/price", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("price")
            if price and price > 0:
                return float(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except Exception:
        pass
    return None


# =============================================================================
# UTILITY FUNCTIONS (giu nguyen)
# =============================================================================

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"signals": {}, "report": None}

def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def save_data_json(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def clean_old_signals(signals):
    now = datetime.now()
    cutoff = now - timedelta(hours=24)
    cleaned = {}
    for timestamp, data in signals.items():
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            if dt > cutoff:
                cleaned[timestamp] = data
        except:
            cleaned[timestamp] = data
    return cleaned

def gmt7_to_gmt0(dt):
    if dt is None:
        return None
    return dt - timedelta(hours=7)

def format_time_gmt0(dt):
    if dt is None:
        return ""
    dt_gmt0 = gmt7_to_gmt0(dt)
    return dt_gmt0.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")

def calc_profit(entry, current_price, signal_type, status):
    if entry is None or current_price is None:
        return 0.0
    if "BUY" in signal_type.upper():
        return round((current_price - entry) * 10, 1)
    else:
        return round((entry - current_price) * 10, 1)

# =============================================================================
# PARSE TELEGRAM MESSAGES (giu nguyen)
# =============================================================================

def parse_signal_message(text):
    if "Signal:" not in text:
        return None
    if "=== EXPLANATION ===" in text or "HOLD" in text.upper():
        return None

    try:
        signal_match = re.search(r"Signal:\s*(BUY\s*STOP|BUY\s*LIMIT|SELL\s*STOP|SELL\s*LIMIT|BUY|SELL)", text, re.IGNORECASE)
        signal_type = signal_match.group(1).upper() if signal_match else None
        if signal_type:
            signal_type = " ".join(signal_type.split())

        entry_match = re.search(r"Entry:\s*([\d.]+)", text)
        entry = float(entry_match.group(1)) if entry_match else None

        tp1 = float(re.search(r"TP1:\s*([\d.]+)", text).group(1)) if re.search(r"TP1:\s*([\d.]+)", text) else None
        tp2 = float(re.search(r"TP2:\s*([\d.]+)", text).group(1)) if re.search(r"TP2:\s*([\d.]+)", text) else None
        tp3 = float(re.search(r"TP3:\s*([\d.]+)", text).group(1)) if re.search(r"TP3:\s*([\d.]+)", text) else None
        sl = float(re.search(r"SL:\s*([\d.]+)", text).group(1)) if re.search(r"SL:\s*([\d.]+)", text) else None

        time_match = re.search(r"Generated at:\s*([\d-]+\s+[\d:]+)", text)
        timestamp = time_match.group(1) if time_match else None

        if signal_type and entry:
            return {
                "timestamp": timestamp,
                "signal": signal_type,
                "entry": entry,
                "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl,
                "status": "pending",
                "profit_pips": None,
                "entry_time": None,
                "close_time": None
            }
    except:
        pass
    return None

def parse_entry_hit(text):
    if "hit entry" in text.lower():
        price_match = re.search(r"price\s*([\d.]+)", text)
        if price_match:
            return {"status": "running", "entry_hit_price": float(price_match.group(1))}
    return None

def parse_tp_hit(text):
    tp_patterns = [
        (r"🥇\s*TP1\s*hit", "tp1_hit"),
        (r"🥈\s*TP2\s*hit", "tp2_hit"),
        (r"🥉\s*TP3\s*hit", "tp3_hit"),
        (r"TP1\s*hit", "tp1_hit"),
        (r"TP2\s*hit", "tp2_hit"),
        (r"TP3\s*hit", "tp3_hit"),
    ]
    for pattern, status in tp_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            price_match = re.search(r"Price:\s*([\d.]+)", text)
            pips_match = re.search(r"\(([\+\-]?[\d.]+)\s*p\)", text)
            return {
                "status": status,
                "hit_price": float(price_match.group(1)) if price_match else None,
                "hit_pips": float(pips_match.group(1)) if pips_match else None
            }
    return None

def parse_sl_hit(text):
    if "SL hit" in text or ("🛑" in text and "hit" in text.lower()):
        price_match = re.search(r"Price:\s*([\d.]+)", text)
        pips_match = re.search(r"\(([\+\-]?[\d.]+)\s*p\)", text)
        return {
            "status": "sl_hit",
            "sl_hit_price": float(price_match.group(1)) if price_match else None,
            "sl_hit_pips": float(pips_match.group(1)) if pips_match else None
        }
    return None

def parse_exit(text):
    exit_match = re.search(r"⏳\s*Exit\s*at\s*price\s*([\d.]+)\s*\(([\+\-]?[\d.]+)\s*p\)", text, re.IGNORECASE)
    if exit_match:
        try:
            return {
                "status": "exit",
                "exit_price": float(exit_match.group(1)),
                "exit_pips": float(exit_match.group(2))
            }
        except:
            pass
    return None

def parse_cancel(text):
    if "❌ CANCEL" in text or "CANCEL:" in text.upper():
        return {"action": "cancel"}
    return None

def parse_yesterday_report(text, target_date_str):
    if "Tổng hợp lệnh XAU ngày" not in text or target_date_str not in text:
        return None
    try:
        clean_text = text.replace("**", "").replace("__", "")

        tp_match = re.search(r"TP:\s*(\d+)\s*\(Tổng\s*([\+\-]?[\d.]+)\s*pip\)", clean_text)
        tp_count = int(tp_match.group(1)) if tp_match else 0
        tp_pips = float(tp_match.group(2)) if tp_match else 0.0

        sl_match = re.search(r"SL:\s*(\d+)\s*\(Tổng\s*([\+\-]?[\d.]+)\s*pip\)", clean_text)
        sl_count = int(sl_match.group(1)) if sl_match else 0
        sl_pips = float(sl_match.group(2)) if sl_match else 0.0

        exit_match = re.search(r"Exit:\s*(\d+)\s*\(Tổng\s*([\+\-]?[\d.]+)\s*pip\)", clean_text)
        exit_count = int(exit_match.group(1)) if exit_match else 0
        exit_pips = float(exit_match.group(2)) if exit_match else 0.0

        net_match = re.search(r"Tổng lệnh:\s*([\+\-]?[\d.]+)\s*pip", clean_text)
        net_pips = float(net_match.group(1)) if net_match else (tp_pips + sl_pips + exit_pips)

        return {
            "date": target_date_str,
            "tp_count": tp_count, "tp_pips": tp_pips,
            "sl_count": sl_count, "sl_pips": sl_pips,
            "exit_count": exit_count, "exit_pips": exit_pips,
            "net_pips": net_pips
        }
    except:
        return None

def process_message(text, signals, msg_time=None, is_history=False):
    changed = False

    # CANCEL
    if parse_cancel(text):
        pending = [(ts, s) for ts, s in signals.items() if s.get("status") == "pending"]
        if pending:
            pending.sort(key=lambda x: x[0], reverse=True)
            del signals[pending[0][0]]
            if not is_history:
                print(f"  CANCEL")
            return True
        return False

    # Signal moi
    signal_data = parse_signal_message(text)
    if signal_data:
        timestamp = signal_data.pop("timestamp")
        if not timestamp and msg_time:
            timestamp = msg_time.strftime("%Y-%m-%d %H:%M:%S")
        elif not timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if timestamp not in signals:
            signal_data["signal_time"] = msg_time.strftime("%Y-%m-%d %H:%M:%S") if msg_time else timestamp
            signals[timestamp] = signal_data
            if not is_history:
                print(f"  Signal: {signal_data['signal']} @ {signal_data['entry']}")
            return True
        return False

    # Entry hit
    entry_hit = parse_entry_hit(text)
    if entry_hit:
        for ts in sorted(signals.keys(), reverse=True):
            if signals[ts].get("status") == "pending":
                signals[ts]["status"] = "running"
                signals[ts]["entry_time"] = msg_time.strftime("%Y-%m-%d %H:%M:%S") if msg_time else None
                if not is_history:
                    print(f"  Entry hit")
                return True
        return False

    # TP hit
    tp_hit = parse_tp_hit(text)
    if tp_hit:
        new_status = tp_hit["status"]
        for ts in sorted(signals.keys(), reverse=True):
            current_status = signals[ts].get("status", "")
            valid = {"tp1_hit": ["running"], "tp2_hit": ["running", "tp1_hit"], "tp3_hit": ["running", "tp1_hit", "tp2_hit"]}
            if current_status in valid.get(new_status, ["running"]):
                signals[ts]["status"] = new_status
                if tp_hit.get("hit_pips") is not None:
                    signals[ts]["profit_pips"] = tp_hit["hit_pips"]
                signals[ts]["close_time"] = msg_time.strftime("%Y-%m-%d %H:%M:%S") if msg_time else None
                if not is_history:
                    print(f"  {new_status.upper()}: {tp_hit.get('hit_pips')}p")
                return True
        return False

    # SL hit
    sl_hit = parse_sl_hit(text)
    if sl_hit:
        for ts in sorted(signals.keys(), reverse=True):
            if signals[ts].get("status") in ("running", "pending", "tp1_hit", "tp2_hit"):
                signals[ts]["status"] = "sl_hit"
                if sl_hit.get("sl_hit_pips") is not None:
                    signals[ts]["profit_pips"] = sl_hit["sl_hit_pips"]
                signals[ts]["close_time"] = msg_time.strftime("%Y-%m-%d %H:%M:%S") if msg_time else None
                if not is_history:
                    print(f"  SL hit: {sl_hit.get('sl_hit_pips')}p")
                return True
        return False

    # EXIT
    exit_data = parse_exit(text)
    if exit_data:
        for ts in sorted(signals.keys(), reverse=True):
            if signals[ts].get("status") in ("running", "pending", "tp1_hit", "tp2_hit"):
                signals[ts]["status"] = "exit"
                signals[ts]["profit_pips"] = exit_data["exit_pips"]
                signals[ts]["close_time"] = msg_time.strftime("%Y-%m-%d %H:%M:%S") if msg_time else None
                if not is_history:
                    print(f"  EXIT: {exit_data['exit_pips']}p")
                return True
        return False

    return False

# =============================================================================
# BUILD DATA FOR HTML (giu nguyen)
# =============================================================================

def build_data_for_html(signals, report, current_price):
    valid_signals = [(ts, s) for ts, s in signals.items() if s.get("status") != "cancelled"]
    valid_signals.sort(key=lambda x: x[0], reverse=True)

    current_signal = None
    if valid_signals:
        ts, sig = valid_signals[0]
        current_signal = build_signal_data(ts, sig, current_price, is_current=True)

    prev_signals = []
    for ts, sig in valid_signals[1:4]:
        prev_signals.append(build_signal_data(ts, sig, current_price, is_current=False))

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_price": current_price,
        "current_signal": current_signal,
        "previous_signals": prev_signals,
        "yesterday_report": report
    }

def build_signal_data(timestamp, sig, current_price, is_current=False):
    if not sig:
        return None

    status = sig.get("status", "pending")
    signal_type = sig.get("signal", "")
    entry = sig.get("entry")
    profit_pips = sig.get("profit_pips")

    if status == "pending":
        profit = 0.0
    elif status == "running":
        profit = calc_profit(entry, current_price, signal_type, status) if current_price else 0.0
    else:
        profit = profit_pips if profit_pips is not None else 0.0

    status_display = {"pending": "Waiting", "running": "Running", "tp1_hit": "TP1", "tp2_hit": "TP2", "tp3_hit": "TP3", "sl_hit": "SL", "exit": "Exit"}.get(status, status)

    display_time = (sig.get("entry_time") or sig.get("signal_time")) if is_current else (sig.get("close_time") or sig.get("entry_time") or sig.get("signal_time"))
    time_formatted = ""
    if display_time:
        try:
            dt = datetime.strptime(display_time, "%Y-%m-%d %H:%M:%S")
            time_formatted = format_time_gmt0(dt)
        except:
            pass

    return {
        "timestamp": timestamp,
        "signal": signal_type,
        "entry": entry,
        "tp1": sig.get("tp1"), "tp2": sig.get("tp2"), "tp3": sig.get("tp3"), "sl": sig.get("sl"),
        "status": status,
        "status_display": status_display,
        "profit": profit,
        "profit_formatted": f"+{profit:.1f}p" if profit >= 0 else f"{profit:.1f}p",
        "time_formatted": time_formatted,
        "signal_time": sig.get("signal_time"),
        "entry_time": sig.get("entry_time"),
        "close_time": sig.get("close_time"),
        "tp1_hit": status in ("tp1_hit", "tp2_hit", "tp3_hit"),
        "tp2_hit": status in ("tp2_hit", "tp3_hit"),
        "tp3_hit": status == "tp3_hit",
        "sl_hit": status == "sl_hit",
        "is_buy": "BUY" in signal_type.upper() if signal_type else True,
        "is_win": profit > 0,
        "is_loss": profit < 0
    }

# =============================================================================
# TELETHON CLIENT (thay doi: dung MT5 thay APISed)
# =============================================================================

class LisaForexBot:
    def __init__(self):
        self.state = load_state()
        self.signals = self.state.get("signals", {})
        self.report = self.state.get("report")
        self.client = None
        self.running = True

    async def load_signal_history(self):
        print(f"  Loading {HISTORY_LIMIT} messages tu Signal group...")
        try:
            entity = await self.client.get_entity(PeerChannel(SIGNAL_GROUP_ID))
            messages = []
            async for message in self.client.iter_messages(entity, limit=HISTORY_LIMIT):
                if message.text:
                    messages.append({"text": message.text, "date": message.date})

            print(f"  Nhan duoc {len(messages)} messages")
            messages.sort(key=lambda x: x["date"])

            for msg in messages:
                msg_time = msg["date"].replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7)))
                msg_time = msg_time.replace(tzinfo=None)
                process_message(msg["text"], self.signals, msg_time=msg_time, is_history=True)

            self.signals = clean_old_signals(self.signals)
            print(f"  Loaded {len(self.signals)} signals")
        except Exception as e:
            print(f"  Loi load signal history: {e}")

    async def load_yesterday_report(self):
        print(f"  Loading Yesterday Report...")
        try:
            yesterday = datetime.now() - timedelta(days=1)
            target_date_str = yesterday.strftime("%d/%m/%Y")
            print(f"  Tim report ngay: {target_date_str}")

            entity = await self.client.get_entity(PeerChannel(REPORT_GROUP_ID))

            all_reports = []
            async for message in self.client.iter_messages(entity, limit=500):
                if message.text and "Tổng hợp lệnh XAU ngày" in message.text and target_date_str in message.text:
                    report = parse_yesterday_report(message.text, target_date_str)
                    if report:
                        all_reports.append(report)

            if all_reports:
                best_report = max(all_reports, key=lambda r: r["tp_count"] + r["sl_count"] + r["exit_count"] + abs(r["net_pips"]))
                self.report = best_report
                try:
                    dt = datetime.strptime(best_report["date"], "%d/%m/%Y")
                    self.report["date_display"] = dt.strftime("%b %d, %Y")
                except:
                    self.report["date_display"] = best_report["date"]
                print(f"  Found report: TP={best_report['tp_count']} SL={best_report['sl_count']} NET={best_report['net_pips']}p")
            else:
                print(f"  Khong tim thay report ngay {target_date_str}")
                self.report = None
        except Exception as e:
            print(f"  Loi load report: {e}")

    async def on_new_signal_message(self, event):
        try:
            text = event.message.text
            if not text:
                return
            msg_time = event.message.date.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7)))
            msg_time = msg_time.replace(tzinfo=None)
            if process_message(text, self.signals, msg_time=msg_time, is_history=False):
                self.signals = clean_old_signals(self.signals)
                self.save_all()
        except Exception as e:
            print(f"  Loi: {e}")

    async def on_new_report_message(self, event):
        try:
            text = event.message.text
            if not text:
                return
            yesterday = datetime.now() - timedelta(days=1)
            target_date_str = yesterday.strftime("%d/%m/%Y")
            report = parse_yesterday_report(text, target_date_str)
            if report:
                self.report = report
                try:
                    dt = datetime.strptime(report["date"], "%d/%m/%Y")
                    self.report["date_display"] = dt.strftime("%b %d, %Y")
                except:
                    self.report["date_display"] = report["date"]
                print(f"  Updated report: NET {report['net_pips']}p")
                self.save_all()
        except Exception as e:
            print(f"  Loi: {e}")

    def save_all(self):
        self.state["signals"] = self.signals
        self.state["report"] = self.report
        save_state(self.state)

    async def update_loop(self):
        """Vong lap cap nhat gia - dung MT5 thay APISed"""
        price_fail_count = 0
        while self.running:
            try:
                current_price = get_gold_price()
                if current_price:
                    price_fail_count = 0
                else:
                    price_fail_count += 1
                    if price_fail_count % 30 == 1:  # Log moi 30s
                        print(f"[Price] Khong lay duoc gia (lan thu {price_fail_count})")

                data = build_data_for_html(self.signals, self.report, current_price)
                save_data_json(data)
            except Exception as e:
                print(f"[Price] Update loop error: {e}")
            await asyncio.sleep(UPDATE_INTERVAL)

    async def run(self):
        print("=" * 60)
        print("  LISA FOREX - Telegram HTML Bot (MT5 Version)")
        print("=" * 60)
        print(f"  Data: {DATA_PATH}")
        print(f"  Signal Group: {SIGNAL_GROUP_ID}")
        print(f"  Report Group: {REPORT_GROUP_ID}")
        print(f"  Price source: server(mt5).py -> {SERVER_URL}/api/price")
        print("=" * 60)

        # Test gia tu server
        test_price = get_gold_price()
        if test_price:
            print(f"[Price] Gia hien tai: {test_price}")
        else:
            print("[Price] WARNING: Chua lay duoc gia (server chua san sang hoac ngoai gio)")

        if not API_ID or not API_HASH:
            print("  Chua dien API_ID va API_HASH trong file .env")
            return

        self.client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        print("  Dang ket noi Telegram...")
        await self.client.start()
        print("  Da ket noi Telegram")

        await self.load_signal_history()
        await self.load_yesterday_report()
        self.save_all()

        current_price = get_gold_price()
        data = build_data_for_html(self.signals, self.report, current_price)
        save_data_json(data)
        print(f"  Da tao data.json")

        @self.client.on(events.NewMessage(chats=PeerChannel(SIGNAL_GROUP_ID)))
        async def signal_handler(event):
            await self.on_new_signal_message(event)

        @self.client.on(events.NewMessage(chats=PeerChannel(REPORT_GROUP_ID)))
        async def report_handler(event):
            await self.on_new_report_message(event)

        print("=" * 60)
        print("  Bot san sang! Dang lang nghe messages...")
        print("  Nguon gia: server(mt5).py -> MT5 EXNESS")
        print("  Nhan Ctrl+C de dung")
        print("=" * 60)

        update_task = asyncio.create_task(self.update_loop())
        await self.client.run_until_disconnected()
        self.running = False
        update_task.cancel()

async def main():
    bot = LisaForexBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Da dung bot.")
    except Exception as e:
        print(f"  Loi: {e}")
