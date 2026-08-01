"""CoinMarketCap public API client with listing helpers for discovery features."""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class CoinMarketCapClient:
    """Lightweight client for public CoinMarketCap endpoints."""

    LISTING_URL = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    DETAIL_URL = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail"
    MARKETS_URL = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/latest"
    NEWS_URL = "https://api.coinmarketcap.com/content/v3/news"

    def __init__(self, listing_limit: int = 5000, cache_seconds: int = 600):
        self.listing_limit = listing_limit
        self.cache_seconds = cache_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "PocketCryptoBot/2.0 (+https://github.com/Mahdi-Habibi/pocket_crypto)",
            }
        )
        self._symbol_cache: Dict[str, str] = {}
        self._name_cache: Dict[str, str] = {}
        self._listing_cache: List[Dict] = []
        self._last_refresh = 0.0

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Return CoinMarketCap slug for a given ticker symbol."""
        self._refresh_cache()
        return self._symbol_cache.get(symbol.upper())

    def symbol_for_slug(self, slug: str) -> Optional[str]:
        """Reverse-lookup ticker symbol for a CoinMarketCap slug."""
        self._refresh_cache()
        for symbol, cached_slug in self._symbol_cache.items():
            if cached_slug == slug:
                return symbol
        return None

    def suggest_symbols(self, query: str, limit: int = 6) -> List[Dict[str, str]]:
        """Suggest tickers/names that match a partial query."""
        self._refresh_cache()
        q = (query or "").strip().upper()
        if not q:
            return []

        suggestions: List[Dict[str, str]] = []
        seen = set()

        # Exact / prefix symbol matches first
        for symbol, slug in self._symbol_cache.items():
            if symbol.startswith(q) or q in symbol:
                if symbol in seen:
                    continue
                seen.add(symbol)
                suggestions.append(
                    {
                        "symbol": symbol,
                        "slug": slug,
                        "name": self._name_cache.get(symbol, symbol),
                    }
                )
                if len(suggestions) >= limit:
                    return suggestions

        # Name matches
        for symbol, name in self._name_cache.items():
            if symbol in seen:
                continue
            if q in name.upper():
                seen.add(symbol)
                suggestions.append(
                    {
                        "symbol": symbol,
                        "slug": self._symbol_cache.get(symbol, ""),
                        "name": name,
                    }
                )
                if len(suggestions) >= limit:
                    break
        return suggestions

    def fetch_quote(self, slug: str) -> Optional[Dict]:
        """Fetch detailed statistics for a specific coin slug."""
        try:
            resp = self.session.get(self.DETAIL_URL, params={"slug": slug}, timeout=12)
            resp.raise_for_status()
            data = resp.json().get("data")
            if not data:
                return None
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "slug": slug,
                "stats": data.get("statistics") or {},
                "description": (data.get("description") or "")[:280],
            }
        except requests.RequestException as exc:
            logger.exception("Failed fetching detail for %s: %s", slug, exc)
            return None

    def fetch_markets(self, slug: str, limit: int = 8) -> list:
        """Fetch top markets (exchanges) where the coin trades."""
        try:
            resp = self.session.get(
                self.MARKETS_URL,
                params={"slug": slug, "start": 1, "limit": limit},
                timeout=12,
            )
            resp.raise_for_status()
            market_pairs = (resp.json().get("data") or {}).get("marketPairs") or []
            markets = []
            for pair in market_pairs:
                base = pair.get("baseSymbol")
                quote = pair.get("quoteSymbol")
                pair_label = pair.get("marketPair") or (
                    f"{base}/{quote}" if base and quote else None
                )
                markets.append(
                    {
                        "exchange": pair.get("exchangeName"),
                        "pair": pair_label,
                        "url": pair.get("marketUrl"),
                        "volume": pair.get("volumeUsd"),
                    }
                )
            return markets
        except requests.RequestException as exc:
            logger.exception("Failed fetching markets for %s: %s", slug, exc)
            return []

    def fetch_news(self, coin_id: Optional[int], limit: int = 5) -> list:
        """Fetch latest news for the given coin id."""
        if not coin_id:
            return []
        try:
            resp = self.session.get(
                self.NEWS_URL,
                params={"cryptocurrencyId": coin_id, "size": limit},
                timeout=12,
            )
            resp.raise_for_status()
            items = resp.json().get("data") or []
            news = []
            for item in items:
                meta = item.get("meta") or {}
                news.append(
                    {
                        "title": meta.get("title"),
                        "url": meta.get("sourceUrl") or meta.get("url"),
                        "source": meta.get("sourceName"),
                        "published": meta.get("createdAt"),
                    }
                )
            return news
        except requests.RequestException as exc:
            logger.exception("Failed fetching news for %s: %s", coin_id, exc)
            return []

    def fetch_predictions(self, slug: Optional[str], limit: int = 5) -> list:
        """Fetch price predictions from coin-predictions.com for the given slug."""
        if not slug:
            return []
        try:
            resp = self.session.get(f"https://coin-predictions.com/{slug}/", timeout=12)
            if resp.status_code != 200:
                return []
            html = resp.text
            import html as html_lib

            matches = re.findall(
                r"<strong>([^<]*?Forecast[^<]*?)</strong>\s*&nbsp;?([^<]+)",
                html,
                flags=re.I,
            )
            items = []
            for title_raw, body_raw in matches:
                title = html_lib.unescape(re.sub("<.*?>", "", title_raw)).strip()
                body = html_lib.unescape(re.sub("<.*?>", "", body_raw)).strip()
                if title and body:
                    items.append(
                        {
                            "title": title,
                            "description": body,
                            "source": "coin-predictions.com",
                        }
                    )
                if len(items) >= limit:
                    break
            return items
        except requests.RequestException as exc:
            logger.exception("Failed fetching predictions for %s: %s", slug, exc)
            return []

    def fetch_movers(self, sort_by: str = "percent_change_24h", limit: int = 10) -> List[Dict]:
        """Fetch top movers (gainers by default). Use sortType asc for losers."""
        sort_type = "desc"
        if sort_by.endswith(":asc"):
            sort_by, sort_type = sort_by.split(":", 1)[0], "asc"
        try:
            resp = self.session.get(
                self.LISTING_URL,
                params={
                    "start": 1,
                    "limit": limit,
                    "sortBy": sort_by,
                    "sortType": sort_type,
                    "convert": "USD",
                    "cryptoType": "all",
                    "tagType": "all",
                    "audited": False,
                },
                timeout=12,
            )
            resp.raise_for_status()
            listing = (resp.json().get("data") or {}).get("cryptoCurrencyList") or []
            return [self._normalize_listing_item(item) for item in listing]
        except requests.RequestException as exc:
            logger.exception("Failed fetching movers (%s): %s", sort_by, exc)
            return []

    def get_cached_listing(self, limit: int = 20) -> List[Dict]:
        self._refresh_cache()
        return self._listing_cache[:limit]

    def _normalize_listing_item(self, item: Dict) -> Dict:
        quote = (item.get("quotes") or [{}])[0]
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "symbol": item.get("symbol"),
            "slug": item.get("slug"),
            "rank": item.get("cmcRank"),
            "price": quote.get("price"),
            "change_1h": quote.get("percentChange1h"),
            "change_24h": quote.get("percentChange24h"),
            "change_7d": quote.get("percentChange7d"),
            "market_cap": quote.get("marketCap"),
            "volume_24h": quote.get("volume24h"),
        }

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
            resp = self.session.get(self.LISTING_URL, params=params, timeout=20)
            resp.raise_for_status()
            payload = resp.json().get("data", {})
            listing = payload.get("cryptoCurrencyList", [])
            mapping: Dict[str, str] = {}
            names: Dict[str, str] = {}
            normalized: List[Dict] = []
            for item in listing:
                symbol = (item.get("symbol") or "").upper()
                slug = item.get("slug")
                name = item.get("name") or symbol
                if symbol and slug and symbol not in mapping:
                    mapping[symbol] = slug
                    names[symbol] = name
                normalized.append(self._normalize_listing_item(item))
            self._symbol_cache = mapping
            self._name_cache = names
            self._listing_cache = normalized
            self._last_refresh = time.time()
            logger.info("Loaded %s symbols from CoinMarketCap", len(mapping))
        except requests.RequestException as exc:
            logger.exception("Failed refreshing symbol cache: %s", exc)
