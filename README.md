# LISA FOREX - XAU/USD Real-time Chart & Signal Display

Real-time XAU/USD candlestick chart with live trading signal overlay from Telegram.

## System Architecture

```
Telegram Group                    Browser
(mInvestAI-Elite)
      |                           +------------------+
      v                           | chart.html       |
telegram_html_bot.py ---> data.json <--- server.py ---> | (localhost:8000)  |
                    |              |     |            +------------------+
                    v              |     |
              signals_state.json   |     +---> WebSocket (live price)
                                   |     +---> /api/history (candles)
                                   |     +---> /api/signal (signal data)
                                   |
                                   +---> display.html (signal panel, standalone)
```

### Components

| File | Role |
|------|------|
| `server.py` | FastAPI server: proxies TradingView history, APISed real-time price via WebSocket, serves chart.html, and exposes `/api/signal` |
| `chart.html` | Lightweight Charts v4 candlestick chart with VIDYA indicator, real-time price updates, and signal entry line overlay |
| `update(tuan)/telegram_html_bot.py` | Telethon bot monitoring Telegram group for trading signals, writes `data.json` and `signals_state.json` |
| `update(tuan)/display.html` | Standalone signal display panel (400px), reads `data.json` via XHR |
| `update(tuan)/START_LISA_FOREX.bat` | One-click launcher: git pull + start all services + open browser |

## Signal Lifecycle

Signals from Telegram follow this lifecycle:

```
Signal received -> WAITING (pending, blinking blue)
Price hits entry -> RUNNING (blinking yellow)
Price hits TP1   -> TP1 (green)
Price hits TP2   -> TP2 (green)
Price hits TP3   -> TP3 (green)
Price hits SL    -> SL (red)
Signal cancelled -> removed from chart
```

Signal types: `BUY LIMIT`, `BUY STOP`, `SELL LIMIT`, `SELL STOP`

On the chart, the current signal is displayed as:
- A yellow dashed horizontal line at the entry price
- A label showing signal type + entry price (e.g., "BUY LIMIT 4838.10")
- A status badge showing current state (WAITING / RUNNING / TP1-3 / SL)

## Data Format

### data.json

Written by `telegram_html_bot.py` every ~1 second.

```json
{
  "updated_at": "2026-02-06 14:07:51",
  "current_price": 4842.75,
  "current_signal": {
    "timestamp": "2026-02-06 14:07:51",
    "signal": "BUY STOP",
    "entry": 4842.75,
    "tp1": 4845.75,
    "tp2": 4847.75,
    "tp3": 4851.0,
    "sl": 4839.5,
    "status": "pending",
    "tp1_hit": false,
    "tp2_hit": false,
    "tp3_hit": false,
    "sl_hit": false
  },
  "previous_signals": [...],
  "yesterday_report": {...}
}
```

**Note:** All timestamps in data.json are GMT+7. The chart converts them to UTC internally.

### signals_state.json

Full signal history with entry/close times and profit in pips.

## Setup

### Requirements

- Python 3.10+
- Packages:
  ```
  pip install fastapi uvicorn websocket-client httpx numpy telethon python-dotenv requests
  ```

### First-time Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd "lisa test"
   ```

2. **Create `update(tuan)/.env`:**
   ```env
   API_ID=your_telegram_api_id
   API_HASH=your_telegram_api_hash
   SIGNAL_GROUP_ID=2866162244
   REPORT_GROUP_ID=3103146104
   APISED_KEY=your_apised_key
   ```

3. **Create Telegram session:**
   ```bash
   cd update(tuan)
   python telegram_html_bot.py
   ```
   Follow the prompts to authenticate with Telegram. This creates `telegram_session.session`.

4. **Run the launcher:**
   Double-click `update(tuan)/START_LISA_FOREX.bat`

### What START_LISA_FOREX.bat Does

1. `git pull` - updates code from GitHub
2. Starts `server.py` on port 8000 (background)
3. Opens `http://localhost:8000/` (chart) and `display.html` (signal panel) in browser
4. Starts `telegram_html_bot.py` (foreground, keeps window open)
5. On Ctrl+C: kills server process and exits

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serves chart.html |
| `GET /api/history?interval=1&bars=1500` | Historical OHLC candles from TradingView |
| `GET /api/price` | Current price from APISed |
| `WS /ws/price` | Real-time price WebSocket (1s interval) |
| `GET /api/signal` | Current signal data from data.json |

## Deploying to a Second Machine

1. Clone the repo on the new machine
2. Install Python + packages (see Requirements)
3. Create `update(tuan)/.env` with your credentials
4. Run `telegram_html_bot.py` once to create the Telegram session
5. Double-click `update(tuan)/START_LISA_FOREX.bat`

Files that stay local (not in git): `.env`, `*.session`, `data.json`, `signals.json`, `signals_state.json`

## Timezone

- Telegram timestamps: GMT+7
- Chart display: UTC (GMT+0)
- The chart auto-converts GMT+7 timestamps to UTC
