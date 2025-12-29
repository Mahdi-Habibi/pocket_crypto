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
$env:USE_WEBHOOK="true"
$env:WEBHOOK_BASE_URL="https://<your-ngrok-or-vercel-domain>"
$env:WEBHOOK_PATH="/api/webhook" # default for Vercel
$env:PORT="8080"
# bash
export TELEGRAM_BOT_TOKEN="your-telegram-token-here"
export USE_WEBHOOK="true"
export WEBHOOK_BASE_URL="https://<your-ngrok-or-vercel-domain>"
export WEBHOOK_PATH="/api/webhook"
export PORT="8080"
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
$env:WEBHOOK_PATH="/webhook" # optional; defaults to /api/webhook
$env:PORT="8080"
```
3) Run:
```bash
python main.py
```

## Deploy to Vercel (webhook)
The repo includes `api/webhook.py`, a Vercel-compatible Python function.

1) Set env vars in Vercel:
   - `TELEGRAM_BOT_TOKEN`
   - `USE_WEBHOOK` = `true`
   - `WEBHOOK_BASE_URL` = `https://<your-project>.vercel.app`
   - `WEBHOOK_PATH` = `/api/webhook` (optional; this is the default)
2) Deploy to Vercel; the webhook will be available at `https://<your-project>.vercel.app/api/webhook`.
3) If Telegram does not receive updates automatically, set the webhook once:
   ```bash
   curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d "url=https://<your-project>.vercel.app/api/webhook"
   ```

> Serverless caveat: Vercel functions can sleep between requests. Automations and scheduled jobs need the function to stay warm (Vercel Pro “Always On” helps).

## Usage
- `/start` — Greets, then prompts for a symbol.
- Reply with a symbol (e.g., `BTC`), or type another symbol anytime to get fresh data.
- `/help` — Quick instructions.
- `/automation` — Create an automatic update for a symbol (choose hourly/daily/weekly/monthly).
- `/manageautomation` — List your automations and change cadence or delete them.

## Notes
- Data is scraped from public CoinMarketCap endpoints; no API key required.
- Symbols are matched against the latest CoinMarketCap listings (top 5000 by market cap). If a symbol is ambiguous/missing, the bot will say it wasn't found.
