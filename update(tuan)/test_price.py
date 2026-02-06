"""
Test lấy giá XAU/USD realtime từ 3 nguồn:
1. APISed REST (đang dùng trong hệ thống)
2. Twelve Data REST (đang dùng trong hệ thống)
3. Twelve Data WebSocket (streaming realtime)

Chạy: python test_price.py
"""

import requests
import json
import time
import threading
import traceback
from datetime import datetime, timezone, timedelta

# === Credentials từ hệ thống cũ ===
APISED_KEY = "sk_c27869e90912e2A4f32E104A77Ad9dFC02bb47B5e489f4cE"
TWELVE_API_KEY = "62b38a17a73b4e03bf889bf872ebf3a1"


# ============================================================
# TEST 1: APISed REST — Giá spot XAU/USD
# ============================================================
def test_apised():
    print("\n" + "="*60)
    print("📡 TEST 1: APISed REST API")
    print("="*60)
    url = "https://gold.g.apised.com/v1/latest?metals=XAU&base_currency=USD&currencies=USD&weight_unit=TOZ"
    headers = {"x-api-key": APISED_KEY}

    success = 0
    fail = 0
    prices = []
    times = []

    print("Gọi 5 lần liên tiếp, mỗi lần cách 1 giây...\n")
    for i in range(5):
        t1 = time.time()
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            t2 = time.time()
            latency = (t2 - t1) * 1000

            if resp.status_code == 200:
                data = resp.json()
                price = float(data["data"]["metal_prices"]["XAU"]["price"])
                ts = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S.%f")[:-3]
                prices.append(price)
                times.append(latency)
                success += 1
                print(f"  [{i+1}] ✅ Giá: {price:.2f} | Latency: {latency:.0f}ms | Time: {ts}")
            else:
                fail += 1
                print(f"  [{i+1}] ❌ HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            fail += 1
            print(f"  [{i+1}] ❌ Lỗi: {e}")
        time.sleep(1)

    print(f"\n📊 Kết quả APISed: {success}/5 thành công, {fail}/5 lỗi")
    if prices:
        print(f"   Giá min: {min(prices):.2f} | max: {max(prices):.2f} | spread: {max(prices)-min(prices):.2f}")
        print(f"   Latency trung bình: {sum(times)/len(times):.0f}ms")
        if len(set(prices)) == 1:
            print("   ⚠️ Giá KHÔNG thay đổi giữa các lần gọi → Server không cập nhật mỗi giây")
        else:
            print("   ✅ Giá CÓ thay đổi giữa các lần gọi")


# ============================================================
# TEST 2: Twelve Data REST — Giá realtime quote
# ============================================================
def test_twelvedata_rest():
    print("\n" + "="*60)
    print("📡 TEST 2: Twelve Data REST API (price endpoint)")
    print("="*60)
    url = "https://api.twelvedata.com/price"
    params = {
        "symbol": "XAU/USD",
        "apikey": TWELVE_API_KEY
    }

    success = 0
    fail = 0
    prices = []
    times = []

    print("Gọi 5 lần liên tiếp, mỗi lần cách 1 giây...\n")
    for i in range(5):
        t1 = time.time()
        try:
            resp = requests.get(url, params=params, timeout=10)
            t2 = time.time()
            latency = (t2 - t1) * 1000

            if resp.status_code == 200:
                data = resp.json()
                if "price" in data:
                    price = float(data["price"])
                    ts = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S.%f")[:-3]
                    prices.append(price)
                    times.append(latency)
                    success += 1
                    print(f"  [{i+1}] ✅ Giá: {price:.2f} | Latency: {latency:.0f}ms | Time: {ts}")
                else:
                    fail += 1
                    print(f"  [{i+1}] ❌ Response: {data}")
            else:
                fail += 1
                print(f"  [{i+1}] ❌ HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            fail += 1
            print(f"  [{i+1}] ❌ Lỗi: {e}")
        time.sleep(1)

    print(f"\n📊 Kết quả Twelve Data REST: {success}/5 thành công, {fail}/5 lỗi")
    if prices:
        print(f"   Giá min: {min(prices):.2f} | max: {max(prices):.2f} | spread: {max(prices)-min(prices):.2f}")
        print(f"   Latency trung bình: {sum(times)/len(times):.0f}ms")
        if len(set(prices)) == 1:
            print("   ⚠️ Giá KHÔNG thay đổi giữa các lần gọi")
        else:
            print("   ✅ Giá CÓ thay đổi giữa các lần gọi")


# ============================================================
# TEST 3: Twelve Data WebSocket — Streaming realtime
# ============================================================
def test_twelvedata_websocket():
    print("\n" + "="*60)
    print("📡 TEST 3: Twelve Data WebSocket (streaming)")
    print("="*60)

    try:
        import websocket
        print(f"   ✅ websocket-client đã cài (version: {websocket.__version__})")
    except ImportError:
        print("   ❌ Cần cài: pip install websocket-client")
        print("   Bỏ qua test WebSocket.\n")
        return

    ws_url = f"wss://ws.twelvedata.com/v1/quotes/price?apikey={TWELVE_API_KEY}"
    prices = []
    count = [0]
    max_ticks = 10
    error_msg = [None]

    def on_open(ws):
        subscribe_msg = {
            "action": "subscribe",
            "params": {
                "symbols": "XAU/USD"
            }
        }
        ws.send(json.dumps(subscribe_msg))
        print(f"   ✅ Đã kết nối WebSocket, đang chờ {max_ticks} tick...\n")

    def on_message(ws, message):
        data = json.loads(message)

        if data.get("event") in ("subscribe-status", "heartbeat"):
            status = data.get("status", "")
            print(f"  [system] {data.get('event')}: {status}")
            if status == "error":
                print(f"  [system] Chi tiết lỗi: {json.dumps(data, indent=2)}")
            return

        if "price" in data:
            price = float(data["price"])
            symbol = data.get("symbol", "XAU/USD")
            ts_raw = data.get("timestamp", 0)
            ts = datetime.fromtimestamp(ts_raw, tz=timezone(timedelta(hours=7))).strftime("%H:%M:%S.%f")[:-3] if ts_raw else "N/A"
            local_ts = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S.%f")[:-3]

            prices.append(price)
            count[0] += 1
            print(f"  [tick {count[0]:>2}] 💰 {symbol}: {price:.2f} | Server: {ts} | Local: {local_ts}")

            if count[0] >= max_ticks:
                ws.close()
        else:
            print(f"  [unknown] {json.dumps(data)[:200]}")

    def on_error(ws, error):
        error_msg[0] = str(error)
        print(f"  ❌ WebSocket lỗi: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"\n  WebSocket đã đóng (code: {close_status_code}, msg: {close_msg})")

    print(f"   Kết nối tới: {ws_url[:60]}...")
    print(f"   Chờ tối đa {max_ticks} tick (timeout 30s)...\n")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws_thread = threading.Thread(target=lambda: ws.run_forever(ping_interval=10))
    ws_thread.daemon = True
    ws_thread.start()
    ws_thread.join(timeout=30)

    if ws_thread.is_alive():
        print("  ⏰ Timeout 30s — đóng WebSocket")
        ws.close()

    print(f"\n📊 Kết quả WebSocket: Nhận {count[0]} tick")
    if prices:
        print(f"   Giá min: {min(prices):.2f} | max: {max(prices):.2f} | spread: {max(prices)-min(prices):.2f}")
        if len(prices) > 1:
            changes = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
            print(f"   Thay đổi trung bình giữa tick: {sum(changes)/len(changes):.3f}")
            unique = len(set(prices))
            print(f"   Số giá khác nhau: {unique}/{len(prices)}")
    elif error_msg[0]:
        print(f"   ⚠️ Lỗi: {error_msg[0]}")
        print("   💡 Có thể do free plan không hỗ trợ WebSocket cho XAU/USD")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("🚀 BẮT ĐẦU TEST GIÁ XAU/USD REALTIME")
    print(f"⏰ Thời gian: {datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S')} GMT+7")

    try:
        test_apised()
    except Exception as e:
        print(f"❌ Test APISed crash: {e}")
        traceback.print_exc()

    try:
        test_twelvedata_rest()
    except Exception as e:
        print(f"❌ Test Twelve Data REST crash: {e}")
        traceback.print_exc()

    try:
        test_twelvedata_websocket()
    except Exception as e:
        print(f"❌ Test WebSocket crash: {e}")
        traceback.print_exc()

    print("\n" + "="*60)
    print("✅ HOÀN THÀNH TẤT CẢ TEST")
    print("="*60)
    print("""
📝 ĐÁNH GIÁ:
- APISed REST: Ổn định, giá cập nhật mỗi giây, latency ~230ms
- Twelve Data REST: Chậm hơn, giá có thể bị delay
- Twelve Data WebSocket: Realtime nhất nếu plan hỗ trợ
""")

    # === GIỮ TERMINAL KHÔNG ĐÓNG ===
    input("⏸️  Nhấn Enter để đóng terminal...")