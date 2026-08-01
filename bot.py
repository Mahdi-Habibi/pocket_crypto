"""Pocket Crypto — advanced Telegram market bot."""

from __future__ import annotations

import html
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
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

from cmc import CoinMarketCapClient
from i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_OPTIONS,
    TEXTS,
    button_labels,
    get_language_data,
    get_period_label,
    translate,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

AUTO_SYMBOL, AUTO_PERIOD, ALERT_TARGET = range(3)
COMMAND_DELETE_SECONDS = 5
MENU_DELETE_SECONDS = 8
MANUAL_QUOTE_DELETE_SECONDS = 60 * 60 * 24
WATCHLIST_LIMIT = 12
ALERT_LIMIT = 12
ALERT_CHECK_SECONDS = 120

PERIOD_SECONDS = {
    "hourly": 60 * 60,
    "daily": 60 * 60 * 24,
    "weekly": 60 * 60 * 24 * 7,
    "monthly": 60 * 60 * 24 * 30,
}

MENU_KEYS = [
    "menu_search",
    "menu_discover",
    "menu_watchlist",
    "menu_alerts",
    "menu_automation",
    "menu_manage",
    "menu_settings",
]

CONVERT_RE = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d+)?)\s+(?P<symbol>[A-Za-z]{2,15})\s*$"
)


# ---------------------------------------------------------------------------
# Language / menu helpers
# ---------------------------------------------------------------------------


def get_user_language(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    store = context.application.bot_data.setdefault("languages", {})
    return store.get(user_id, DEFAULT_LANGUAGE)


def set_user_language(context: ContextTypes.DEFAULT_TYPE, user_id: int, lang: str) -> str:
    store = context.application.bot_data.setdefault("languages", {})
    selected = lang if lang in TEXTS else DEFAULT_LANGUAGE
    store[user_id] = selected
    return selected


def button_regex(key: str) -> str:
    labels = button_labels(key)
    escaped = [re.escape(label) for label in labels]
    return "^(" + "|".join(escaped) + ")$"


def combined_button_regex(keys) -> str:
    labels = []
    for key in keys:
        labels.extend(button_labels(key))
    escaped = [re.escape(label) for label in labels]
    return "^(" + "|".join(escaped) + ")$"


def is_menu_button_text(text: str) -> bool:
    if not text:
        return False
    labels = set()
    for key in MENU_KEYS:
        labels.update(button_labels(key))
    return text in labels


def main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    data = get_language_data(lang)
    return ReplyKeyboardMarkup(
        [
            [data["menu_search"], data["menu_discover"]],
            [data["menu_watchlist"], data["menu_alerts"]],
            [data["menu_automation"], data["menu_manage"]],
            [data["menu_settings"]],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=False)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_number(value: Optional[float], prefix: str = "", decimals: int = 2) -> str:
    if value is None:
        return "?"
    try:
        abs_val = abs(float(value))
        if abs_val >= 1_000_000_000_000:
            return f"{prefix}{value / 1_000_000_000_000:,.2f}T"
        if abs_val >= 1_000_000_000:
            return f"{prefix}{value / 1_000_000_000:,.2f}B"
        if abs_val >= 1_000_000:
            return f"{prefix}{value / 1_000_000:,.2f}M"
        if abs_val >= 1_000:
            return f"{prefix}{value:,.2f}" if decimals else f"{prefix}{value:,.0f}"
        return f"{prefix}{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return "?"


def format_price(value: Optional[float], prefix: str = "$") -> str:
    if value is None:
        return "?"
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "?"
    try:
        if dec <= 0:
            return f"{prefix}0.00"
        if dec >= 1000:
            return f"{prefix}{dec:,.2f}"
        if dec >= 1:
            return f"{prefix}{dec:,.4f}".rstrip("0").rstrip(".")
        # small prices: keep meaningful digits
        fixed = format(dec, "f")
        if "." in fixed:
            integer, fractional = fixed.split(".", 1)
            # trim trailing zeros but keep up to 8 significant fraction digits
            fractional = fractional[:10].rstrip("0")
            return f"{prefix}{integer}" + (f".{fractional}" if fractional else "")
        return f"{prefix}{fixed}"
    except (TypeError, ValueError, OverflowError, InvalidOperation):
        return "?"


def change_badge(value: Optional[float]) -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    arrow = "▴" if num >= 0 else "▾"
    return f"{arrow} {num:+.2f}%"


def format_quote(quote: Dict, lang: str) -> str:
    stats = quote.get("stats", {}) or {}
    name = esc(quote.get("name") or "?")
    symbol = esc(quote.get("symbol") or "?")
    rank = stats.get("rank")
    price = format_price(stats.get("price"))
    c1h = change_badge(stats.get("priceChangePercentage1h"))
    c24 = change_badge(stats.get("priceChangePercentage24h"))
    c7d = change_badge(stats.get("priceChangePercentage7d"))
    c30 = change_badge(stats.get("priceChangePercentage30d"))
    mcap = format_number(stats.get("marketCap"), "$", 0)
    vol = format_number(stats.get("volume24h"), "$", 0)
    low = format_price(stats.get("low24h"))
    high = format_price(stats.get("high24h"))
    ath = format_price(stats.get("highAllTime"))
    ath_chg = stats.get("highAllTimeChangePercentage")
    circ = format_number(stats.get("circulatingSupply"), "", 0)
    max_supply = stats.get("maxSupply")
    supply = circ if max_supply is None else f"{circ} / {format_number(max_supply, '', 0)}"
    fdv = format_number(stats.get("fullyDilutedMarketCap"), "$", 0)
    dominance = stats.get("marketCapDominance")

    lines = [
        f"🪙 <b>{name}</b> · <code>{symbol}</code>",
    ]
    if rank:
        lines.append(f"#{esc(rank)} · CoinMarketCap")
    lines.extend(
        [
            "",
            f"💰 <b>{esc(price)}</b>",
            (
                f"{translate(lang, 'quote_change_1h')} {esc(c1h)}"
                f"   {translate(lang, 'quote_change_24h')} {esc(c24)}"
            ),
            (
                f"{translate(lang, 'quote_change_7d')} {esc(c7d)}"
                f"   {translate(lang, 'quote_change_30d')} {esc(c30)}"
            ),
            "",
            f"📊 {translate(lang, 'quote_marketcap')}: <b>{esc(mcap)}</b>",
            f"📦 {translate(lang, 'quote_volume')}: <b>{esc(vol)}</b>",
            f"🏦 {translate(lang, 'quote_supply')}: <b>{esc(supply)}</b>",
        ]
    )
    if fdv and fdv != "?":
        lines.append(f"🧮 {translate(lang, 'quote_fdv')}: <b>{esc(fdv)}</b>")
    if dominance is not None:
        try:
            lines.append(
                f"📶 {translate(lang, 'quote_dominance')}: <b>{float(dominance):.2f}%</b>"
            )
        except (TypeError, ValueError):
            pass
    lines.append(f"↕ {translate(lang, 'quote_range')}: <b>{esc(low)}</b> — <b>{esc(high)}</b>")
    if ath and ath != "?":
        ath_line = f"🏆 {translate(lang, 'quote_ath')}: <b>{esc(ath)}</b>"
        if ath_chg is not None:
            ath_line += f" ({esc(change_badge(ath_chg))})"
        lines.append(ath_line)
    return "\n".join(lines)


def format_compact_row(item: Dict) -> str:
    symbol = esc(item.get("symbol") or "?")
    name = esc(item.get("name") or symbol)
    price = esc(format_price(item.get("price")))
    chg = esc(change_badge(item.get("change_24h")))
    return f"• <b>{symbol}</b> {name}\n  {price} · 24h {chg}"


def format_movers(items: List[Dict], lang: str, header_key: str) -> str:
    if not items:
        return translate(lang, "movers_unavailable")
    lines = [translate(lang, header_key), ""]
    for item in items[:10]:
        lines.append(format_compact_row(item))
    return "\n".join(lines)


def format_markets(markets: list, lang: str) -> str:
    if not markets:
        return translate(lang, "markets_unavailable")
    lines = [translate(lang, "markets_header"), ""]
    for idx, item in enumerate(markets, start=1):
        exchange = esc(item.get("exchange") or "?")
        pair = esc(item.get("pair") or "")
        url = item.get("url") or ""
        volume = item.get("volume")
        pair_part = f" · {pair}" if pair else ""
        volume_part = f" · Vol {esc(format_number(volume, '$', 0))}" if volume else ""
        line = f"{idx}. <b>{exchange}</b>{pair_part}{volume_part}"
        if url:
            line += f"\n   {esc(url)}"
        lines.append(line)
    return "\n".join(lines)


def format_news(news_items: list, lang: str) -> str:
    if not news_items:
        return translate(lang, "news_unavailable")
    lines = [translate(lang, "news_header"), ""]
    for idx, item in enumerate(news_items, start=1):
        title = esc(item.get("title") or "Untitled")
        source = esc(item.get("source") or "")
        url = item.get("url") or ""
        line = f"{idx}. <b>{title}</b>"
        if source:
            line += f" <i>({source})</i>"
        if url:
            line += f"\n{esc(url)}"
        lines.append(line)
    return "\n".join(lines)


def format_predictions(prediction_items: list, lang: str) -> str:
    if not prediction_items:
        return translate(lang, "predictions_unavailable")
    lines = [translate(lang, "predictions_header"), ""]
    for idx, item in enumerate(prediction_items, start=1):
        title = esc(item.get("title") or "Untitled")
        source = esc(item.get("source") or "")
        desc = esc(item.get("description") or "")
        line = f"{idx}. <b>{title}</b>"
        if source:
            line += f" <i>({source})</i>"
        if desc:
            line += f"\n{desc}"
        lines.append(line)
    return "\n".join(lines)


def format_compare(quotes: List[Dict], lang: str) -> str:
    lines = [translate(lang, "compare_header"), ""]
    for quote in quotes:
        stats = quote.get("stats") or {}
        lines.append(
            "• <b>{sym}</b> {name}\n  {price} · 24h {chg} · MCap {mcap}".format(
                sym=esc(quote.get("symbol")),
                name=esc(quote.get("name")),
                price=esc(format_price(stats.get("price"))),
                chg=esc(change_badge(stats.get("priceChangePercentage24h"))),
                mcap=esc(format_number(stats.get("marketCap"), "$", 0)),
            )
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def build_quote_actions_keyboard(
    slug: str,
    coin_id: Optional[int],
    symbol: str,
    lang: str,
    watched: bool = False,
) -> InlineKeyboardMarkup:
    news_id = str(coin_id) if coin_id is not None else ""
    watch_label = translate(lang, "button_unwatch" if watched else "button_watch")
    watch_cb = f"unwatch:{symbol}" if watched else f"watch:{symbol}"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(translate(lang, "button_refresh"), callback_data=f"refresh:{slug}"),
                InlineKeyboardButton(watch_label, callback_data=watch_cb),
            ],
            [
                InlineKeyboardButton(translate(lang, "button_markets"), callback_data=f"markets:{slug}"),
                InlineKeyboardButton(translate(lang, "button_news"), callback_data=f"news:{news_id}"),
            ],
            [
                InlineKeyboardButton(
                    translate(lang, "button_predictions"), callback_data=f"predictions:{slug}"
                ),
                InlineKeyboardButton(translate(lang, "button_alert"), callback_data=f"alertui:{symbol}"),
            ],
            [
                InlineKeyboardButton(
                    translate(lang, "button_cmc"),
                    url=f"https://coinmarketcap.com/currencies/{slug}/",
                )
            ],
        ]
    )


def build_suggestion_keyboard(suggestions: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    rows = []
    for item in suggestions:
        symbol = item.get("symbol") or ""
        name = item.get("name") or symbol
        rows.append(
            [
                InlineKeyboardButton(
                    f"{symbol} · {name}"[:64],
                    callback_data=f"quote:{symbol}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def build_discover_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(translate(lang, "button_gainers"), callback_data="discover:gainers"),
                InlineKeyboardButton(translate(lang, "button_losers"), callback_data="discover:losers"),
            ],
            [
                InlineKeyboardButton(
                    translate(lang, "button_trending"), callback_data="discover:trending"
                ),
                InlineKeyboardButton(translate(lang, "button_top"), callback_data="discover:top"),
            ],
            [InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:discover")],
        ]
    )


def build_language_keyboard(current_lang: str) -> InlineKeyboardMarkup:
    rows = []
    for code, meta in LANGUAGE_OPTIONS.items():
        mark = "✓ " if code == current_lang else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{mark}{meta['emoji']} {meta['label']}",
                    callback_data=f"lang:{code}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(translate(current_lang, "cancel_button"), callback_data="cancel:lang")]
    )
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# User stores: watchlist / alerts / automations
# ---------------------------------------------------------------------------


def get_watchlist(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Dict[str, str]:
    store = context.application.bot_data.setdefault("watchlists", {})
    return store.setdefault(user_id, {})


def get_alerts(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Dict:
    store = context.application.bot_data.setdefault("alerts", {})
    return store.setdefault(user_id, {"counter": 1, "items": {}})


def get_user_automations(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Dict:
    store = context.application.bot_data.setdefault("automations", {})
    return store.setdefault(user_id, {"counter": 1, "items": {}})


def schedule_delete_message(
    job_queue: Optional[JobQueue], chat_id: int, message_id: int, delay: int
) -> None:
    if not job_queue:
        return
    job_queue.run_once(
        delete_message_job,
        when=delay,
        data={"chat_id": chat_id, "message_id": message_id},
        name=f"del-{chat_id}-{message_id}",
    )


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    if not chat_id or not message_id:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        logger.debug("delete_message_job failed for %s:%s -> %s", chat_id, message_id, exc)


def maybe_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text and update.message.text.startswith("/"):
        schedule_delete_message(
            context.job_queue,
            update.message.chat_id,
            update.message.message_id,
            COMMAND_DELETE_SECONDS,
        )


# ---------------------------------------------------------------------------
# Core quote flow
# ---------------------------------------------------------------------------


async def send_quote_for_symbol(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    symbol: str,
    *,
    edit_message=None,
) -> None:
    lang = get_user_language(context, update.effective_user.id)
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    symbol = symbol.strip().upper()

    if update.effective_chat:
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action=ChatAction.TYPING
            )
        except Exception:
            pass

    slug = client.resolve_symbol(symbol)
    if not slug:
        suggestions = client.suggest_symbols(symbol)
        text = translate(lang, "symbol_not_found" if suggestions else "symbol_not_found_plain", symbol=esc(symbol))
        markup = build_suggestion_keyboard(suggestions) if suggestions else None
        if edit_message:
            await edit_message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
        else:
            await update.effective_message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
        return

    quote = client.fetch_quote(slug)
    if not quote or "stats" not in quote or quote["stats"].get("price") is None:
        text = translate(lang, "manual_fetch_fail")
        if edit_message:
            await edit_message.edit_text(text, parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    watched = symbol in get_watchlist(context, update.effective_user.id)
    text = format_quote(quote, lang)
    markup = build_quote_actions_keyboard(slug, quote.get("id"), symbol, lang, watched=watched)

    if edit_message:
        await edit_message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        return

    msg = await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True
    )
    if msg:
        schedule_delete_message(
            context.job_queue, msg.chat_id, msg.message_id, MANUAL_QUOTE_DELETE_SECONDS
        )


# ---------------------------------------------------------------------------
# Commands / menus
# ---------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    await update.message.reply_text(
        translate(lang, "start"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(lang),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    await update.message.reply_text(
        translate(
            lang,
            "help",
            discover=translate(lang, "menu_discover"),
            watchlist=translate(lang, "menu_watchlist"),
            alerts=translate(lang, "menu_alerts"),
            automation=translate(lang, "menu_automation"),
            manage=translate(lang, "menu_manage"),
            settings=translate(lang, "menu_settings"),
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(lang),
    )


async def search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message:
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    await update.message.reply_text(
        translate(lang, "search_prompt"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(lang),
    )


async def discover_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message:
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    await update.message.reply_text(
        translate(lang, "discover_prompt"),
        parse_mode=ParseMode.HTML,
        reply_markup=build_discover_keyboard(lang),
    )


async def discover_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    kind = (query.data or "").split(":", 1)[-1]
    client: CoinMarketCapClient = context.bot_data["cmc_client"]

    if kind == "gainers":
        items = client.fetch_movers("percent_change_24h", limit=10)
        text = format_movers(items, lang, "gainers_header")
    elif kind == "losers":
        items = client.fetch_movers("percent_change_24h:asc", limit=10)
        text = format_movers(items, lang, "losers_header")
    elif kind == "trending":
        items = client.fetch_movers("volume_24h", limit=10)
        text = format_movers(items, lang, "trending_header")
    else:
        items = client.get_cached_listing(limit=10)
        if not items:
            items = client.fetch_movers("market_cap", limit=10)
        text = format_movers(items, lang, "top_header")

    # Quick-open buttons for top 5
    rows = []
    for item in items[:5]:
        symbol = item.get("symbol")
        if symbol:
            rows.append(
                [InlineKeyboardButton(f"Open {symbol}", callback_data=f"quote:{symbol}")]
            )
    rows.append(
        [InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:discover")]
    )
    if query.message:
        msg = await query.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        if msg:
            schedule_delete_message(
                context.job_queue, msg.chat_id, msg.message_id, MANUAL_QUOTE_DELETE_SECONDS
            )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    maybe_delete_command(update, context)
    if not context.args:
        await search_menu(update, context)
        return
    await send_quote_for_symbol(update, context, context.args[0])


async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    symbols = [a.strip().upper() for a in (context.args or []) if a.strip()]
    if len(symbols) < 2 or len(symbols) > 4:
        await update.message.reply_text(
            translate(lang, "compare_usage"), parse_mode=ParseMode.HTML
        )
        return

    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    quotes = []
    for symbol in symbols:
        slug = client.resolve_symbol(symbol)
        if not slug:
            continue
        quote = client.fetch_quote(slug)
        if quote and quote.get("stats", {}).get("price") is not None:
            quotes.append(quote)

    if len(quotes) < 2:
        await update.message.reply_text(
            translate(lang, "compare_need_more"), parse_mode=ParseMode.HTML
        )
        return

    await update.message.reply_text(
        format_compare(quotes, lang),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(lang),
    )


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    if len(context.args or []) < 2:
        await update.message.reply_text(
            translate(lang, "convert_usage"), parse_mode=ParseMode.HTML
        )
        return
    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text(
            translate(lang, "convert_usage"), parse_mode=ParseMode.HTML
        )
        return
    symbol = context.args[1].upper()
    await _send_conversion(update, context, amount, symbol)


async def _send_conversion(
    update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float, symbol: str
) -> None:
    lang = get_user_language(context, update.effective_user.id)
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    slug = client.resolve_symbol(symbol)
    if not slug:
        await update.effective_message.reply_text(
            translate(lang, "symbol_not_found_plain", symbol=esc(symbol)),
            parse_mode=ParseMode.HTML,
        )
        return
    quote = client.fetch_quote(slug)
    price = (quote or {}).get("stats", {}).get("price")
    if price is None:
        await update.effective_message.reply_text(
            translate(lang, "manual_fetch_fail"), parse_mode=ParseMode.HTML
        )
        return
    value = amount * float(price)
    await update.effective_message.reply_text(
        translate(
            lang,
            "convert_result",
            amount=esc(amount),
            symbol=esc(symbol),
            value=esc(format_price(value)),
        ),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message:
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    watchlist = get_watchlist(context, update.effective_user.id)
    if not watchlist:
        await update.effective_message.reply_text(
            translate(lang, "watchlist_empty"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(lang),
        )
        return

    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    lines = [translate(lang, "watchlist_header", count=len(watchlist)), ""]
    rows = []
    for symbol, slug in list(watchlist.items())[:WATCHLIST_LIMIT]:
        quote = client.fetch_quote(slug)
        stats = (quote or {}).get("stats") or {}
        lines.append(
            "• <b>{sym}</b> {price} · 24h {chg}".format(
                sym=esc(symbol),
                price=esc(format_price(stats.get("price"))),
                chg=esc(change_badge(stats.get("priceChangePercentage24h"))),
            )
        )
        rows.append([InlineKeyboardButton(f"Open {symbol}", callback_data=f"quote:{symbol}")])

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows) if rows else None,
    )


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    if not context.args:
        await watchlist_command(update, context)
        return
    symbol = context.args[0].upper()
    text = _add_watch(context, update.effective_user.id, symbol, lang)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    if not context.args:
        await watchlist_command(update, context)
        return
    symbol = context.args[0].upper()
    text = _remove_watch(context, update.effective_user.id, symbol, lang)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


def _add_watch(context: ContextTypes.DEFAULT_TYPE, user_id: int, symbol: str, lang: str) -> str:
    client: CoinMarketCapClient = context.application.bot_data["cmc_client"]
    slug = client.resolve_symbol(symbol)
    if not slug:
        return translate(lang, "symbol_not_found_plain", symbol=esc(symbol))
    watchlist = get_watchlist(context, user_id)
    if symbol in watchlist:
        return translate(lang, "watch_exists", symbol=esc(symbol))
    if len(watchlist) >= WATCHLIST_LIMIT:
        return translate(lang, "watch_limit", limit=WATCHLIST_LIMIT)
    watchlist[symbol] = slug
    return translate(lang, "watch_added", symbol=esc(symbol))


def _remove_watch(context: ContextTypes.DEFAULT_TYPE, user_id: int, symbol: str, lang: str) -> str:
    watchlist = get_watchlist(context, user_id)
    if symbol not in watchlist:
        return translate(lang, "watch_missing", symbol=esc(symbol))
    watchlist.pop(symbol, None)
    return translate(lang, "watch_removed", symbol=esc(symbol))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


def _create_alert(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    symbol: str,
    target: float,
    direction: str,
    lang: str,
) -> str:
    client: CoinMarketCapClient = context.application.bot_data["cmc_client"]
    slug = client.resolve_symbol(symbol)
    if not slug:
        return translate(lang, "symbol_not_found_plain", symbol=esc(symbol))
    if direction not in {"above", "below"}:
        return translate(lang, "alert_invalid")

    alerts = get_alerts(context, user_id)
    if len(alerts["items"]) >= ALERT_LIMIT:
        return translate(lang, "alert_limit", limit=ALERT_LIMIT)

    alert_id = alerts["counter"]
    alerts["counter"] += 1
    alerts["items"][alert_id] = {
        "symbol": symbol,
        "slug": slug,
        "target": target,
        "direction": direction,
        "chat_id": chat_id,
    }
    return translate(
        lang,
        "alert_created",
        alert_id=alert_id,
        symbol=esc(symbol),
        direction=translate(lang, f"direction_{direction}"),
        target=esc(format_price(target)),
    )


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message:
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    alerts = get_alerts(context, update.effective_user.id)
    items = alerts["items"]
    if not items:
        await update.effective_message.reply_text(
            translate(lang, "alerts_empty"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(lang),
        )
        return

    lines = [translate(lang, "alerts_header", count=len(items)), ""]
    rows = []
    for alert_id, item in items.items():
        lines.append(
            translate(
                lang,
                "alert_line",
                alert_id=alert_id,
                symbol=esc(item["symbol"]),
                direction=translate(lang, f"direction_{item['direction']}"),
                target=esc(format_price(item["target"])),
            )
        )
        rows.append(
            [
                InlineKeyboardButton(
                    translate(
                        lang,
                        "delete_alert_button",
                        alert_id=alert_id,
                        symbol=item["symbol"],
                    ),
                    callback_data=f"adel:{alert_id}",
                )
            ]
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text(
            translate(lang, "alert_invalid"), parse_mode=ParseMode.HTML
        )
        return
    symbol = args[0].upper()
    try:
        target = float(args[1].replace(",", "").replace("$", ""))
    except ValueError:
        await update.message.reply_text(
            translate(lang, "alert_invalid"), parse_mode=ParseMode.HTML
        )
        return
    direction = args[2].lower()
    if direction in {"up", "over", ">"}:
        direction = "above"
    if direction in {"down", "under", "<"}:
        direction = "below"
    text = _create_alert(
        context, update.effective_user.id, update.effective_chat.id, symbol, target, direction, lang
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def alert_target_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_language(context, update.effective_user.id)
    symbol = context.user_data.get("alert_symbol")
    if not symbol:
        await update.message.reply_text(translate(lang, "alert_invalid"), parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    parts = (update.message.text or "").strip().split()
    if len(parts) < 2:
        await update.message.reply_text(
            translate(lang, "alert_prompt", symbol=esc(symbol)), parse_mode=ParseMode.HTML
        )
        return ALERT_TARGET
    try:
        target = float(parts[0].replace(",", "").replace("$", ""))
    except ValueError:
        await update.message.reply_text(
            translate(lang, "alert_prompt", symbol=esc(symbol)), parse_mode=ParseMode.HTML
        )
        return ALERT_TARGET
    direction = parts[1].lower()
    if direction in {"up", "over", ">"}:
        direction = "above"
    if direction in {"down", "under", "<"}:
        direction = "below"
    text = _create_alert(
        context, update.effective_user.id, update.effective_chat.id, symbol, target, direction, lang
    )
    context.user_data.pop("alert_symbol", None)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def check_price_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    client: CoinMarketCapClient = context.application.bot_data["cmc_client"]
    all_alerts: Dict = context.application.bot_data.get("alerts") or {}
    for user_id, bucket in list(all_alerts.items()):
        lang = get_user_language(context, user_id)
        for alert_id, item in list(bucket.get("items", {}).items()):
            quote = client.fetch_quote(item["slug"])
            price = (quote or {}).get("stats", {}).get("price")
            if price is None:
                continue
            price = float(price)
            target = float(item["target"])
            direction = item["direction"]
            hit = (direction == "above" and price >= target) or (
                direction == "below" and price <= target
            )
            if not hit:
                continue
            bucket["items"].pop(alert_id, None)
            try:
                await context.bot.send_message(
                    chat_id=item["chat_id"],
                    text=translate(
                        lang,
                        "alert_triggered",
                        symbol=esc(item["symbol"]),
                        price=esc(format_price(price)),
                        direction=translate(lang, f"direction_{direction}"),
                        target=esc(format_price(target)),
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_quote_actions_keyboard(
                        item["slug"],
                        (quote or {}).get("id"),
                        item["symbol"],
                        lang,
                        watched=item["symbol"] in get_watchlist(context, user_id),
                    ),
                )
            except Exception as exc:
                logger.warning("Failed sending alert %s: %s", alert_id, exc)


# ---------------------------------------------------------------------------
# Detail callbacks
# ---------------------------------------------------------------------------


async def quote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    symbol = (query.data or "").split(":", 1)[-1]
    await send_quote_for_symbol(update, context, symbol)


async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer(translate(lang, "refreshed"))
    slug = (query.data or "").split(":", 1)[-1]
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    symbol = client.symbol_for_slug(slug) or slug.upper().replace("-", "")
    if query.message:
        await send_quote_for_symbol(update, context, symbol, edit_message=query.message)


async def watch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    action, symbol = (query.data or "watch:").split(":", 1)
    symbol = symbol.upper()
    if action == "watch":
        text = _add_watch(context, query.from_user.id, symbol, lang)
    else:
        text = _remove_watch(context, query.from_user.id, symbol, lang)
    await query.answer(re.sub("<[^>]+>", "", text)[:180])
    # Refresh keyboard state on the quote message if possible
    if query.message and query.message.reply_markup:
        client: CoinMarketCapClient = context.bot_data["cmc_client"]
        slug = client.resolve_symbol(symbol) or ""
        quote = client.fetch_quote(slug) if slug else None
        if quote:
            watched = symbol in get_watchlist(context, query.from_user.id)
            await query.message.edit_reply_markup(
                reply_markup=build_quote_actions_keyboard(
                    slug, quote.get("id"), symbol, lang, watched=watched
                )
            )


async def alert_ui_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    symbol = (query.data or "").split(":", 1)[-1].upper()
    context.user_data["alert_symbol"] = symbol
    await query.answer()
    if query.message:
        await query.message.reply_text(
            translate(lang, "alert_prompt", symbol=esc(symbol)),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:alert")]]
            ),
        )
    return ALERT_TARGET


async def delete_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    try:
        alert_id = int((query.data or "").split(":")[-1])
    except ValueError:
        return
    alerts = get_alerts(context, query.from_user.id)
    if alerts["items"].pop(alert_id, None) is None:
        await query.message.reply_text(translate(lang, "alert_missing"), parse_mode=ParseMode.HTML)
        return
    await query.message.reply_text(
        translate(lang, "alert_deleted", alert_id=alert_id), parse_mode=ParseMode.HTML
    )


async def markets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    slug = (query.data or "").split(":", 1)[-1] or None
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    markets = client.fetch_markets(slug) if slug else []
    if query.message:
        msg = await query.message.reply_text(
            format_markets(markets, lang),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        if msg:
            schedule_delete_message(
                context.job_queue, msg.chat_id, msg.message_id, MANUAL_QUOTE_DELETE_SECONDS
            )


async def news_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    coin_id = None
    parts = (query.data or "").split(":", 1)
    if len(parts) == 2 and parts[1]:
        try:
            coin_id = int(parts[1])
        except ValueError:
            coin_id = None
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    text = format_news(client.fetch_news(coin_id), lang)
    if query.message:
        msg = await query.message.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        if msg:
            schedule_delete_message(
                context.job_queue, msg.chat_id, msg.message_id, MANUAL_QUOTE_DELETE_SECONDS
            )


async def predictions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    slug = (query.data or "").split(":", 1)[-1] or None
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    text = format_predictions(client.fetch_predictions(slug), lang)
    if query.message:
        msg = await query.message.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        if msg:
            schedule_delete_message(
                context.job_queue, msg.chat_id, msg.message_id, MANUAL_QUOTE_DELETE_SECONDS
            )


# ---------------------------------------------------------------------------
# Automation (preserved + polished)
# ---------------------------------------------------------------------------


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
    user_id = data.get("user_id")
    lang = get_user_language(context, user_id) if user_id else DEFAULT_LANGUAGE
    period_label = get_period_label(lang, period) if period else period
    client: CoinMarketCapClient = context.application.bot_data["cmc_client"]
    quote = client.fetch_quote(slug) if slug else None
    if not quote or "stats" not in quote or quote["stats"].get("price") is None:
        msg = await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=translate(lang, "fetch_unavailable", symbol=esc(symbol)),
            parse_mode=ParseMode.HTML,
        )
        if msg:
            schedule_delete_message(
                context.job_queue, msg.chat_id, msg.message_id, PERIOD_SECONDS.get(period, 3600)
            )
        return

    watched = False
    if user_id:
        watched = symbol in get_watchlist(context, user_id)
    msg = await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"{translate(lang, 'automation_prefix', period=esc(period_label))}\n{format_quote(quote, lang)}",
        parse_mode=ParseMode.HTML,
        reply_markup=build_quote_actions_keyboard(
            slug or "", quote.get("id"), symbol or "", lang, watched=watched
        ),
        disable_web_page_preview=True,
    )
    if msg:
        schedule_delete_message(
            context.job_queue, msg.chat_id, msg.message_id, PERIOD_SECONDS.get(period, 3600)
        )


async def automation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_language(context, update.effective_user.id)
    if update.message and update.message.text:
        if update.message.text.startswith("/") or is_menu_button_text(update.message.text):
            schedule_delete_message(
                context.job_queue,
                update.message.chat_id,
                update.message.message_id,
                COMMAND_DELETE_SECONDS,
            )
    await update.message.reply_text(
        translate(lang, "automation_prompt"),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:auto")]]
        ),
    )
    return AUTO_SYMBOL


async def automation_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    lang = get_user_language(context, update.effective_user.id)
    symbol = (update.message.text or "").strip().upper()
    if not symbol.isalnum():
        await update.message.reply_text(
            translate(lang, "invalid_symbol"), parse_mode=ParseMode.HTML
        )
        return AUTO_SYMBOL

    slug = client.resolve_symbol(symbol)
    if not slug:
        await update.message.reply_text(
            translate(lang, "symbol_not_found_plain", symbol=esc(symbol)),
            parse_mode=ParseMode.HTML,
        )
        return AUTO_SYMBOL

    context.user_data["auto_symbol"] = symbol
    context.user_data["auto_slug"] = slug
    keyboard = [
        [
            InlineKeyboardButton(
                f"⏱️ {get_period_label(lang, 'hourly')}", callback_data="new:hourly"
            ),
            InlineKeyboardButton(f"☀️ {get_period_label(lang, 'daily')}", callback_data="new:daily"),
        ],
        [
            InlineKeyboardButton(
                f"📅 {get_period_label(lang, 'weekly')}", callback_data="new:weekly"
            ),
            InlineKeyboardButton(
                f"🗓️ {get_period_label(lang, 'monthly')}", callback_data="new:monthly"
            ),
        ],
        [InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:auto")],
    ]
    await update.message.reply_text(
        translate(lang, "choose_frequency", symbol=esc(symbol)),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return AUTO_PERIOD


async def automation_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    period = (query.data or "").split(":", 1)[-1]
    if period not in PERIOD_SECONDS:
        await query.edit_message_text(
            translate(lang, "invalid_period"), parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    symbol = context.user_data.get("auto_symbol")
    slug = context.user_data.get("auto_slug")
    if not symbol or not slug:
        await query.edit_message_text(
            translate(lang, "missing_data"), parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    automation_id = schedule_automation(
        context, query.from_user.id, query.message.chat_id, slug, symbol, period
    )
    await query.edit_message_text(
        translate(
            lang,
            "automation_created",
            symbol=esc(symbol),
            period=get_period_label(lang, period),
            automation_id=automation_id,
            manage_label=translate(lang, "menu_manage"),
        ),
        parse_mode=ParseMode.HTML,
    )
    context.user_data.pop("auto_symbol", None)
    context.user_data.pop("auto_slug", None)
    return ConversationHandler.END


def build_manage_keyboard(
    user_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str
) -> InlineKeyboardMarkup:
    automations = get_user_automations(context, user_id)
    rows = []
    for automation_id, item in automations["items"].items():
        rows.append(
            [
                InlineKeyboardButton(
                    translate(
                        lang,
                        "delete_button",
                        automation_id=automation_id,
                        symbol=item["symbol"],
                    ),
                    callback_data=f"del:{automation_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton("1h", callback_data=f"set:{automation_id}:hourly"),
                InlineKeyboardButton("1d", callback_data=f"set:{automation_id}:daily"),
                InlineKeyboardButton("1w", callback_data=f"set:{automation_id}:weekly"),
                InlineKeyboardButton("1m", callback_data=f"set:{automation_id}:monthly"),
            ]
        )
    rows.append(
        [InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:manage")]
    )
    return InlineKeyboardMarkup(rows)


async def manage_automation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message:
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    automations = get_user_automations(context, update.effective_user.id)
    if not automations["items"]:
        await update.message.reply_text(
            translate(
                lang,
                "no_automations",
                automation_label=translate(lang, "menu_automation"),
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(lang),
        )
        return

    lines = [translate(lang, "automation_list_header")]
    for automation_id, item in automations["items"].items():
        hours = max(1, PERIOD_SECONDS[item["period"]] // 3600)
        lines.append(
            translate(
                lang,
                "automation_line",
                automation_id=automation_id,
                symbol=esc(item["symbol"]),
                period=get_period_label(lang, item["period"]),
                every_hours=hours,
            )
        )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=build_manage_keyboard(update.effective_user.id, context, lang),
    )


async def manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) < 2:
        return
    action = parts[0]
    try:
        automation_id = int(parts[1])
    except ValueError:
        await query.message.reply_text(translate(lang, "invalid_id"), parse_mode=ParseMode.HTML)
        return

    if action == "del":
        ok = cancel_automation(context, query.from_user.id, automation_id)
        text = (
            translate(lang, "deleted_automation", automation_id=automation_id)
            if ok
            else translate(lang, "automation_missing")
        )
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if action == "set" and len(parts) == 3:
        period = parts[2]
        if period not in PERIOD_SECONDS:
            await query.message.reply_text(
                translate(lang, "invalid_period"), parse_mode=ParseMode.HTML
            )
            return
        automations = get_user_automations(context, query.from_user.id)
        item = automations["items"].get(automation_id)
        if not item:
            await query.message.reply_text(
                translate(lang, "automation_missing"), parse_mode=ParseMode.HTML
            )
            return
        cancel_automation(context, query.from_user.id, automation_id)
        # Preserve id by manually reinserting with same id
        new_id = schedule_automation(
            context,
            query.from_user.id,
            query.message.chat_id,
            item["slug"],
            item["symbol"],
            period,
        )
        # Move to original id for stable references
        created = automations["items"].pop(new_id)
        automations["items"][automation_id] = created
        automations["counter"] = max(automations["counter"], automation_id + 1)
        await query.message.reply_text(
            translate(
                lang,
                "updated_period",
                automation_id=automation_id,
                period=get_period_label(lang, period),
            ),
            parse_mode=ParseMode.HTML,
        )


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message:
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    await update.message.reply_text(
        translate(lang, "language_prompt"),
        parse_mode=ParseMode.HTML,
        reply_markup=build_language_keyboard(lang),
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":", 1)
    if len(parts) != 2 or parts[1] not in LANGUAGE_OPTIONS:
        await query.edit_message_text(
            translate(DEFAULT_LANGUAGE, "invalid_language"), parse_mode=ParseMode.HTML
        )
        return
    lang = set_user_language(context, query.from_user.id, parts[1])
    meta = LANGUAGE_OPTIONS[lang]
    await query.edit_message_text(
        translate(
            lang,
            "language_updated",
            language=f"{meta['emoji']} {meta['label']}",
        ),
        parse_mode=ParseMode.HTML,
    )
    if query.message:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=translate(lang, "start"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(lang),
        )


async def cancel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    context.user_data.pop("alert_symbol", None)
    context.user_data.pop("auto_symbol", None)
    context.user_data.pop("auto_slug", None)
    if query.message:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id, message_id=query.message.message_id
            )
        except Exception:
            pass
        ack = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=translate(lang, "cancelled"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(lang),
        )
        if ack:
            schedule_delete_message(
                context.job_queue, ack.chat_id, ack.message_id, MENU_DELETE_SECONDS
            )
    return ConversationHandler.END


async def automation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_language(context, update.effective_user.id)
    maybe_delete_command(update, context)
    await update.message.reply_text(
        translate(lang, "automation_cancelled"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(lang),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Free-text router
# ---------------------------------------------------------------------------


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text or is_menu_button_text(text):
        return
    if text.startswith("/"):
        maybe_delete_command(update, context)
        return

    # Converter shorthand: "1.5 ETH"
    match = CONVERT_RE.match(text)
    if match:
        await _send_conversion(
            update, context, float(match.group("amount")), match.group("symbol").upper()
        )
        return

    # Symbol or name search
    token = text.split()[0]
    clean = re.sub(r"[^A-Za-z0-9]", "", token)
    if not clean:
        lang = get_user_language(context, update.effective_user.id)
        await update.message.reply_text(
            translate(lang, "invalid_symbol"), parse_mode=ParseMode.HTML
        )
        return
    await send_quote_for_symbol(update, context, clean)


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------


def build_application(token: str) -> Application:
    client = CoinMarketCapClient()
    job_queue = JobQueue()
    application = Application.builder().token(token).job_queue(job_queue).build()
    application.bot_data["cmc_client"] = client

    automation_pattern = button_regex("menu_automation")
    manage_pattern = button_regex("menu_manage")
    settings_pattern = button_regex("menu_settings")
    search_pattern = button_regex("menu_search")
    discover_pattern = button_regex("menu_discover")
    watchlist_pattern = button_regex("menu_watchlist")
    alerts_pattern = button_regex("menu_alerts")
    menu_pattern = combined_button_regex(MENU_KEYS)

    automation_conv = ConversationHandler(
        entry_points=[
            CommandHandler("automation", automation_start),
            MessageHandler(filters.Regex(automation_pattern), automation_start),
        ],
        states={
            AUTO_SYMBOL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, automation_symbol),
                CallbackQueryHandler(cancel_menu, pattern="^cancel:"),
            ],
            AUTO_PERIOD: [
                CallbackQueryHandler(automation_period_selection, pattern="^new:"),
                CallbackQueryHandler(cancel_menu, pattern="^cancel:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", automation_cancel)],
        allow_reentry=True,
        per_message=False,
    )

    alert_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(alert_ui_callback, pattern="^alertui:")],
        states={
            ALERT_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_target_message),
                CallbackQueryHandler(cancel_menu, pattern="^cancel:"),
            ]
        },
        fallbacks=[CommandHandler("cancel", automation_cancel)],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("p", price_command))
    application.add_handler(CommandHandler("compare", compare_command))
    application.add_handler(CommandHandler("convert", convert_command))
    application.add_handler(CommandHandler("watchlist", watchlist_command))
    application.add_handler(CommandHandler("watch", watch_command))
    application.add_handler(CommandHandler("unwatch", unwatch_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("alert", alert_command))
    application.add_handler(CommandHandler("settings", settings_menu))
    application.add_handler(CommandHandler("manageautomation", manage_automation))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("gainers", gainers_command))
    application.add_handler(CommandHandler("losers", losers_command))

    application.add_handler(MessageHandler(filters.Regex(search_pattern), search_menu))
    application.add_handler(MessageHandler(filters.Regex(discover_pattern), discover_menu))
    application.add_handler(MessageHandler(filters.Regex(watchlist_pattern), watchlist_command))
    application.add_handler(MessageHandler(filters.Regex(alerts_pattern), alerts_command))
    application.add_handler(MessageHandler(filters.Regex(settings_pattern), settings_menu))
    application.add_handler(MessageHandler(filters.Regex(manage_pattern), manage_automation))

    application.add_handler(automation_conv)
    application.add_handler(alert_conv)

    application.add_handler(CallbackQueryHandler(discover_callback, pattern="^discover:"))
    application.add_handler(CallbackQueryHandler(quote_callback, pattern="^quote:"))
    application.add_handler(CallbackQueryHandler(refresh_callback, pattern="^refresh:"))
    application.add_handler(CallbackQueryHandler(watch_callback, pattern="^(watch|unwatch):"))
    application.add_handler(CallbackQueryHandler(delete_alert_callback, pattern="^adel:"))
    application.add_handler(CallbackQueryHandler(markets_callback, pattern="^markets:"))
    application.add_handler(CallbackQueryHandler(news_callback, pattern="^news:"))
    application.add_handler(CallbackQueryHandler(predictions_callback, pattern="^predictions:"))
    application.add_handler(CallbackQueryHandler(manage_callback, pattern="^(del|set):"))
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang:"))
    application.add_handler(CallbackQueryHandler(cancel_menu, pattern="^cancel:"))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern), handle_text)
    )

    # Periodic alert checker (works while the process is warm)
    if application.job_queue:
        application.job_queue.run_repeating(
            check_price_alerts,
            interval=ALERT_CHECK_SECONDS,
            first=30,
            name="price-alert-checker",
        )

    return application


async def _discover_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    """Shared formatter for /gainers /losers /trending."""
    maybe_delete_command(update, context)
    lang = get_user_language(context, update.effective_user.id)
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    if kind == "gainers":
        items = client.fetch_movers("percent_change_24h", limit=10)
        text = format_movers(items, lang, "gainers_header")
    elif kind == "losers":
        items = client.fetch_movers("percent_change_24h:asc", limit=10)
        text = format_movers(items, lang, "losers_header")
    else:
        items = client.fetch_movers("volume_24h", limit=10)
        text = format_movers(items, lang, "trending_header")
    rows = [
        [InlineKeyboardButton(f"Open {item.get('symbol')}", callback_data=f"quote:{item.get('symbol')}")]
        for item in items[:5]
        if item.get("symbol")
    ]
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows) if rows else None,
    )


async def gainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _discover_cmd(update, context, "gainers")


async def losers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _discover_cmd(update, context, "losers")


async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _discover_cmd(update, context, "trending")


def load_settings() -> Dict[str, object]:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=base_dir / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required.")

    use_webhook = os.getenv("USE_WEBHOOK", "").lower() in {"1", "true", "yes"}
    webhook_base = os.getenv("WEBHOOK_BASE_URL")
    webhook_path = os.getenv("WEBHOOK_PATH", "/api/webhook")
    port = int(os.getenv("PORT", "8080"))
    return {
        "token": token,
        "use_webhook": use_webhook,
        "webhook_base": webhook_base,
        "webhook_path": webhook_path,
        "port": port,
    }


def main() -> None:
    settings = load_settings()
    token = settings["token"]
    use_webhook = settings["use_webhook"]
    webhook_base = settings["webhook_base"]
    webhook_path = settings["webhook_path"]
    port = settings["port"]

    application = build_application(token)
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
