"""Vercel serverless webhook for the Telegram bot.

Uses lazy initialization so health checks can succeed even when the bot token
is missing, and so cold starts fail with a clear error body instead of an
opaque FUNCTION_INVOCATION_FAILED crash during import.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler
from typing import Any, Optional

from telegram import Update

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_application = None
_settings: Optional[dict[str, Any]] = None
_init_error: Optional[str] = None
_webhook_configured = False


def _run_in_loop(coro, timeout: float = 25.0):
    if _event_loop is None:
        raise RuntimeError("Event loop is not running")
    return asyncio.run_coroutine_threadsafe(coro, _event_loop).result(timeout=timeout)


def _start_loop() -> None:
    global _event_loop, _loop_thread
    if _event_loop is not None:
        return

    loop = asyncio.new_event_loop()

    def _runner() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=_runner, name="telegram-loop", daemon=True)
    thread.start()
    _event_loop = loop
    _loop_thread = thread


def _ensure_application():
    """Initialize the Telegram application once per warm instance."""
    global _application, _settings, _init_error, _webhook_configured

    if _application is not None:
        return _application
    if _init_error is not None:
        raise RuntimeError(_init_error)

    with _init_lock:
        if _application is not None:
            return _application
        if _init_error is not None:
            raise RuntimeError(_init_error)

        try:
            # Import here so missing deps/token do not crash module import.
            from bot import build_application, load_settings

            settings = load_settings()
            _start_loop()
            application = build_application(settings["token"])
            _run_in_loop(application.initialize())
            _run_in_loop(application.start())

            if settings.get("use_webhook") and settings.get("webhook_base") and not _webhook_configured:
                webhook_url = f"{settings['webhook_base'].rstrip('/')}{settings['webhook_path']}"
                _run_in_loop(
                    application.bot.set_webhook(webhook_url, drop_pending_updates=False)
                )
                _webhook_configured = True
                logger.info("Webhook set to %s", webhook_url)

            _settings = settings
            _application = application
            return _application
        except Exception as exc:
            _init_error = f"{type(exc).__name__}: {exc}"
            logger.exception("Failed to initialize Telegram application")
            raise RuntimeError(_init_error) from exc


async def _process_update(payload: dict) -> None:
    application = _ensure_application()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _write_response(self, status: int, body: str, content_type: str = "text/plain") -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _expected_paths(self) -> set[str]:
        paths = {"/api/webhook", "/api/webhook.py", "/"}
        if _settings and _settings.get("webhook_path"):
            configured = str(_settings["webhook_path"]).rstrip("/") or "/api/webhook"
            paths.add(configured)
            paths.add(configured + ".py")
        return {p.rstrip("/") or "/" for p in paths}

    def do_GET(self):
        # Health check should not hard-crash the function.
        try:
            _ensure_application()
            self._write_response(200, "ok")
        except Exception as exc:
            self._write_response(503, f"unavailable: {exc}")

    def do_POST(self):
        request_path = (self.path or "/").split("?", 1)[0].rstrip("/") or "/"
        # On first request settings may be unset; allow common Vercel paths.
        if request_path not in self._expected_paths() and request_path not in {
            "/api/webhook",
            "/api/webhook.py",
            "/",
        }:
            self._write_response(404, "not found")
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode() or "{}")
        except json.JSONDecodeError:
            self._write_response(400, "invalid json")
            return

        try:
            _ensure_application()
            _run_in_loop(_process_update(payload), timeout=20.0)
        except Exception as exc:
            logger.exception("Failed to process Telegram update")
            self._write_response(500, f"error: {exc}")
            return

        self._write_response(200, "ok")
