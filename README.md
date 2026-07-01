# TgTrading — Copy Trading Bot

Telegram signallarini **Google Gemini** orqali tahlil qilib avtomatik trade ochadigan Python bot.

```
Telegram xabar → Gemini → JSON buyruq → MetaAPI yoki MT5
```

## Backend

| Rejim | Buyruq | Platforma |
|---|---|---|
| **MetaAPI** (default) | `python main.py` | VPS / Linux / Windows |
| **MT5 local** | `python main.py --win` | Windows (terminal ochiq) |

## Talablar

- Python 3.11+
- [Telegram API](https://my.telegram.org)
- [Google AI Studio](https://aistudio.google.com/apikey)
- **MetaAPI:** [MetaAPI Cloud](https://app.metaapi.cloud) token + account ID
- **--win:** MetaTrader 5 terminal ochiq, Algo Trading yoqilgan

## O'rnatish

```powershell
git clone <repo-url>
cd TgTrading
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## `.env`

**MetaAPI (default):** `METAAPI_TOKEN`, `METAAPI_ACCOUNT_ID`

**MT5 (--win):** `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_PATH` (ixtiyoriy)

Umumiy: `TRADING_ENABLED`, `ALLOWED_SYMBOLS`, `TELEGRAM_*`, `GEMINI_*`

## Ishga tushirish

```powershell
python main.py          # MetaAPI cloud
python main.py --win    # Windows MT5 terminal
```

## Loyiha tuzilmasi

```
pipeline/orchestrator.py   # Telegram → AI → trade
trading/metaapi/           # MetaAPI (default)
trading/mt5/               # MT5 local (--win)
ai/                        # Gemini tahlil
telegram/                  # Telethon
```

## Muammolar

| Muammo | Yechim |
|---|---|
| `METAAPI_TOKEN required` | `.env` da MetaAPI kalitlari yoki `--win` ishlating |
| `MT5 initialize failed` | Terminal ochiqmi, `--win` Windows dami |
| Symbol topilmadi | `ALLOWED_SYMBOLS` broker nomiga moslang |

## Texnologiyalar

- **MetaAPI Cloud SDK** / **MetaTrader5**
- **Telethon**, **Google Gemini**
