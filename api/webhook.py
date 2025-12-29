import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler

from telegram import Update

from main import build_application, load_settings

settings = load_settings()
application = build_application(settings["token"])

# Run the Telegram application (and its JobQueue) on a background event loop.
event_loop = asyncio.new_event_loop()


def _loop_runner(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


threading.Thread(target=_loop_runner, args=(event_loop,), daemon=True).start()


def _run_in_loop(coro):
    return asyncio.run_coroutine_threadsafe(coro, event_loop).result()


_run_in_loop(application.initialize())
_run_in_loop(application.start())

if settings.get("use_webhook") and settings.get("webhook_base"):
    webhook_url = f"{settings['webhook_base'].rstrip('/')}{settings['webhook_path']}"
    _run_in_loop(application.bot.set_webhook(webhook_url, drop_pending_updates=True))


async def _process_update(payload: dict) -> None:
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)


class handler(BaseHTTPRequestHandler):
    def _write_response(self, status: int, body: str) -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        # Simple health check endpoint.
        self._write_response(200, "ok")

    def do_POST(self):
        expected_path = settings["webhook_path"].rstrip("/") or "/api/webhook"
        if self.path.rstrip("/") != expected_path:
            self._write_response(404, "not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode() or "{}")
        except json.JSONDecodeError:
            self._write_response(400, "invalid json")
            return

        future = asyncio.run_coroutine_threadsafe(_process_update(payload), event_loop)
        try:
            future.result(timeout=10)
        except Exception as exc:
            self._write_response(500, f"error: {exc}")
        else:
            self._write_response(200, "ok")
