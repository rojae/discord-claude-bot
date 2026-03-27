#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  discord-claude-bot  —  Status check
# ──────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"

PIDFILE="bot.pid"
LOG="bot.log"

# ── Colors (disable if not TTY) ──────────────────────────────
if [ -t 1 ]; then
    BOLD='\033[1m' DIM='\033[2m' CYAN='\033[36m'
    GREEN='\033[32m' YELLOW='\033[33m' RED='\033[31m' RESET='\033[0m'
else
    BOLD='' DIM='' CYAN='' GREEN='' YELLOW='' RED='' RESET=''
fi

info()    { echo -e "  ${CYAN}›${RESET} $1"; }
success() { echo -e "  ${GREEN}✔${RESET} $1"; }
warn()    { echo -e "  ${YELLOW}▲${RESET} $1"; }

# ── Check status ─────────────────────────────────────────────
echo -e "${BOLD}  discord-claude-bot status${RESET}"
echo ""

PID=""
SOURCE=""

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        SOURCE="pidfile"
    else
        rm -f "$PIDFILE"
        warn "Stale PID file removed"
        PID=""
    fi
fi

# Fallback: search for process without PID file
if [ -z "$PID" ]; then
    PID=$(pgrep -f "python main.py" | head -1 || true)
    if [ -n "$PID" ]; then
        SOURCE="pgrep"
    fi
fi

if [ -n "$PID" ]; then
    success "Bot is ${GREEN}running${RESET} (PID: ${PID})"
    if [ "$SOURCE" = "pgrep" ]; then
        warn "No PID file — bot may have been started manually"
    fi

    # Process details
    UPTIME=$(ps -o etime= -p "$PID" 2>/dev/null | xargs || echo "unknown")
    MEMORY=$(ps -o rss= -p "$PID" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "unknown")
    CPU=$(ps -o %cpu= -p "$PID" 2>/dev/null | xargs || echo "unknown")

    echo ""
    echo -e "  ${DIM}┌──────────────────────────────────────┐${RESET}"
    echo -e "  ${DIM}│${RESET}  Uptime:  ${BOLD}${UPTIME}${RESET}$(printf '%*s' $((25 - ${#UPTIME})) '')${DIM}│${RESET}"
    echo -e "  ${DIM}│${RESET}  Memory:  ${BOLD}${MEMORY}${RESET}$(printf '%*s' $((25 - ${#MEMORY})) '')${DIM}│${RESET}"
    echo -e "  ${DIM}│${RESET}  CPU:     ${BOLD}${CPU}%%${RESET}$(printf '%*s' $((24 - ${#CPU})) '')${DIM}│${RESET}"
    echo -e "  ${DIM}└──────────────────────────────────────┘${RESET}"

    # Recent log
    if [ -f "$LOG" ]; then
        echo ""
        info "Recent log:"
        echo -e "  ${DIM}─────────────────────────────────────${RESET}"
        tail -5 "$LOG" 2>/dev/null | while IFS= read -r line; do
            echo -e "  ${DIM}  ${line}${RESET}"
        done
    fi
else
    echo -e "  ${RED}✖${RESET} Bot is ${RED}not running${RESET}"

    # Show last log entry for context
    if [ -f "$LOG" ]; then
        LAST_LINE=$(tail -1 "$LOG" 2>/dev/null || true)
        if [ -n "$LAST_LINE" ]; then
            echo ""
            info "Last log entry:"
            echo -e "    ${DIM}${LAST_LINE}${RESET}"
        fi
    fi

    echo ""
    info "Start with: ${CYAN}./run.sh${RESET}"
fi

echo ""
