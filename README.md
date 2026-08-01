# Currency & Crypto Telegram Bot

Python Telegram bot that fetches live currency/crypto info from CoinMarketCap. Users start the bot, enter a symbol (e.g., `BTC`, `USDT`, `TON`), and receive price, market cap, and daily change. They can immediately ask for another symbol without restarting.

## Prerequisites
- Python 3.12+
- Telegram bot token (via [@BotFather](https://t.me/BotFather))

## Setup
1) Install dependencies:
```bash
pip install -r requirements.txt
```
2) Configure secrets (copy `.env.example` to `.env` and fill values, or export env vars):
```bash
export TELEGRAM_BOT_TOKEN="your-telegram-token-here"
export USE_WEBHOOK="true"
export WEBHOOK_BASE_URL="https://cryptoinyourpocketbot.vercel.app"
export WEBHOOK_PATH="/api/webhook"
export PORT="8080"
```
3) Run the bot locally (polling):
```bash
python bot.py
```

## Deploy to Vercel (webhook)
The repo includes `api/webhook.py`, a Vercel Python serverless function.

### Required Vercel environment variables
Set these in the Vercel project **Settings → Environment Variables** for Production:

| Name | Value | Notes |
|------|-------|-------|
| `TELEGRAM_BOT_TOKEN` | *(from BotFather)* | Mark as **Sensitive** |
| `USE_WEBHOOK` | `true` | |
| `WEBHOOK_BASE_URL` | `https://cryptoinyourpocketbot.vercel.app` | Must match the project domain |
| `WEBHOOK_PATH` | `/api/webhook` | Optional (default) |

After changing env vars, **redeploy** Production so the new values are picked up.

### Fix GitHub alert “Telegram Bot Token #1” (+ Vercel rotation)
GitHub secret scanning flagged a bot token that was once committed in `.env` / `.env.example`.
History on `main` has been rewritten to remove it, but **the alert stays open until the token is revoked and you close the alert**.

1. Open [@BotFather](https://t.me/BotFather) → `/mybots` → **CryptoInYourPocketbot** → **API Token** → **Revoke current token**.
2. Copy the new token.
3. In Vercel → Project → Settings → Environment Variables:
   - Edit `TELEGRAM_BOT_TOKEN`, paste the new value
   - Enable **Sensitive**
   - Save for Production (and Preview if used)
4. Redeploy Production.
5. Point Telegram at the webhook:
   ```bash
   export TELEGRAM_BOT_TOKEN="new-token"
   export WEBHOOK_BASE_URL="https://cryptoinyourpocketbot.vercel.app"
   ./scripts/set_webhook.sh
   ```
6. Verify: `curl https://cryptoinyourpocketbot.vercel.app/api/webhook` should return `ok`.
7. In GitHub → **Security** → **Secret scanning** → **Telegram Bot Token #1** → **Close as → Revoked**.
8. Optional: ask [GitHub Support](https://support.github.com) to purge cached views of old commit `0e3f325` / PR #1 refs so orphan SHAs disappear from `raw.githubusercontent.com`.

> Never commit real tokens. Always rotate after any leak.

### Production URL
Webhook endpoint: `https://cryptoinyourpocketbot.vercel.app/api/webhook`

If you use the `pocketcrypto.vercel.app` alias, set `WEBHOOK_BASE_URL` to that domain instead and run `scripts/set_webhook.sh` again.

## Usage
- `/start` — Greets, then prompts for a symbol.
- Reply with a symbol (e.g., `BTC`), or type another symbol anytime to get fresh data.
- `/help` — Quick instructions.
- `/automation` — Create an automatic update for a symbol (choose hourly/daily/weekly/monthly).
- `/manageautomation` — List your automations and change cadence or delete them.

## Notes
- Data is scraped from public CoinMarketCap endpoints; no API key required.
- Symbols are matched against the latest CoinMarketCap listings (top 5000 by market cap).
- Serverless caveat: in-memory automations reset when the function goes cold. An hourly cron/`keep-warm` workflow pings the health endpoint to reduce cold starts.
