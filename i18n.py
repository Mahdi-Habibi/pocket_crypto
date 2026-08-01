"""Multilingual strings for Pocket Crypto bot."""

from __future__ import annotations

from typing import Dict

DEFAULT_LANGUAGE = "en"

LANGUAGE_OPTIONS = {
    "en": {"label": "English", "emoji": "🇺🇸"},
    "es": {"label": "Español", "emoji": "🇪🇸"},
    "zh": {"label": "中文", "emoji": "🇨🇳"},
    "fa": {"label": "فارسی", "emoji": "🇮🇷"},
}

_EN = {
    "menu_search": "🔎 Search",
    "menu_discover": "📈 Discover",
    "menu_watchlist": "⭐ Watchlist",
    "menu_alerts": "🚨 Alerts",
    "menu_automation": "🤖 Automation",
    "menu_manage": "🗂️ Manage",
    "menu_settings": "⚙️ Settings",
    "start": (
        "🪙 <b>Pocket Crypto</b>\n"
        "Live markets from CoinMarketCap — designed for quick decisions.\n\n"
        "Try a ticker like <code>BTC</code>, <code>ETH</code>, or <code>TON</code>\n"
        "or use the menu for Discover, Watchlist, Alerts &amp; more."
    ),
    "help": (
        "<b>Commands &amp; tips</b>\n"
        "• Send a symbol: <code>BTC</code>\n"
        "• Compare: <code>/compare BTC ETH SOL</code>\n"
        "• Convert: <code>/convert 1.5 ETH</code> or <code>2 BTC</code>\n"
        "• Discover: {discover}\n"
        "• Watchlist: {watchlist}\n"
        "• Alerts: {alerts}\n"
        "• Automation: {automation}\n"
        "• Manage jobs: {manage}\n"
        "• Settings: {settings}"
    ),
    "search_prompt": "Send a ticker or name (e.g. <code>BTC</code>, <code>solana</code>).",
    "discover_prompt": "Market radar — pick a view:",
    "button_gainers": "🚀 Gainers",
    "button_losers": "📉 Losers",
    "button_trending": "🔥 Trending",
    "button_top": "🏆 Top market cap",
    "gainers_header": "🚀 <b>Top 24h gainers</b>",
    "losers_header": "📉 <b>Top 24h losers</b>",
    "trending_header": "🔥 <b>Highest 24h volume</b>",
    "top_header": "🏆 <b>Top by market cap</b>",
    "movers_unavailable": "Couldn't load market movers right now.",
    "automation_prompt": "Automation setup: send a symbol (e.g. <code>BTC</code>).",
    "invalid_symbol": "Please send a valid symbol (letters/numbers only).",
    "symbol_not_found": "Couldn't find <b>{symbol}</b>. Did you mean one of these?",
    "symbol_not_found_plain": "Couldn't find <b>{symbol}</b> on CoinMarketCap.",
    "choose_frequency": "Great — <b>{symbol}</b> found. How often should I ping you?",
    "invalid_selection": "Invalid selection. Please restart Automation.",
    "missing_data": "Missing data. Please restart Automation.",
    "automation_created": (
        "✅ Automation created for <b>{symbol}</b> ({period}).\n"
        "ID: <code>{automation_id}</code>\n"
        "Use {manage_label} to adjust."
    ),
    "automation_prefix": "⏰ <b>{period} automation</b>",
    "no_automations": "No automations yet. Use {automation_label} to create one.",
    "automation_list_header": "<b>Your automations</b>",
    "automation_line": "• #{automation_id}: <b>{symbol}</b> · {period} · every {every_hours}h",
    "delete_button": "🗑 #{automation_id} {symbol}",
    "invalid_action": "Invalid action.",
    "invalid_id": "Invalid automation id.",
    "automation_missing": "Automation not found.",
    "deleted_automation": "Deleted automation #{automation_id}.",
    "invalid_period": "Invalid period selection.",
    "updated_period": "Updated automation #{automation_id} to {period}.",
    "automation_cancelled": "Automation setup cancelled.",
    "fetch_unavailable": "Automation for {symbol}: unable to fetch data right now.",
    "manual_fetch_fail": "Couldn't fetch live data right now. Please try again.",
    "invalid_language": "Invalid language selection.",
    "cancel_button": "❌ Cancel",
    "cancelled": "Cancelled.",
    "language_prompt": "Choose your language:",
    "language_updated": "Language changed to {language}.",
    "quote_price": "Price",
    "quote_change_1h": "1h",
    "quote_change_24h": "24h",
    "quote_change_7d": "7d",
    "quote_change_30d": "30d",
    "quote_marketcap": "Market Cap",
    "quote_volume": "Volume 24h",
    "quote_rank": "Rank",
    "quote_range": "24h Range",
    "quote_ath": "All-time high",
    "quote_supply": "Circulating",
    "quote_fdv": "FDV",
    "quote_dominance": "Dominance",
    "button_markets": "📊 Markets",
    "button_news": "📰 News",
    "button_predictions": "🔮 Forecast",
    "button_refresh": "🔄 Refresh",
    "button_watch": "⭐ Watch",
    "button_unwatch": "☆ Unwatch",
    "button_alert": "🚨 Alert",
    "button_cmc": "🔗 CoinMarketCap",
    "button_compare": "⚖️ Compare",
    "markets_header": "📊 <b>Top markets</b>",
    "markets_unavailable": "No market data available right now.",
    "news_header": "📰 <b>Latest news</b>",
    "news_unavailable": "No news found right now.",
    "predictions_header": "🔮 <b>Price forecasts</b>",
    "predictions_unavailable": "No predictions found right now.",
    "watchlist_empty": "Your watchlist is empty. Open a coin and tap <b>⭐ Watch</b>, or send <code>/watch BTC</code>.",
    "watchlist_header": "⭐ <b>Watchlist</b> ({count})",
    "watch_added": "Added <b>{symbol}</b> to your watchlist.",
    "watch_removed": "Removed <b>{symbol}</b> from your watchlist.",
    "watch_exists": "<b>{symbol}</b> is already on your watchlist.",
    "watch_missing": "<b>{symbol}</b> is not on your watchlist.",
    "watch_limit": "Watchlist limit reached ({limit}). Remove one first.",
    "alerts_empty": (
        "No price alerts yet.\n"
        "Create one with:\n"
        "<code>/alert BTC 70000 above</code>\n"
        "<code>/alert ETH 2000 below</code>\n"
        "or open a coin and tap <b>🚨 Alert</b>."
    ),
    "alerts_header": "🚨 <b>Active alerts</b> ({count})",
    "alert_line": "• #{alert_id}: <b>{symbol}</b> {direction} {target}",
    "alert_created": "✅ Alert #{alert_id}: ping me when <b>{symbol}</b> goes {direction} {target}.",
    "alert_deleted": "Deleted alert #{alert_id}.",
    "alert_missing": "Alert not found.",
    "alert_invalid": "Usage: <code>/alert BTC 70000 above</code> or <code>/alert ETH 2000 below</code>",
    "alert_prompt": "Send target like <code>70000 above</code> or <code>2000 below</code> for <b>{symbol}</b>.",
    "alert_triggered": (
        "🚨 <b>Alert triggered</b>\n"
        "<b>{symbol}</b> is now {price}\n"
        "Condition: {direction} {target}"
    ),
    "alert_limit": "Alert limit reached ({limit}). Delete one first.",
    "delete_alert_button": "🗑 #{alert_id} {symbol}",
    "compare_usage": "Usage: <code>/compare BTC ETH SOL</code> (2–4 symbols)",
    "compare_header": "⚖️ <b>Compare</b>",
    "compare_need_more": "Need at least 2 valid symbols to compare.",
    "convert_usage": "Usage: <code>/convert 1.5 ETH</code> or send <code>2 BTC</code>",
    "convert_result": "💱 <b>{amount} {symbol}</b> ≈ <b>{value}</b>",
    "loading": "Fetching live data…",
    "refreshed": "Quote refreshed.",
    "periods": {
        "hourly": "Hourly",
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly",
    },
    "direction_above": "above",
    "direction_below": "below",
}

TEXTS: Dict[str, Dict] = {
    "en": _EN,
    "es": {
        **_EN,
        "menu_search": "🔎 Buscar",
        "menu_discover": "📈 Descubrir",
        "menu_watchlist": "⭐ Lista",
        "menu_alerts": "🚨 Alertas",
        "menu_automation": "🤖 Automatización",
        "menu_manage": "🗂️ Gestionar",
        "menu_settings": "⚙️ Ajustes",
        "start": (
            "🪙 <b>Pocket Crypto</b>\n"
            "Mercados en vivo de CoinMarketCap.\n\n"
            "Prueba un ticker como <code>BTC</code>, <code>ETH</code> o <code>TON</code>."
        ),
        "search_prompt": "Envía un ticker o nombre (ej. <code>BTC</code>, <code>solana</code>).",
        "discover_prompt": "Radar de mercado — elige una vista:",
        "button_gainers": "🚀 Ganadores",
        "button_losers": "📉 Perdedores",
        "button_trending": "🔥 Tendencia",
        "button_top": "🏆 Top capitalización",
        "cancel_button": "❌ Cancelar",
        "cancelled": "Cancelado.",
        "language_prompt": "Elige tu idioma:",
        "language_updated": "Idioma cambiado a {language}.",
        "manual_fetch_fail": "No pude obtener datos en vivo ahora. Inténtalo de nuevo.",
        "watchlist_empty": "Tu lista está vacía. Abre una moneda y pulsa <b>⭐ Watch</b>.",
        "watch_added": "Se añadió <b>{symbol}</b> a tu lista.",
        "watch_removed": "Se eliminó <b>{symbol}</b> de tu lista.",
        "alerts_empty": "Sin alertas. Usa <code>/alert BTC 70000 above</code>.",
        "alert_created": "✅ Alerta #{alert_id}: te aviso si <b>{symbol}</b> pasa {direction} {target}.",
        "compare_usage": "Uso: <code>/compare BTC ETH SOL</code> (2–4 símbolos)",
        "convert_usage": "Uso: <code>/convert 1.5 ETH</code> o envía <code>2 BTC</code>",
        "convert_result": "💱 <b>{amount} {symbol}</b> ≈ <b>{value}</b>",
        "periods": {
            "hourly": "Cada hora",
            "daily": "Diario",
            "weekly": "Semanal",
            "monthly": "Mensual",
        },
        "direction_above": "por encima de",
        "direction_below": "por debajo de",
    },
    "zh": {
        **_EN,
        "menu_search": "🔎 搜索",
        "menu_discover": "📈 发现",
        "menu_watchlist": "⭐ 自选",
        "menu_alerts": "🚨 提醒",
        "menu_automation": "🤖 自动更新",
        "menu_manage": "🗂️ 管理",
        "menu_settings": "⚙️ 设置",
        "start": (
            "🪙 <b>Pocket Crypto</b>\n"
            "来自 CoinMarketCap 的实时行情。\n\n"
            "发送代号如 <code>BTC</code>、<code>ETH</code>、<code>TON</code>。"
        ),
        "search_prompt": "发送代号或名称（如 <code>BTC</code>、<code>solana</code>）。",
        "discover_prompt": "市场雷达 — 选择视图：",
        "button_gainers": "🚀 涨幅榜",
        "button_losers": "📉 跌幅榜",
        "button_trending": "🔥 热度",
        "button_top": "🏆 市值榜",
        "cancel_button": "❌ 取消",
        "cancelled": "已取消。",
        "language_prompt": "选择你的语言：",
        "language_updated": "语言已切换为 {language}。",
        "manual_fetch_fail": "现在无法获取实时数据，请稍后再试。",
        "watchlist_empty": "自选为空。打开币种并点击 <b>⭐ Watch</b>。",
        "watch_added": "已将 <b>{symbol}</b> 加入自选。",
        "watch_removed": "已将 <b>{symbol}</b> 移出自选。",
        "alerts_empty": "暂无提醒。使用 <code>/alert BTC 70000 above</code>。",
        "alert_created": "✅ 提醒 #{alert_id}：当 <b>{symbol}</b> {direction} {target} 时通知你。",
        "compare_usage": "用法：<code>/compare BTC ETH SOL</code>（2–4 个代号）",
        "convert_usage": "用法：<code>/convert 1.5 ETH</code> 或发送 <code>2 BTC</code>",
        "convert_result": "💱 <b>{amount} {symbol}</b> ≈ <b>{value}</b>",
        "periods": {
            "hourly": "每小时",
            "daily": "每天",
            "weekly": "每周",
            "monthly": "每月",
        },
        "direction_above": "高于",
        "direction_below": "低于",
    },
    "fa": {
        **_EN,
        "menu_search": "🔎 جستجو",
        "menu_discover": "📈 کشف",
        "menu_watchlist": "⭐ دیده‌بان",
        "menu_alerts": "🚨 هشدارها",
        "menu_automation": "🤖 خودکارسازی",
        "menu_manage": "🗂️ مدیریت",
        "menu_settings": "⚙️ تنظیمات",
        "start": (
            "🪙 <b>Pocket Crypto</b>\n"
            "بازار زنده از CoinMarketCap.\n\n"
            "نمادی مثل <code>BTC</code>، <code>ETH</code> یا <code>TON</code> بفرست."
        ),
        "search_prompt": "یک نماد یا نام بفرست (مثل <code>BTC</code> یا <code>solana</code>).",
        "discover_prompt": "رادار بازار — یک نما انتخاب کن:",
        "button_gainers": "🚀 بیشترین رشد",
        "button_losers": "📉 بیشترین افت",
        "button_trending": "🔥 داغ‌ترین‌ها",
        "button_top": "🏆 برتر از نظر ارزش",
        "cancel_button": "❌ لغو",
        "cancelled": "لغو شد.",
        "language_prompt": "زبان خود را انتخاب کن:",
        "language_updated": "زبان به {language} تغییر کرد.",
        "manual_fetch_fail": "الان نمی‌توانم داده زنده بگیرم. دوباره تلاش کن.",
        "watchlist_empty": "دیده‌بان خالی است. روی <b>⭐ Watch</b> بزن یا <code>/watch BTC</code> بفرست.",
        "watch_added": "<b>{symbol}</b> به دیده‌بان اضافه شد.",
        "watch_removed": "<b>{symbol}</b> از دیده‌بان حذف شد.",
        "alerts_empty": "هشداری نیست. از <code>/alert BTC 70000 above</code> استفاده کن.",
        "alert_created": "✅ هشدار #{alert_id}: وقتی <b>{symbol}</b> {direction} {target} شد خبر بده.",
        "compare_usage": "نحوه استفاده: <code>/compare BTC ETH SOL</code> (۲ تا ۴ نماد)",
        "convert_usage": "نحوه استفاده: <code>/convert 1.5 ETH</code> یا <code>2 BTC</code>",
        "convert_result": "💱 <b>{amount} {symbol}</b> ≈ <b>{value}</b>",
        "periods": {
            "hourly": "ساعتی",
            "daily": "روزانه",
            "weekly": "هفتگی",
            "monthly": "ماهانه",
        },
        "direction_above": "بالای",
        "direction_below": "زیر",
    },
}


def get_language_data(lang: str) -> Dict:
    return TEXTS.get(lang, TEXTS[DEFAULT_LANGUAGE])


def translate(lang: str, key: str, **kwargs) -> str:
    data = get_language_data(lang)
    template = data.get(key) or TEXTS[DEFAULT_LANGUAGE].get(key, "")
    if not isinstance(template, str):
        return str(template)
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def get_period_label(lang: str, period: str) -> str:
    data = get_language_data(lang).get("periods", {})
    return data.get(period, TEXTS[DEFAULT_LANGUAGE]["periods"].get(period, period))


def button_labels(key: str) -> list:
    return [lang_data.get(key) for lang_data in TEXTS.values() if lang_data.get(key)]
