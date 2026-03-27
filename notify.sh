#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  Send a notification to Discord via webhook
#  Usage: ./notify.sh "message"
# ──────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# Load webhook URL from .env
if [ -f ".env" ]; then
    WEBHOOK_URL=$(grep '^DISCORD_WEBHOOK_URL=' .env | cut -d'=' -f2- | xargs)
fi

if [ -z "$WEBHOOK_URL" ]; then
    exit 0  # No webhook configured, skip silently
fi

MESSAGE="${1:-Bot notification}"

curl -s -o /dev/null -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"$MESSAGE\"}"
