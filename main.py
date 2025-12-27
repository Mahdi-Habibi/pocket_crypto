import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    JobQueue,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

AUTO_SYMBOL, AUTO_PERIOD = range(2)
MENU_AUTOMATION = "Automation"
MENU_MANAGE = "Manage automations"


class CoinMarketCapClient:
    """Lightweight client for public CoinMarketCap endpoints."""

    LISTING_URL = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    DETAIL_URL = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail"

    def __init__(self, listing_limit: int = 5000, cache_seconds: int = 600):
        self.listing_limit = listing_limit
        self.cache_seconds = cache_seconds
        self.session = requests.Session()
        self._symbol_cache: Dict[str, str] = {}
        self._last_refresh = 0.0

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Return CoinMarketCap slug for a given ticker symbol."""
        self._refresh_cache()
        return self._symbol_cache.get(symbol.upper())

    def fetch_quote(self, slug: str) -> Optional[Dict]:
        """Fetch detailed statistics for a specific coin slug."""
        try:
            resp = self.session.get(
                self.DETAIL_URL, params={"slug": slug}, timeout=10
            )
            resp.raise_for_status()
            data = resp.json().get("data")
            if not data:
                return None
            return {
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "slug": slug,
                "stats": data.get("statistics") or {},
            }
        except requests.RequestException as exc:
            logger.exception("Failed fetching detail for %s: %s", slug, exc)
            return None

    def _refresh_cache(self) -> None:
        cache_valid = time.time() - self._last_refresh < self.cache_seconds
        if self._symbol_cache and cache_valid:
            return

        params = {
            "start": 1,
            "limit": self.listing_limit,
            "sortBy": "market_cap",
            "sortType": "desc",
            "convert": "USD",
            "cryptoType": "all",
            "tagType": "all",
            "audited": False,
        }
        try:
            resp = self.session.get(self.LISTING_URL, params=params, timeout=10)
            resp.raise_for_status()
            payload = resp.json().get("data", {})
            listing = payload.get("cryptoCurrencyList", [])
            mapping: Dict[str, str] = {}
            for item in listing:
                symbol = (item.get("symbol") or "").upper()
                slug = item.get("slug")
                if symbol and slug and symbol not in mapping:
                    mapping[symbol] = slug
            self._symbol_cache = mapping
            self._last_refresh = time.time()
            logger.info("Loaded %s symbols from CoinMarketCap", len(mapping))
        except requests.RequestException as exc:
            logger.exception("Failed refreshing symbol cache: %s", exc)


PERIOD_SECONDS = {
    "hourly": 60 * 60,
    "daily": 60 * 60 * 24,
    "weekly": 60 * 60 * 24 * 7,
    "monthly": 60 * 60 * 24 * 30,
}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[MENU_AUTOMATION, MENU_MANAGE]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_user_automations(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Dict:
    store = context.application.bot_data.setdefault("automations", {})
    return store.setdefault(user_id, {"counter": 1, "items": {}})


def schedule_automation(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    slug: str,
    symbol: str,
    period: str,
) -> int:
    automations = get_user_automations(context, user_id)
    automation_id = automations["counter"]
    automations["counter"] += 1

    interval = PERIOD_SECONDS[period]
    job = context.job_queue.run_repeating(
        send_automation_update,
        interval=interval,
        data={"slug": slug, "symbol": symbol, "user_id": user_id, "period": period},
        chat_id=chat_id,
        name=f"auto-{user_id}-{automation_id}",
    )
    automations["items"][automation_id] = {
        "slug": slug,
        "symbol": symbol,
        "period": period,
        "job": job,
    }
    return automation_id


def cancel_automation(context: ContextTypes.DEFAULT_TYPE, user_id: int, automation_id: int) -> bool:
    automations = get_user_automations(context, user_id)
    item = automations["items"].pop(automation_id, None)
    if item:
        item["job"].schedule_removal()
        return True
    return False


async def send_automation_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    slug = data.get("slug")
    symbol = data.get("symbol")
    period = data.get("period")

    client: CoinMarketCapClient = context.application.bot_data["cmc_client"]
    quote = client.fetch_quote(slug) if slug else None
    if not quote or "stats" not in quote or quote["stats"].get("price") is None:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"Automation for {symbol}: unable to fetch data right now.",
        )
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"[{period.title()} automation]\n{format_quote(quote)}",
    )


def format_number(value: Optional[float], prefix: str = "", decimals: int = 2) -> str:
    if value is None:
        return "?"
    try:
        return f"{prefix}{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return "?"


def format_quote(quote: Dict) -> str:
    stats = quote.get("stats", {})
    price = format_number(stats.get("price"), "$", 4 if stats.get("price", 0) < 1 else 2)
    change_24h = stats.get("priceChangePercentage24h")
    market_cap = format_number(stats.get("marketCap"), "$", 0)
    volume = format_number(stats.get("volume24h"), "$", 0)
    rank = stats.get("rank")

    change_str = "?" if change_24h is None else f"{change_24h:+.2f}%"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"{quote.get('name')} ({quote.get('symbol')})",
        f"Price: {price}",
        f"24h Change: {change_str}",
        f"Market Cap: {market_cap}",
        f"24h Volume: {volume}",
    ]
    if rank:
        lines.append(f"Market Cap Rank: #{rank}")
    lines.append(f"Source: CoinMarketCap - {timestamp}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Hi! Send me a crypto or stablecoin symbol (e.g., BTC, USDT, TON) "
        "and I'll fetch the latest info from CoinMarketCap. "
        "You can keep sending symbols to get fresh updates."
    )
    await update.message.reply_text(message, reply_markup=main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Use the menu buttons or commands:\n"
        "- Automation: schedule recurring updates\n"
        "- Manage automations: list or adjust\n"
        "Or send a symbol like BTC/USDT for immediate data.",
        reply_markup=main_menu_keyboard(),
    )


async def automation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Automation setup: send a symbol (e.g., BTC, USDT, TON).", reply_markup=main_menu_keyboard()
    )
    return AUTO_SYMBOL


async def automation_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    symbol = (update.message.text or "").strip().upper()
    if not symbol.isalnum():
        await update.message.reply_text("Please send a valid symbol (letters/numbers only).")
        return AUTO_SYMBOL

    slug = client.resolve_symbol(symbol)
    if not slug:
        await update.message.reply_text(f"Couldn't find {symbol} on CoinMarketCap. Try another ticker?")
        return AUTO_SYMBOL

    context.user_data["auto_symbol"] = symbol
    context.user_data["auto_slug"] = slug

    keyboard = [
        [
            InlineKeyboardButton("Hourly", callback_data="new:hourly"),
            InlineKeyboardButton("Daily", callback_data="new:daily"),
        ],
        [
            InlineKeyboardButton("Weekly", callback_data="new:weekly"),
            InlineKeyboardButton("Monthly", callback_data="new:monthly"),
        ],
    ]
    await update.message.reply_text(
        f"Great, {symbol} found. Choose how often to send updates:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return AUTO_PERIOD


async def automation_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) != 2:
        await query.edit_message_text("Invalid selection. Please restart Automation.")
        return ConversationHandler.END

    period = parts[1]
    symbol = context.user_data.get("auto_symbol")
    slug = context.user_data.get("auto_slug")
    if not symbol or not slug or period not in PERIOD_SECONDS:
        await query.edit_message_text("Missing data. Please restart Automation.")
        return ConversationHandler.END

    automation_id = schedule_automation(
        context=context,
        user_id=query.from_user.id,
        chat_id=query.message.chat_id,
        slug=slug,
        symbol=symbol,
        period=period,
    )
    await query.edit_message_text(
        f"Automation created for {symbol} ({period}). ID: {automation_id}. "
        "Use Manage automations to view or adjust."
    )
    return ConversationHandler.END


def build_manage_keyboard(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    automations = get_user_automations(context, user_id)["items"]
    rows = []
    for automation_id, item in automations.items():
        rows.append(
            [
                InlineKeyboardButton(
                    f"Delete #{automation_id} ({item['symbol']})",
                    callback_data=f"del:{automation_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton("Hourly", callback_data=f"set:{automation_id}:hourly"),
                InlineKeyboardButton("Daily", callback_data=f"set:{automation_id}:daily"),
                InlineKeyboardButton("Weekly", callback_data=f"set:{automation_id}:weekly"),
                InlineKeyboardButton("Monthly", callback_data=f"set:{automation_id}:monthly"),
            ]
        )
    return InlineKeyboardMarkup(rows) if rows else InlineKeyboardMarkup([])


async def manage_automation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    data = get_user_automations(context, user_id)
    items = data["items"]
    if not items:
        await update.message.reply_text(
            "You have no automations. Use Automation in the menu to create one.",
            reply_markup=main_menu_keyboard(),
        )
        return

    lines = ["Your automations:"]
    for automation_id, item in items.items():
        every_hours = PERIOD_SECONDS[item["period"]] // 3600
        lines.append(
            f"- ID {automation_id}: {item['symbol']} ({item['period']}) every {every_hours}h"
        )
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=build_manage_keyboard(user_id, context),
    )


async def manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split(":")
    if not parts or parts[0] not in {"del", "set"}:
        await query.edit_message_text("Invalid action.")
        return

    user_id = query.from_user.id
    automations = get_user_automations(context, user_id)
    items = automations["items"]

    try:
        automation_id = int(parts[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Invalid automation id.")
        return

    if automation_id not in items:
        await query.edit_message_text("Automation not found.")
        return

    if parts[0] == "del":
        cancel_automation(context, user_id, automation_id)
        await query.edit_message_text(f"Deleted automation #{automation_id}.")
        return

    if parts[0] == "set":
        if len(parts) < 3 or parts[2] not in PERIOD_SECONDS:
            await query.edit_message_text("Invalid period selection.")
            return
        period = parts[2]
        item = items[automation_id]
        item["job"].schedule_removal()
        interval = PERIOD_SECONDS[period]
        job = context.job_queue.run_repeating(
            send_automation_update,
            interval=interval,
            data={
                "slug": item["slug"],
                "symbol": item["symbol"],
                "user_id": user_id,
                "period": period,
            },
            chat_id=query.message.chat_id,
            name=f"auto-{user_id}-{automation_id}",
        )
        item["period"] = period
        item["job"] = job
        await query.edit_message_text(f"Updated automation #{automation_id} to {period}.")


async def automation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Automation setup cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def handle_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    text = (update.message.text or "").strip()
    # Ignore menu button texts here; they are handled elsewhere.
    if text in {MENU_AUTOMATION, MENU_MANAGE}:
        return

    symbol = text.upper()
    if not symbol.isalnum():
        await update.message.reply_text("Please send a valid symbol (letters/numbers only).")
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)

    slug = client.resolve_symbol(symbol)
    if not slug:
        await update.message.reply_text(
            f"Couldn't find {symbol} on CoinMarketCap. Try another ticker?"
        )
        return

    quote = client.fetch_quote(slug)
    if not quote or "stats" not in quote or quote["stats"].get("price") is None:
        await update.message.reply_text("I couldn't fetch live data right now. Please try again.")
        return

    await update.message.reply_text(format_quote(quote), reply_markup=main_menu_keyboard())


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=base_dir / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required.")

    use_webhook = os.getenv("USE_WEBHOOK", "").lower() in {"1", "true", "yes"}
    webhook_base = os.getenv("WEBHOOK_BASE_URL")
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
    port = int(os.getenv("PORT", "8080"))

    client = CoinMarketCapClient()
    job_queue = JobQueue()
    application = Application.builder().token(token).job_queue(job_queue).build()
    application.bot_data["cmc_client"] = client

    automation_conv = ConversationHandler(
        entry_points=[
            CommandHandler("automation", automation_start),
            MessageHandler(filters.Regex(f"^{MENU_AUTOMATION}$"), automation_start),
        ],
        states={
            AUTO_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, automation_symbol)],
            AUTO_PERIOD: [CallbackQueryHandler(automation_period_selection, pattern="^new:")],
        },
        fallbacks=[CommandHandler("cancel", automation_cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("manageautomation", manage_automation))
    application.add_handler(MessageHandler(filters.Regex(f"^{MENU_MANAGE}$"), manage_automation))
    application.add_handler(automation_conv)
    application.add_handler(CallbackQueryHandler(manage_callback, pattern="^(del|set):"))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{MENU_AUTOMATION}$|^{MENU_MANAGE}$"),
            handle_symbol,
        )
    )

    logger.info("Bot is starting in %s mode", "webhook" if use_webhook else "polling")

    if use_webhook:
        if not webhook_base:
            raise RuntimeError("WEBHOOK_BASE_URL is required when USE_WEBHOOK is true.")
        webhook_url = f"{webhook_base.rstrip('/')}{webhook_path}"
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path.lstrip("/"),
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )
    else:
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
