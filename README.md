# Currency & Crypto Telegram Bot

Python Telegram bot that fetches live currency/crypto info from CoinMarketCap. Users start the bot, enter a symbol (e.g., `BTC`, `USDT`, `TON`), and receive price, market cap, and daily change. They can immediately ask for another symbol without restarting.

## Prerequisites
- Python 3.10+
- Telegram bot token (via [@BotFather](https://t.me/BotFather))
- Optional: ngrok (for webhook mode)

## Setup
1) Install dependencies:
```bash
pip install -r requirements.txt
```
2) Configure secrets (either set env vars or create `.env` in the `bot/` folder):
```bash
# PowerShell
$env:TELEGRAM_BOT_TOKEN="your-telegram-token-here"
# bash
export TELEGRAM_BOT_TOKEN="your-telegram-token-here"
# or copy .env.example to .env and fill TELEGRAM_BOT_TOKEN
```
3) Run the bot (polling, simplest):
```bash
python main.py
```

### Webhook mode with ngrok
1) Install ngrok and start a tunnel:
```bash
ngrok http http://localhost:8080
```
Note the `https://...ngrok-free.app` forwarding URL.
2) Set env vars (PowerShell shown):
```bash
$env:TELEGRAM_BOT_TOKEN="your-telegram-token-here"
$env:USE_WEBHOOK="true"
$env:WEBHOOK_BASE_URL="https://<your-ngrok-domain>"
# optional overrides:
# $env:WEBHOOK_PATH="/webhook"
# $env:PORT="8080"
```
3) Run:
```bash
python main.py
```

## Usage
- `/start` — Greets, then prompts for a symbol.
- Reply with a symbol (e.g., `BTC`), or type another symbol anytime to get fresh data.
- `/help` — Quick instructions.
- `/automation` — Create an automatic update for a symbol (choose hourly/daily/weekly/monthly).
- `/manageautomation` — List your automations and change cadence or delete them.

## Notes
- Data is scraped from public CoinMarketCap endpoints; no API key required.
- Symbols are matched against the latest CoinMarketCap listings (top 5000 by market cap). If a symbol is ambiguous/missing, the bot will say it wasn't found.
