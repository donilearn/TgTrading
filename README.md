# TgTrading — MT5 Copy Trading Bot

Telegram guruh signallarini **Google Gemini** orqali tahlil qilib, **MetaTrader 5** da avtomatik trade ochadigan Python bot.

```
Telegram xabar → Gemini → JSON buyruq → MT5 trade
```

## Talablar

- Python 3.11+
- **MetaTrader 5 terminal** — Windows da ochiq va login qilingan
- [Telegram API](https://my.telegram.org)
- [Google AI Studio](https://aistudio.google.com/apikey) — Gemini

## O'rnatish

```powershell
git clone <repo-url>
cd TgTrading
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## `.env` — MT5 sozlamalari

| O'zgaruvchi | Tavsif |
|---|---|
| `MT5_PATH` | `terminal64.exe` yo'li (bo'sh qoldirilsa default) |
| `MT5_LOGIN` | Hisob login (integer) |
| `MT5_PASSWORD` | Hisob paroli |
| `MT5_SERVER` | Broker server nomi (ixtiyoriy) |
| `MT5_TIMEOUT` | Initialize timeout ms (default: 60000) |
| `TRADING_ENABLED` | `true` — live, `false` — dry-run |
| `ALLOWED_SYMBOLS` | Broker symbol nomlari (masalan `BTCUSDm`) |

**Muhim:** MT5 terminal ishlayotgan bo'lishi va Algo Trading yoqilgan bo'lishi kerak.

## Ishga tushirish

```powershell
python main.py
```

## Loyiha tuzilmasi

```
pipeline/orchestrator.py   # Telegram → AI → MT5
trading/mt5/               # MT5 ulanish, adapter, order builder
trading/ai_order_executor.py
ai/                        # Gemini tahlil
telegram/                  # Telethon listener
```

## Deploy (Windows VPS)

1. MT5 terminalni avto-login bilan sozlang
2. Botni Task Scheduler yoki NSSM bilan xizmat sifatida ishga tushiring
3. `.env` va `*.session` fayllarni gitga qo'ymang

## Muammolar

| Muammo | Yechim |
|---|---|
| `MT5 initialize failed` | Terminal ochiqmi, `MT5_PATH` to'g'rimi |
| `MT5 login failed` | Login/parol/server tekshiring |
| Symbol topilmadi | `ALLOWED_SYMBOLS` broker nomiga moslang |
| Order rad etildi | Algo Trading yoqilganmi, filling mode |

## Texnologiyalar

- **MetaTrader5** — Python MT5 integratsiya
- **Telethon** — Telegram
- **Google Gemini** — AI signal tahlili
