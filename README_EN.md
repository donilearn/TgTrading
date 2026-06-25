# TgTrading — MT5 Copy Trading Bot

Python bot that analyzes Telegram group signals with **Google Gemini** and executes trades via **MetaTrader 5** Python API.

```
Telegram message → Gemini → JSON command → MT5 trade
```

## Requirements

- Python 3.11+
- **MetaTrader 5 terminal** — running and logged in on Windows
- [Telegram API](https://my.telegram.org)
- [Google AI Studio](https://aistudio.google.com/apikey)

## Setup

```bash
git clone <repo-url>
cd TgTrading
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## `.env` — MT5 settings

| Variable | Description |
|---|---|
| `MT5_PATH` | Path to `terminal64.exe` (optional) |
| `MT5_LOGIN` | Account login (integer) |
| `MT5_PASSWORD` | Account password |
| `MT5_SERVER` | Broker server name (optional) |
| `MT5_TIMEOUT` | Initialize timeout ms (default: 60000) |
| `TRADING_ENABLED` | `true` — live, `false` — dry-run |
| `ALLOWED_SYMBOLS` | Broker symbol names (e.g. `BTCUSDm`) |

**Important:** MT5 terminal must be running with Algo Trading enabled.

## Run

```powershell
python main.py
```

## Architecture

```
pipeline/orchestrator.py   # Telegram → AI → MT5
trading/mt5/               # MT5 connection, adapter, order builder
trading/ai_order_executor.py
ai/                        # Gemini analysis
telegram/                  # Telethon listener
```

## Troubleshooting

| Issue | Fix |
|---|---|
| `MT5 initialize failed` | Check terminal is open, verify `MT5_PATH` |
| `MT5 login failed` | Verify login/password/server |
| Unknown symbol | Match `ALLOWED_SYMBOLS` to broker names |
| Order rejected | Enable Algo Trading, check filling mode |

## Stack

- **MetaTrader5** — [Python integration docs](https://www.mql5.com/en/docs/python_metatrader5)
- **Telethon** — Telegram
- **Google Gemini** — AI signal analysis
