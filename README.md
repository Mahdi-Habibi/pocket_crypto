# Pocket Crypto Telegram Bot

Advanced Telegram market bot powered by CoinMarketCap public data. Send a ticker for a rich quote card, or use Discover, Watchlist, Alerts, Compare, and Convert.

## Features
- **Rich quote cards** — price, 1h/24h/7d/30d change, market cap, volume, supply, 24h range, ATH, dominance
- **Inline actions** — Refresh, Watch/Unwatch, Markets, News, Forecast, Alert, CoinMarketCap link
- **Discover** — top gainers, losers, volume leaders, market-cap leaders
- **Watchlist** — pin coins and review them in one view
- **Price alerts** — get notified when a coin crosses above/below a target
- **Compare** — side-by-side snapshot for 2–4 tickers
- **Convert** — `2 BTC` or `/convert 1.5 ETH`
- **Automations** — scheduled quote pushes (hourly/daily/weekly/monthly)
- **Multilingual UI** — English, Español, 中文, فارسی

## Prerequisites
- Python 3.12+
- Telegram bot token (via [@BotFather](https://t.me/BotFather))

## Setup
1) Install dependencies:
```bash
pip install -r requirements.txt
```
2) Configure secrets (copy `.env.example` to `.env` or export env vars):
```bash
export TELEGRAM_BOT_TOKEN="your-telegram-token-here"
export USE_WEBHOOK="true"
export WEBHOOK_BASE_URL="https://cryptoinyourpocketbot.vercel.app"
export WEBHOOK_PATH="/api/webhook"
export PORT="8080"
```
3) Run locally (polling):
```bash
python bot.py
```

## Usage
| Action | Example |
|--------|---------|
| Quote | `BTC` or `/price ETH` |
| Search menu | 🔎 Search |
| Discover | 📈 Discover · `/gainers` `/losers` `/trending` |
| Watchlist | `/watch BTC` · `/watchlist` · `/unwatch BTC` |
| Alerts | `/alert BTC 70000 above` · `/alerts` |
| Compare | `/compare BTC ETH SOL` |
| Convert | `1.5 ETH` or `/convert 2 BTC` |
| Automation | 🤖 Automation · `/manageautomation` |
| Language | ⚙️ Settings |

## Deploy to Vercel (webhook)
The repo includes `api/webhook.py` plus `bot.py`, `cmc.py`, and `i18n.py`.

### Required Vercel environment variables
| Name | Value | Notes |
|------|-------|-------|
| `TELEGRAM_BOT_TOKEN` | *(from BotFather)* | Mark as **Sensitive** |
| `USE_WEBHOOK` | `true` | |
| `WEBHOOK_BASE_URL` | `https://cryptoinyourpocketbot.vercel.app` | Must match production domain |
| `WEBHOOK_PATH` | `/api/webhook` | Optional (default) |

After changing env vars, **redeploy** Production.

### Fix GitHub alert “Telegram Bot Token #1” (+ Vercel rotation)
1. [@BotFather](https://t.me/BotFather) → `/mybots` → **CryptoInYourPocketbot** → **Revoke current token**
2. Update `TELEGRAM_BOT_TOKEN` in Vercel (Sensitive) and redeploy
3. `TELEGRAM_BOT_TOKEN=... WEBHOOK_BASE_URL=https://cryptoinyourpocketbot.vercel.app ./scripts/set_webhook.sh`
4. GitHub → Security → Secret scanning → close the alert as **Revoked**

## Notes
- Data comes from public CoinMarketCap endpoints; no CMC API key required.
- Watchlists, alerts, and automations are in-memory on the serverless instance — they reset on cold starts. The keep-warm workflow reduces that.
- Forecast snippets are scraped from coin-predictions.com when available.
