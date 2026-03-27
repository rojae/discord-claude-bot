"""
/finance command — Korean financial market snapshot.

Shows KOSPI, KOSDAQ indices and USD/KRW exchange rate
using Discord Embed cards with color-coded indicators.
"""

import logging
from datetime import datetime, timezone, timedelta

import discord
import yfinance as yf

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# Yahoo Finance ticker symbols
_TICKERS = {
    "kospi": {"symbol": "^KS11", "label": "코스피 (KOSPI)", "emoji": "🇰🇷"},
    "kosdaq": {"symbol": "^KQ11", "label": "코스닥 (KOSDAQ)", "emoji": "🇰🇷"},
    "usdkrw": {"symbol": "USDKRW=X", "label": "원/달러 환율", "emoji": "💵"},
}


def _arrow(change: float) -> str:
    if change > 0:
        return "▲"
    elif change < 0:
        return "▼"
    return "―"


def _sign(change: float) -> str:
    return "+" if change > 0 else ""


def _fetch_quote(symbol: str) -> dict | None:
    """Fetch latest quote data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = info.last_price
        prev_close = info.previous_close

        if price is None or prev_close is None:
            return None

        change = price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0

        return {
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch {symbol}: {e}")
        return None


def _format_field(meta: dict, quote: dict | None) -> str:
    """Format a single market field value."""
    if quote is None:
        return "데이터를 불러올 수 없습니다"

    price = quote["price"]
    change = quote["change"]
    pct = quote["change_pct"]
    arrow = _arrow(change)

    # Format price: exchange rate to 2 decimals, indices to 2 decimals
    price_str = f"{price:,.2f}"
    change_str = f"{abs(change):,.2f}"
    pct_str = f"{abs(pct):.2f}"

    return f"**{price_str}**\n{arrow} {change_str} ({_sign(change)}{pct_str}%)"


def _overall_color(quotes: list[dict | None]) -> int:
    """Pick embed color based on overall market direction."""
    total_pct = 0
    count = 0
    for q in quotes:
        if q:
            total_pct += q["change_pct"]
            count += 1

    if count == 0:
        return 0x95A5A6  # grey

    avg = total_pct / count
    if avg > 0.3:
        return 0xE74C3C  # red (Korean convention: up = red)
    elif avg < -0.3:
        return 0x3498DB  # blue (Korean convention: down = blue)
    return 0x95A5A6  # grey (flat)


def _market_status_text() -> str:
    """Return market open/closed status."""
    now = datetime.now(KST)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    hour = now.hour
    minute = now.minute
    t = hour * 60 + minute

    if weekday >= 5:
        return "🔴 장 마감 (주말)"

    market_open = 9 * 60       # 09:00
    market_close = 15 * 60 + 30  # 15:30

    if market_open <= t < market_close:
        return "🟢 장 운영 중"
    else:
        return "🔴 장 마감"


class FinanceCommand:
    """/finance — Korean financial market snapshot."""

    async def execute(self, message: discord.Message) -> None:
        # Send a "loading" message first since fetching takes a moment
        loading_msg = await message.reply("📊 시세 조회 중...")

        try:
            quotes = {}
            for key, meta in _TICKERS.items():
                quotes[key] = _fetch_quote(meta["symbol"])

            now = datetime.now(KST)
            status = _market_status_text()
            color = _overall_color(list(quotes.values()))

            embed = discord.Embed(
                title="📊 한국 금융 시장 현황",
                color=color,
            )

            for key, meta in _TICKERS.items():
                embed.add_field(
                    name=f"{meta['emoji']} {meta['label']}",
                    value=_format_field(meta, quotes[key]),
                    inline=True,
                )

            embed.set_footer(text=f"{status}  •  {now.strftime('%Y-%m-%d %H:%M KST')}")

            await loading_msg.edit(content=None, embed=embed)
            logger.info(f"/finance | user={message.author.id}")

        except Exception as e:
            logger.exception(f"/finance failed: {e}")
            await loading_msg.edit(content="❌ 시세 조회에 실패했습니다. 잠시 후 다시 시도해주세요.")
