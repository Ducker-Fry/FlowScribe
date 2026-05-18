"""Lightweight HTTP server for Bookmarklet integration."""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from flowscribe.server.handlers import AddUrlHandler

logger = logging.getLogger(__name__)


class BookmarkletRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler with CORS support."""

    def __init__(self, *args, handler: AddUrlHandler, **kwargs) -> None:
        self.add_url_handler = handler
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use logging module."""
        logger.info(format % args)

    def _send_cors_headers(self) -> None:
        """Send CORS headers for browser requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json_response(self, status: int, data: dict[str, Any]) -> None:
        """Send JSON response with CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        """Handle preflight CORS requests."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/status":
            result = self.add_url_handler.get_status()
            logger.info(f"📊 Status check - Queue: {result['queue']['total']} total, "
                       f"{result['queue']['pending']} pending, "
                       f"{result['queue']['completed']} completed")
            self._send_json_response(200, result)
        elif self.path == "/bookmarklet.js":
            logger.info("📜 Bookmarklet script requested")
            self._send_bookmarklet_script()
        else:
            logger.warning(f"❌ 404 Not Found: {self.path}")
            self._send_json_response(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/add-url":
            self._handle_add_url()
        elif self.path == "/add-urls":
            self._handle_add_urls()
        else:
            self._send_json_response(404, {"error": "Not found"})

    def _handle_add_url(self) -> None:
        """Handle single URL addition."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            url = data.get("url", "")
            title = data.get("title", "")

            result = self.add_url_handler.add_url(
                url=url,
                title=title,
                timestamp=data.get("timestamp"),
            )

            if result["status"] == "error":
                logger.warning(f"❌ Failed to add URL: {url[:60]}... - {result['message']}")
                self._send_json_response(400, result)
            elif result["status"] == "duplicate":
                logger.info(f"⚠️  Duplicate URL (status: {result['existing_status']}): {url[:60]}...")
                self._send_json_response(200, result)
            else:
                title_str = f" - {title[:40]}..." if title else ""
                logger.info(f"✅ Added to queue (position {result['position']}): {url[:60]}...{title_str}")
                self._send_json_response(200, result)

        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON in request body")
            self._send_json_response(400, {"status": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.exception("❌ Error handling add-url request")
            self._send_json_response(500, {"status": "error", "message": str(e)})

    def _handle_add_urls(self) -> None:
        """Handle batch URL addition."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            urls = data.get("urls", [])
            if not isinstance(urls, list):
                logger.warning("❌ Invalid request: urls must be an array")
                self._send_json_response(400, {
                    "status": "error",
                    "message": "urls must be an array"
                })
                return

            result = self.add_url_handler.add_urls(urls)
            summary = result["summary"]
            logger.info(f"📦 Batch add completed: {summary['queued']} queued, "
                       f"{summary['duplicates']} duplicates, {summary['errors']} errors "
                       f"(total: {summary['total']})")
            self._send_json_response(200, result)

        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON in batch request")
            self._send_json_response(400, {"status": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.exception("❌ Error handling add-urls request")
            self._send_json_response(500, {"status": "error", "message": str(e)})

    def _send_bookmarklet_script(self) -> None:
        """Serve the Bookmarklet JavaScript code."""
        script = """javascript:(function(){
var url=window.location.href;
var title=document.title;
fetch('http://127.0.0.1:8765/add-url',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({url:url,title:title,timestamp:new Date().toISOString()})
})
.then(r=>r.json())
.then(d=>{
if(d.status==='queued'){
alert('✓ Added to FlowScribe queue\\nPosition: '+d.position);
}else if(d.status==='duplicate'){
alert('⚠ Already in queue: '+d.existing_status);
}else{
alert('✗ Error: '+d.message);
}
})
.catch(e=>alert('✗ Connection failed. Is FlowScribe server running?'));
})();"""
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(script.encode("utf-8"))


class BookmarkletServer:
    """HTTP server for Bookmarklet integration."""

    def __init__(
        self,
        queue_store_path: Path,
        host: str = "127.0.0.1",
        port: int = 8765,
        status_interval: int = 30,
        default_output_dir: Path | None = None,
        default_output_formats: tuple[str, ...] = ("json",),
        default_model_name: str = "small",
        default_language: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.handler = AddUrlHandler(
            queue_store_path,
            default_output_dir=default_output_dir,
            default_output_formats=default_output_formats,
            default_model_name=default_model_name,
            default_language=default_language,
        )
        self.server: HTTPServer | None = None
        self.status_interval = status_interval
        self._status_thread: threading.Thread | None = None
        self._stop_status_thread = False

    def start(self) -> None:
        """Start the HTTP server (blocking)."""
        def handler_factory(*args, **kwargs):
            return BookmarkletRequestHandler(*args, handler=self.handler, **kwargs)

        self.server = HTTPServer((self.host, self.port), handler_factory)
        logger.info(f"🚀 FlowScribe Bookmarklet server listening on {self.host}:{self.port}")
        logger.info(f"📁 Queue store: {self.handler.queue_store_path}")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        # Start status reporting thread
        self._start_status_thread()

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            logger.info("\n⏹️  Shutting down server...")
            self.stop()

    def _start_status_thread(self) -> None:
        """Start background thread for periodic status reports."""
        def status_reporter():
            time.sleep(self.status_interval)  # Wait before first report
            while not self._stop_status_thread:
                try:
                    status = self.handler.get_status()
                    queue = status["queue"]
                    logger.info(f"📊 Queue Status: {queue['total']} total | "
                               f"{queue['pending']} pending | "
                               f"{queue['running']} running | "
                               f"{queue['completed']} completed | "
                               f"{queue['failed']} failed")
                except Exception as e:
                    logger.error(f"❌ Error getting status: {e}")

                # Sleep in small intervals to allow quick shutdown
                for _ in range(self.status_interval):
                    if self._stop_status_thread:
                        break
                    time.sleep(1)

        self._status_thread = threading.Thread(target=status_reporter, daemon=True)
        self._status_thread.start()

    def stop(self) -> None:
        """Stop the HTTP server."""
        self._stop_status_thread = True
        if self._status_thread:
            self._status_thread.join(timeout=2)

        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
