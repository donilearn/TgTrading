# TgTrading — Copy Trading Bot

Analyzes Telegram signals with **Google Gemini** and executes trades via **MetaAPI** (default) or **local MT5** (`--win`).

## Run

```powershell
python main.py          # MetaAPI cloud (VPS)
python main.py --win    # Windows MT5 terminal
```

## `.env`

- **Default:** `METAAPI_TOKEN`, `METAAPI_ACCOUNT_ID`
- **`--win`:** `MT5_LOGIN`, `MT5_PASSWORD`, optional `MT5_PATH`

See `.env.example` for full list.

## Stack

MetaAPI Cloud SDK · MetaTrader5 · Telethon · Google Gemini
