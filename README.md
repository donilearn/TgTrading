# TgTrading

Telegram guruh signallarini Google Gemini orqali tahlil qilib, MetaAPI (MT4/MT5) da avtomatik trade ochadigan Python bot.

```
Telegram xabar → Gemini (JSON buyruq) → MetaAPI trade
```

## Imkoniyatlar

- Telegram guruh(lar)dan xabar va media o‘qish
- Har xabar uchun kontekst, mavjud orderlar va bozor narxi (bid/ask) bilan AI tahlil
- AI to‘liq qaror qiladi: symbol, side, orderType, narx, SL/TP
- App faqat AI JSON ni bajaradi
- Har guruh uchun alohida **magic number** (chat ID dan)
- Order limitlari (guruh + global), `AGGRESSIVE_MODE` (2× limit)
- `TRADING_ENABLED=false` — dry-run (haqiqiy trade yo‘q)

## Talablar

- Python 3.11+
- [Telegram API](https://my.telegram.org) — `API_ID`, `API_HASH`
- [Google AI Studio](https://aistudio.google.com/apikey) — Gemini API key
- [MetaAPI Cloud](https://app.metaapi.cloud) — token va MT4/MT5 account ID
- VPS yoki doimiy ishlaydigan server (Telegram session saqlanadi)

## O‘rnatish

```bash
git clone <repo-url>
cd TgTrading

python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

## Sozlash

`.env.example` ni `.env` ga nusxalang va to‘ldiring:

```bash
cp .env.example .env   # Linux/macOS
copy .env.example .env # Windows
```

### `.env` o‘zgaruvchilari

| O‘zgaruvchi | Tavsif |
|---|---|
| `TELEGRAM_API_ID` | Telegram API ID |
| `TELEGRAM_API_HASH` | Telegram API hash |
| `TELEGRAM_SESSION_NAME` | Session fayl nomi (default: `tgtrading`) |
| `TELEGRAM_GROUP_IDS` | Guruh chat ID lar, vergul bilan (masalan `-1001234567890`) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Asosiy model (default: `gemini-2.5-flash`) |
| `GEMINI_FALLBACK_MODELS` | Zaxira modellar, vergul bilan |
| `METAAPI_TOKEN` | MetaAPI token |
| `METAAPI_ACCOUNT_ID` | MetaAPI account UUID |
| `TRADING_ENABLED` | `true` — live trade, `false` — dry-run |
| `ALLOWED_SYMBOLS` | Broker symbol nomlari, vergul bilan (masalan `BTCUSDm,EURUSD`) |
| `DEFAULT_SYMBOL` | Default symbol (ixtiyoriy) |
| `DEFAULT_VOLUME` | Default lot (default: `0.01`) |
| `MIN_VOLUME` / `MAX_VOLUME` | Lot chegaralari |
| `MAX_ORDER_COUNT` | Global order limiti (default: `20`) |
| `MAX_ORDER_PER_GROUP` | Guruh order limiti (default: `5`) |
| `CONTEXT_MESSAGE_COUNT` | AI kontekst xabarlar soni (default: `5`) |
| `AGGRESSIVE_MODE` | `true` — limitlar 2×, zone + market strategiya |

**Muhim:**

- `ALLOWED_SYMBOLS` brokerdagi **aniq** symbol nomi bo‘lishi kerak (masalan `BTCUSDm`, `EURUSD`).
- Guruh ID manfiy son: `-100...` formatida.
- Birinchi ishga tushirishda Telegram login kodi **Telegram ilovasiga** keladi (SMS emas).

## Ishga tushirish

```bash
python main.py
```

Logda ko‘rinadi:

- `DRY-RUN` — `TRADING_ENABLED=false`
- `LIVE` — `TRADING_ENABLED=true`

To‘xtatish: `Ctrl+C`

## Deploy (VPS)

### 1. Serverga yuklash

```bash
git clone <repo-url> /opt/tgtrading
cd /opt/tgtrading
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # kalitlarni to‘ldiring
```

Birinchi marta interaktiv login:

```bash
python main.py
# Telegram kodini kiriting — *.session fayl yaratiladi
```

Keyin `*.session` faylni saqlang — qayta login kerak bo‘lmasin.

### 2. systemd service (Linux)

`/etc/systemd/system/tgtrading.service`:

```ini
[Unit]
Description=TgTrading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tgtrading
Environment=PATH=/opt/tgtrading/venv/bin
ExecStart=/opt/tgtrading/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable tgtrading
sudo systemctl start tgtrading
sudo systemctl status tgtrading
journalctl -u tgtrading -f
```

### 3. Git push (lokal)

```bash
git add .
git commit -m "Initial commit"
git remote add origin <repo-url>
git push -u origin main
```

**Gitga qo‘ymang:** `.env`, `*.session`, `venv/` — ular `.gitignore` da.

## Loyiha tuzilmasi

```
main.py                 # Entry point
pipeline/orchestrator.py # Asosiy oqim
telegram/               # Telethon listener
ai/                     # Gemini tahlil + prompt
trading/                # MetaAPI executor
config/                 # Settings
models/                 # Pydantic modellar
```

## AI javob formati

Gemini quyidagi JSON qaytaradi:

```json
{
  "is_signal": true,
  "symbol": "BTCUSDm",
  "side": "buy",
  "orders": [
    {
      "countOrder": 1,
      "type": "entry",
      "price": 64300.0,
      "sl": null,
      "tp": null,
      "orderType": "limit",
      "volume": 0.01
    }
  ],
  "reasoning": "..."
}
```

- `type`: `entry` | `modify` | `close` | `cancel`
- Zone grid: har narx alohida `orders[]` elementi, `countOrder=1`
- SL/TP faqat signalda aytilganda — aks holda `null`

## Xavfsizlik

- `.env` va session fayllarni hech qachon public repoga qo‘ymang
- Avval `TRADING_ENABLED=false` bilan sinab ko‘ring
- Live rejimga o‘tishdan oldin `ALLOWED_SYMBOLS` va volume limitlarini tekshiring

## Muammolar

| Muammo | Yechim |
|---|---|
| Telegram kod kelmaydi | Telegram ilovasini oching, SMS emas |
| `Invalid symbol` | `ALLOWED_SYMBOLS` ni brokerdagi nomga moslang |
| MetaAPI timeout | Internet/VPS, MetaAPI dashboard da account holati |
| Order ochilmadi | Logda `limit reached` — mavjud orderlar limitni to‘ldirgan |
| `Unclosed client session` | Ctrl+C dan keyin bot to‘g‘ri yopiladi (`pipeline.stop()`) |

## Litsenziya

Private / shaxsiy foydalanish.
