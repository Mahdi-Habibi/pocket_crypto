import logging
import math
from decimal import Decimal, InvalidOperation
import os
import re
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
DEFAULT_LANGUAGE = "en"
COMMAND_DELETE_SECONDS = 5
MENU_DELETE_SECONDS = 5
MANUAL_QUOTE_DELETE_SECONDS = 60 * 60 * 24

LANGUAGE_OPTIONS = {
    "en": {"label": "English", "emoji": "🇺🇸"},
    "es": {"label": "Español", "emoji": "🇪🇸"},
    "zh": {"label": "中文", "emoji": "🇨🇳"},
    "fa": {"label": "فارسی", "emoji": "🇮🇷"},
}

TEXTS = {
    "en": {
        "menu_automation": "🤖 Automation",
        "menu_manage": "🗂️ Manage automations",
        "menu_settings": "⚙️ Settings",
        "start": (
            "Hi! Send me a crypto or stablecoin symbol (e.g., BTC, USDT, TON) "
            "and I'll fetch the latest info from CoinMarketCap. "
            "You can keep sending symbols to get fresh updates."
        ),
        "help": (
            "Use the menu buttons or commands:\n"
            "- {automation}\n"
            "- {manage}\n"
            "- {settings}\n"
            "Or send a symbol like BTC/USDT for immediate data."
        ),
        "automation_prompt": "Automation setup: send a symbol (e.g., BTC, USDT, TON).",
        "invalid_symbol": "Please send a valid symbol (letters/numbers only).",
        "symbol_not_found": "Couldn't find {symbol} on CoinMarketCap. Try another ticker?",
        "choose_frequency": "Great, {symbol} found. Choose how often to send updates:",
        "invalid_selection": "Invalid selection. Please restart Automation.",
        "missing_data": "Missing data. Please restart Automation.",
        "automation_created": (
            "Automation created for {symbol} ({period}). ID: {automation_id}. "
            "Use {manage_label} to view or adjust."
        ),
        "automation_prefix": "[{period} automation]",
        "no_automations": "You have no automations. Use {automation_label} to create one.",
        "automation_list_header": "Your automations:",
        "automation_line": "- ID {automation_id}: {symbol} ({period}) every {every_hours}h",
        "delete_button": "Delete #{automation_id} ({symbol})",
        "invalid_action": "Invalid action.",
        "invalid_id": "Invalid automation id.",
        "automation_missing": "Automation not found.",
        "deleted_automation": "Deleted automation #{automation_id}.",
        "invalid_period": "Invalid period selection.",
        "updated_period": "Updated automation #{automation_id} to {period}.",
        "automation_cancelled": "Automation setup cancelled.",
        "fetch_unavailable": "Automation for {symbol}: unable to fetch data right now.",
        "manual_fetch_fail": "I couldn't fetch live data right now. Please try again.",
        "invalid_language": "Invalid language selection.",
        "cancel_button": "❌ Cancel",
        "cancelled": "Cancelled.",
        "language_prompt": "Choose your language:",
        "language_updated": "Language changed to {language}.",
        "quote_price": "Price",
        "quote_change": "24h Change",
        "quote_marketcap": "Market Cap",
        "quote_volume": "24h Volume",
        "quote_rank": "Market Cap Rank",
        "quote_source": "Source",
        "periods": {
            "hourly": "Hourly",
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
        },
    },
    "es": {
        "menu_automation": "🤖 Automatización",
        "menu_manage": "🗂️ Gestionar automatizaciones",
        "menu_settings": "⚙️ Ajustes",
        "start": (
            "¡Hola! Envíame un símbolo de cripto o stablecoin (ej. BTC, USDT, TON) "
            "y obtendré la información de CoinMarketCap. "
            "Puedes seguir enviando símbolos para obtener nuevas actualizaciones."
        ),
        "help": (
            "Usa los botones del menú o comandos:\n"
            "- {automation}\n"
            "- {manage}\n"
            "- {settings}\n"
            "O envía un símbolo como BTC/USDT para datos inmediatos."
        ),
        "automation_prompt": "Configurar automatización: envía un símbolo (ej. BTC, USDT, TON).",
        "invalid_symbol": "Envía un símbolo válido (solo letras/números).",
        "symbol_not_found": "No encontré {symbol} en CoinMarketCap. ¿Pruebas otro ticker?",
        "choose_frequency": "Listo, {symbol} encontrado. Elige cada cuánto enviar actualizaciones:",
        "invalid_selection": "Selección inválida. Reinicia Automatización.",
        "missing_data": "Faltan datos. Reinicia Automatización.",
        "automation_created": (
            "Automatización creada para {symbol} ({period}). ID: {automation_id}. "
            "Usa {manage_label} para ver o ajustar."
        ),
        "automation_prefix": "[Automatización {period}]",
        "no_automations": "No tienes automatizaciones. Usa {automation_label} para crear una.",
        "automation_list_header": "Tus automatizaciones:",
        "automation_line": "- ID {automation_id}: {symbol} ({period}) cada {every_hours}h",
        "delete_button": "Eliminar #{automation_id} ({symbol})",
        "invalid_action": "Acción inválida.",
        "invalid_id": "ID de automatización inválido.",
        "automation_missing": "Automatización no encontrada.",
        "deleted_automation": "Automatización #{automation_id} eliminada.",
        "invalid_period": "Selección de periodo inválida.",
        "updated_period": "Automatización #{automation_id} actualizada a {period}.",
        "automation_cancelled": "Configuración cancelada.",
        "fetch_unavailable": "Automatización de {symbol}: no puedo obtener datos ahora.",
        "manual_fetch_fail": "No pude obtener datos en vivo ahora. Inténtalo de nuevo.",
        "invalid_language": "Selección de idioma inválida.",
        "cancel_button": "❌ Cancelar",
        "cancelled": "Cancelado.",
        "language_prompt": "Elige tu idioma:",
        "language_updated": "Idioma cambiado a {language}.",
        "quote_price": "Precio",
        "quote_change": "Cambio 24h",
        "quote_marketcap": "Capitalización",
        "quote_volume": "Volumen 24h",
        "quote_rank": "Rango de capitalización",
        "quote_source": "Fuente",
        "periods": {
            "hourly": "Cada hora",
            "daily": "Diario",
            "weekly": "Semanal",
            "monthly": "Mensual",
        },
    },
    "zh": {
        "menu_automation": "🤖 自动更新",
        "menu_manage": "🗂️ 管理更新",
        "menu_settings": "⚙️ 设置",
        "start": "你好！发送加密货币或稳定币代号（如 BTC、USDT、TON），我会提供 CoinMarketCap 的最新信息。",
        "help": (
            "使用菜单按钮或命令：\n"
            "- {automation}\n"
            "- {manage}\n"
            "- {settings}\n"
            "或发送如 BTC/USDT 获取即时数据。"
        ),
        "automation_prompt": "自动更新：发送代号（如 BTC、USDT、TON）。",
        "invalid_symbol": "请发送有效的代号（仅限字母或数字）。",
        "symbol_not_found": "在 CoinMarketCap 上找不到 {symbol}。换一个试试？",
        "choose_frequency": "好的，找到 {symbol}。选择发送频率：",
        "invalid_selection": "选择无效。请重新开始自动更新。",
        "missing_data": "数据缺失。请重新开始自动更新。",
        "automation_created": (
            "已为 {symbol} 创建自动更新（{period}）。ID: {automation_id}。"
            "使用 {manage_label} 查看或调整。"
        ),
        "automation_prefix": "[{period} 更新]",
        "no_automations": "暂无自动更新。使用 {automation_label} 创建一个。",
        "automation_list_header": "你的自动更新：",
        "automation_line": "- ID {automation_id}: {symbol}（{period}）每 {every_hours} 小时",
        "delete_button": "删除 #{automation_id}（{symbol}）",
        "invalid_action": "无效操作。",
        "invalid_id": "自动更新 ID 无效。",
        "automation_missing": "未找到该自动更新。",
        "deleted_automation": "已删除自动更新 #{automation_id}。",
        "invalid_period": "无效的周期选择。",
        "updated_period": "自动更新 #{automation_id} 已改为 {period}。",
        "automation_cancelled": "已取消设置。",
        "fetch_unavailable": "关于 {symbol} 的自动更新：现在无法获取数据。",
        "manual_fetch_fail": "现在无法获取实时数据，请稍后再试。",
        "invalid_language": "语言选择无效。",
        "cancel_button": "❌ 取消",
        "cancelled": "已取消。",
        "language_prompt": "选择你的语言：",
        "language_updated": "语言已切换为 {language}。",
        "quote_price": "价格",
        "quote_change": "24小时变化",
        "quote_marketcap": "市值",
        "quote_volume": "24小时成交量",
        "quote_rank": "市值排名",
        "quote_source": "来源",
        "periods": {
            "hourly": "每小时",
            "daily": "每天",
            "weekly": "每周",
            "monthly": "每月",
        },
    },
    "fa": {
        "menu_automation": "🤖 خودکارسازی",
        "menu_manage": "🗂️ مدیریت خودکارسازی‌ها",
        "menu_settings": "⚙️ تنظیمات",
        "start": "سلام! نماد کریپتو یا استیبل‌کوین (مثل BTC، USDT، TON) را بفرست تا آخرین اطلاعات CoinMarketCap را بگیرم.",
        "help": (
            "از دکمه‌های منو یا دستورها استفاده کن:\n"
            "- {automation}\n"
            "- {manage}\n"
            "- {settings}\n"
            "یا نمادی مثل BTC/USDT بفرست تا داده فوری بگیری."
        ),
        "automation_prompt": "راه‌اندازی خودکارسازی: یک نماد بفرست (مثل BTC، USDT، TON).",
        "invalid_symbol": "لطفاً یک نماد معتبر بفرست (فقط حروف/اعداد).",
        "symbol_not_found": "{symbol} در CoinMarketCap پیدا نشد. نماد دیگری امتحان کن؟",
        "choose_frequency": "عالی، {symbol} پیدا شد. بازه‌ی ارسال را انتخاب کن:",
        "invalid_selection": "انتخاب نامعتبر. خودکارسازی را دوباره شروع کن.",
        "missing_data": "اطلاعات ناقص است. خودکارسازی را دوباره شروع کن.",
        "automation_created": (
            "خودکارسازی برای {symbol} ({period}) ساخته شد. شناسه: {automation_id}. "
            "برای مشاهده یا تغییر از {manage_label} استفاده کن."
        ),
        "automation_prefix": "[به‌روزرسانی {period}]",
        "no_automations": "خودکارسازی‌ای نداری. با {automation_label} یکی بساز.",
        "automation_list_header": "خودکارسازی‌های تو:",
        "automation_line": "- شناسه {automation_id}: {symbol} ({period}) هر {every_hours} ساعت",
        "delete_button": "حذف #{automation_id} ({symbol})",
        "invalid_action": "عملیات نامعتبر.",
        "invalid_id": "شناسه خودکارسازی نامعتبر است.",
        "automation_missing": "خودکارسازی پیدا نشد.",
        "deleted_automation": "خودکارسازی #{automation_id} حذف شد.",
        "invalid_period": "انتخاب بازه نامعتبر است.",
        "updated_period": "خودکارسازی #{automation_id} به {period} تغییر کرد.",
        "automation_cancelled": "تنظیمات لغو شد.",
        "fetch_unavailable": "برای {symbol}: فعلاً نمی‌توانم داده بگیرم.",
        "manual_fetch_fail": "الان نمی‌توانم داده زنده بگیرم. دوباره تلاش کن.",
        "invalid_language": "انتخاب زبان نامعتبر است.",
        "cancel_button": "❌ لغو",
        "cancelled": "لغو شد.",
        "language_prompt": "زبان خود را انتخاب کن:",
        "language_updated": "زبان به {language} تغییر کرد.",
        "quote_price": "قیمت",
        "quote_change": "تغییر ۲۴ساعته",
        "quote_marketcap": "ارزش بازار",
        "quote_volume": "حجم ۲۴ساعته",
        "quote_rank": "رتبه ارزش بازار",
        "quote_source": "منبع",
        "periods": {
            "hourly": "ساعتی",
            "daily": "روزانه",
            "weekly": "هفتگی",
            "monthly": "ماهانه",
        },
    },
}


def get_language_data(lang: str) -> Dict:
    return TEXTS.get(lang, TEXTS[DEFAULT_LANGUAGE])


def translate(lang: str, key: str, **kwargs) -> str:
    data = get_language_data(lang)
    template = data.get(key) or TEXTS[DEFAULT_LANGUAGE].get(key, "")
    return template.format(**kwargs)


def get_period_label(lang: str, period: str) -> str:
    data = get_language_data(lang).get("periods", {})
    return data.get(period, TEXTS[DEFAULT_LANGUAGE]["periods"].get(period, period))


def get_user_language(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    store = context.application.bot_data.setdefault("languages", {})
    return store.get(user_id, DEFAULT_LANGUAGE)


def set_user_language(context: ContextTypes.DEFAULT_TYPE, user_id: int, lang: str) -> str:
    store = context.application.bot_data.setdefault("languages", {})
    selected = lang if lang in TEXTS else DEFAULT_LANGUAGE
    store[user_id] = selected
    return selected


def button_labels(key: str) -> list:
    return [lang_data.get(key) for lang_data in TEXTS.values() if lang_data.get(key)]


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


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    if not chat_id or not message_id:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:  # Telegram might have already removed it
        logger.debug("delete_message_job failed for %s:%s -> %s", chat_id, message_id, exc)


def schedule_delete_message(job_queue: JobQueue, chat_id: int, message_id: int, delay: int) -> None:
    job_queue.run_once(
        delete_message_job,
        when=delay,
        data={"chat_id": chat_id, "message_id": message_id},
        name=f"del-{chat_id}-{message_id}",
    )


def is_menu_button_text(text: str) -> bool:
    if not text:
        return False
    return text in (
        set(button_labels("menu_automation"))
        | set(button_labels("menu_manage"))
        | set(button_labels("menu_settings"))
    )


def main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    data = get_language_data(lang)
    return ReplyKeyboardMarkup(
        [[data["menu_automation"], data["menu_manage"]], [data["menu_settings"]]],
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
    user_id = data.get("user_id")
    lang = get_user_language(context, user_id) if user_id else DEFAULT_LANGUAGE
    period_label = get_period_label(lang, period) if period else period

    client: CoinMarketCapClient = context.application.bot_data["cmc_client"]
    quote = client.fetch_quote(slug) if slug else None
    if not quote or "stats" not in quote or quote["stats"].get("price") is None:
        msg = await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=translate(lang, "fetch_unavailable", symbol=symbol),
        )
        if msg:
            schedule_delete_message(
                context.job_queue, msg.chat_id, msg.message_id, PERIOD_SECONDS.get(period, 3600)
            )
        return

    msg = await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"{translate(lang, 'automation_prefix', period=period_label)}\n{format_quote(quote, lang)}",
    )
    if msg:
        schedule_delete_message(
            context.job_queue, msg.chat_id, msg.message_id, PERIOD_SECONDS.get(period, 3600)
        )


def format_number(value: Optional[float], prefix: str = "", decimals: int = 2) -> str:
    if value is None:
        return "?"
    try:
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
        if dec >= 1:
            return f"{prefix}{dec:,.2f}"

        # For sub-dollar prices, show the full precision without scientific notation.
        fixed = format(dec, "f")
        fixed = fixed.rstrip("0") if "." in fixed else fixed
        if fixed.endswith("."):
            fixed += "0"
        return f"{prefix}{fixed}"
    except (TypeError, ValueError, OverflowError, InvalidOperation):
        return "?"


def format_quote(quote: Dict, lang: str) -> str:
    stats = quote.get("stats", {})
    price = format_price(stats.get("price"))
    change_24h = stats.get("priceChangePercentage24h")
    market_cap = format_number(stats.get("marketCap"), "$", 0)
    volume = format_number(stats.get("volume24h"), "$", 0)
    rank = stats.get("rank")

    labels = get_language_data(lang)
    change_str = "?" if change_24h is None else f"{change_24h:+.2f}%"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"{quote.get('name')} ({quote.get('symbol')})",
        f"{labels['quote_price']}: {price}",
        f"{labels['quote_change']}: {change_str}",
        f"{labels['quote_marketcap']}: {market_cap}",
        f"{labels['quote_volume']}: {volume}",
    ]
    if rank:
        lines.append(f"{labels['quote_rank']}: #{rank}")
    lines.append(f"{labels['quote_source']}: CoinMarketCap - {timestamp}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message and update.message.text and update.message.text.startswith("/"):
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    await update.message.reply_text(
        translate(lang, "start"),
        reply_markup=main_menu_keyboard(lang),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(context, update.effective_user.id)
    if update.message and update.message.text and update.message.text.startswith("/"):
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    await update.message.reply_text(
        translate(
            lang,
            "help",
            automation=translate(lang, "menu_automation"),
            manage=translate(lang, "menu_manage"),
            settings=translate(lang, "menu_settings"),
        ),
        reply_markup=main_menu_keyboard(lang),
    )


async def automation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_language(context, update.effective_user.id)
    if update.message and update.message.text:
        if update.message.text.startswith("/") or is_menu_button_text(update.message.text):
            schedule_delete_message(
                context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
            )
    await update.message.reply_text(
        translate(lang, "automation_prompt"), reply_markup=main_menu_keyboard(lang)
    )
    return AUTO_SYMBOL


async def automation_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    lang = get_user_language(context, update.effective_user.id)
    symbol = (update.message.text or "").strip().upper()
    if not symbol.isalnum():
        await update.message.reply_text(translate(lang, "invalid_symbol"))
        return AUTO_SYMBOL

    slug = client.resolve_symbol(symbol)
    if not slug:
        await update.message.reply_text(translate(lang, "symbol_not_found", symbol=symbol))
        return AUTO_SYMBOL

    context.user_data["auto_symbol"] = symbol
    context.user_data["auto_slug"] = slug

    keyboard = [
        [
            InlineKeyboardButton(f"⏱️ {get_period_label(lang, 'hourly')}", callback_data="new:hourly"),
            InlineKeyboardButton(f"☀️ {get_period_label(lang, 'daily')}", callback_data="new:daily"),
        ],
        [
            InlineKeyboardButton(f"📅 {get_period_label(lang, 'weekly')}", callback_data="new:weekly"),
            InlineKeyboardButton(f"🗓️ {get_period_label(lang, 'monthly')}", callback_data="new:monthly"),
        ],
        [InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:auto")],
    ]
    await update.message.reply_text(
        translate(lang, "choose_frequency", symbol=symbol),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return AUTO_PERIOD


async def automation_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) != 2:
        await query.edit_message_text(translate(lang, "invalid_selection"))
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
        return ConversationHandler.END

    period = parts[1]
    symbol = context.user_data.get("auto_symbol")
    slug = context.user_data.get("auto_slug")
    if not symbol or not slug or period not in PERIOD_SECONDS:
        await query.edit_message_text(translate(lang, "missing_data"))
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
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
        translate(
            lang,
            "automation_created",
            symbol=symbol,
            period=get_period_label(lang, period),
            automation_id=automation_id,
            manage_label=translate(lang, "menu_manage"),
        )
    )
    if query.message:
        schedule_delete_message(
            context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
        )
    return ConversationHandler.END


def build_manage_keyboard(user_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str) -> InlineKeyboardMarkup:
    automations = get_user_automations(context, user_id)["items"]
    rows = []
    for automation_id, item in automations.items():
        rows.append(
            [
                InlineKeyboardButton(
                    f"🗑️ {translate(lang, 'delete_button', automation_id=automation_id, symbol=item['symbol'])}",
                    callback_data=f"del:{automation_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    f"⏱️ {get_period_label(lang, 'hourly')}", callback_data=f"set:{automation_id}:hourly"
                ),
                InlineKeyboardButton(
                    f"☀️ {get_period_label(lang, 'daily')}", callback_data=f"set:{automation_id}:daily"
                ),
                InlineKeyboardButton(
                    f"📅 {get_period_label(lang, 'weekly')}", callback_data=f"set:{automation_id}:weekly"
                ),
                InlineKeyboardButton(
                    f"🗓️ {get_period_label(lang, 'monthly')}", callback_data=f"set:{automation_id}:monthly"
                ),
            ]
        )
    if rows:
        rows.append([InlineKeyboardButton(translate(lang, "cancel_button"), callback_data="cancel:manage")])
    return InlineKeyboardMarkup(rows) if rows else InlineKeyboardMarkup([])


async def manage_automation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_language(context, user_id)
    if update.message and update.message.text:
        if update.message.text.startswith("/") or is_menu_button_text(update.message.text):
            schedule_delete_message(
                context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
            )
    data = get_user_automations(context, user_id)
    items = data["items"]
    if not items:
        await update.message.reply_text(
            translate(lang, "no_automations", automation_label=translate(lang, "menu_automation")),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    lines = [translate(lang, "automation_list_header")]
    for automation_id, item in items.items():
        every_hours = PERIOD_SECONDS[item["period"]] // 3600
        lines.append(
            translate(
                lang,
                "automation_line",
                automation_id=automation_id,
                symbol=item["symbol"],
                period=get_period_label(lang, item["period"]),
                every_hours=every_hours,
            )
        )
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=build_manage_keyboard(user_id, context, lang),
    )


async def manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    data = query.data or ""
    parts = data.split(":")
    if not parts or parts[0] not in {"del", "set"}:
        await query.edit_message_text(translate(lang, "invalid_action"))
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
        return

    user_id = query.from_user.id
    automations = get_user_automations(context, user_id)
    items = automations["items"]

    try:
        automation_id = int(parts[1])
    except (IndexError, ValueError):
        await query.edit_message_text(translate(lang, "invalid_id"))
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
        return

    if automation_id not in items:
        await query.edit_message_text(translate(lang, "automation_missing"))
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
        return

    if parts[0] == "del":
        cancel_automation(context, user_id, automation_id)
        await query.edit_message_text(
            translate(lang, "deleted_automation", automation_id=automation_id)
        )
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
        return

    if parts[0] == "set":
        if len(parts) < 3 or parts[2] not in PERIOD_SECONDS:
            await query.edit_message_text(translate(lang, "invalid_period"))
            if query.message:
                schedule_delete_message(
                    context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
                )
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
        await query.edit_message_text(
            translate(
                lang,
                "updated_period",
                automation_id=automation_id,
                period=get_period_label(lang, period),
            )
        )
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )


def build_language_keyboard(current_lang: str) -> InlineKeyboardMarkup:
    rows = []
    for code, meta in LANGUAGE_OPTIONS.items():
        prefix = "✅ " if code == current_lang else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{prefix}{meta['emoji']} {meta['label']}", callback_data=f"lang:{code}"
                )
            ]
        )
    rows.append([InlineKeyboardButton(translate(current_lang, "cancel_button"), callback_data="cancel:lang")])
    return InlineKeyboardMarkup(rows)


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_language(context, user_id)
    if update.message and update.message.text:
        if update.message.text.startswith("/") or is_menu_button_text(update.message.text):
            schedule_delete_message(
                context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
            )
    await update.message.reply_text(
        translate(lang, "language_prompt"), reply_markup=build_language_keyboard(lang)
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = (query.data or "").split(":")
    await query.answer()

    if len(parts) != 2 or parts[1] not in LANGUAGE_OPTIONS:
        await query.edit_message_text(translate(DEFAULT_LANGUAGE, "invalid_language"))
        if query.message:
            schedule_delete_message(
                context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
            )
        return

    lang = set_user_language(context, query.from_user.id, parts[1])
    await query.edit_message_text(
        translate(lang, "language_prompt"),
        reply_markup=build_language_keyboard(lang),
    )
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=translate(
            lang,
            "language_updated",
            language=f"{LANGUAGE_OPTIONS[lang]['emoji']} {LANGUAGE_OPTIONS[lang]['label']}",
        ),
        reply_markup=main_menu_keyboard(lang),
    )
    if query.message:
        schedule_delete_message(
            context.job_queue, query.message.chat_id, query.message.message_id, MENU_DELETE_SECONDS
        )


async def cancel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang = get_user_language(context, query.from_user.id)
    await query.answer()
    if query.message:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        except Exception as exc:
            logger.debug("Failed to delete menu message: %s", exc)
    ack = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=translate(lang, "cancelled"),
        reply_markup=main_menu_keyboard(lang),
    )
    if ack:
        schedule_delete_message(
            context.job_queue, ack.chat_id, ack.message_id, MENU_DELETE_SECONDS
        )
    return ConversationHandler.END


async def automation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_language(context, update.effective_user.id)
    if update.message and update.message.text and update.message.text.startswith("/"):
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    await update.message.reply_text(
        translate(lang, "automation_cancelled"), reply_markup=main_menu_keyboard(lang)
    )
    return ConversationHandler.END


async def handle_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client: CoinMarketCapClient = context.bot_data["cmc_client"]
    text = (update.message.text or "").strip()
    lang = get_user_language(context, update.effective_user.id)
    if text.startswith("/"):
        schedule_delete_message(
            context.job_queue, update.message.chat_id, update.message.message_id, COMMAND_DELETE_SECONDS
        )
    # Ignore menu button texts here; they are handled elsewhere.
    if is_menu_button_text(text):
        return

    symbol = text.upper()
    if not symbol.isalnum():
        await update.message.reply_text(translate(lang, "invalid_symbol"))
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)

    slug = client.resolve_symbol(symbol)
    if not slug:
        await update.message.reply_text(
        translate(lang, "symbol_not_found", symbol=symbol)
        )
        return

    quote = client.fetch_quote(slug)
    if not quote or "stats" not in quote or quote["stats"].get("price") is None:
        await update.message.reply_text(translate(lang, "manual_fetch_fail"))
        return

    reply = await update.message.reply_text(
        format_quote(quote, lang), reply_markup=main_menu_keyboard(lang)
    )
    if reply:
        schedule_delete_message(
            context.job_queue,
            reply.chat_id,
            reply.message_id,
            MANUAL_QUOTE_DELETE_SECONDS,
        )


def build_application(token: str) -> Application:
    client = CoinMarketCapClient()
    job_queue = JobQueue()
    application = Application.builder().token(token).job_queue(job_queue).build()
    application.bot_data["cmc_client"] = client

    automation_pattern = button_regex("menu_automation")
    manage_pattern = button_regex("menu_manage")
    settings_pattern = button_regex("menu_settings")
    menu_pattern = combined_button_regex(["menu_automation", "menu_manage", "menu_settings"])

    automation_conv = ConversationHandler(
        entry_points=[
            CommandHandler("automation", automation_start),
            MessageHandler(filters.Regex(automation_pattern), automation_start),
        ],
        states={
            AUTO_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, automation_symbol)],
            AUTO_PERIOD: [
                CallbackQueryHandler(automation_period_selection, pattern="^new:"),
                CallbackQueryHandler(cancel_menu, pattern="^cancel:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", automation_cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_menu))
    application.add_handler(MessageHandler(filters.Regex(settings_pattern), settings_menu))
    application.add_handler(CommandHandler("manageautomation", manage_automation))
    application.add_handler(MessageHandler(filters.Regex(manage_pattern), manage_automation))
    application.add_handler(automation_conv)
    application.add_handler(CallbackQueryHandler(manage_callback, pattern="^(del|set):"))
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang:"))
    application.add_handler(CallbackQueryHandler(cancel_menu, pattern="^cancel:"))
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang:"))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern),
            handle_symbol,
        )
    )

    return application


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
