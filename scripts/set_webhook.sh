#!/usr/bin/env bash
# Point Telegram at the Vercel webhook.
# Usage:
#   TELEGRAM_BOT_TOKEN=... WEBHOOK_BASE_URL=https://cryptoinyourpocketbot.vercel.app ./scripts/set_webhook.sh
set -euo pipefail

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
WEBHOOK_BASE_URL="${WEBHOOK_BASE_URL:-https://cryptoinyourpocketbot.vercel.app}"
WEBHOOK_PATH="${WEBHOOK_PATH:-/api/webhook}"
WEBHOOK_URL="${WEBHOOK_BASE_URL%/}${WEBHOOK_PATH}"

echo "Setting webhook to ${WEBHOOK_URL}"
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${WEBHOOK_URL}" \
  -d "drop_pending_updates=false" | tee /tmp/set_webhook.json
echo
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | tee /tmp/webhook_info.json
echo
