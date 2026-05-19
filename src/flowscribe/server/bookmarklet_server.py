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
        """Serve the enhanced Bookmarklet JavaScript code."""
        script = """javascript:(function(){'use strict';const c={serverUrl:'http://127.0.0.1:8765',timeout:5000,notificationDuration:3000};function extractUrl(){const u=window.location.href,h=window.location.hostname;if(h.includes('youtube.com')||h.includes('youtu.be')){if(u.includes('youtu.be/')){const m=u.match(/youtu\\.be\\/([a-zA-Z0-9_-]+)/);if(m)return`https://www.youtube.com/watch?v=${m[1]}`}if(u.includes('youtube.com/watch')){const o=new URL(u),v=o.searchParams.get('v');if(v)return`https://www.youtube.com/watch?v=${v}`}if(u.includes('youtube.com/embed/')){const m=u.match(/youtube\\.com\\/embed\\/([a-zA-Z0-9_-]+)/);if(m)return`https://www.youtube.com/watch?v=${m[1]}`}}if(h.includes('bilibili.com')){const b=u.match(/BV[a-zA-Z0-9]+/);if(b)return`https://www.bilibili.com/video/${b[0]}`;const a=u.match(/av(\\d+)/);if(a)return`https://www.bilibili.com/video/av${a[1]}`}return u}function extractTitle(){let t=document.title.trim();if(!t){const o=document.querySelector('meta[property="og:title"]');if(o)t=o.getAttribute('content')||''}if(!t){const h=document.querySelector('h1');if(h)t=h.textContent.trim()}const s=[/ - YouTube$/,/ - Bilibili$/,/ - 哔哩哔哩$/,/ \\| Bilibili$/,/ \\| 哔哩哔哩$/];for(const r of s)t=t.replace(r,'');return t.trim()||'Untitled'}function showNotification(m,t='success'){const e=document.getElementById('flowscribe-notification');if(e)e.remove();const n=document.createElement('div');n.id='flowscribe-notification';const bg={'success':'linear-gradient(135deg, #667eea 0%, #764ba2 100%)','error':'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)','warning':'linear-gradient(135deg, #ffa751 0%, #ffe259 100%)','info':'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'}[t]||'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';const ic={'success':'✓','error':'✗','warning':'⚠','info':'ℹ'}[t]||'ℹ';n.innerHTML=`<div style="position:fixed;top:20px;right:20px;z-index:999999;background:${bg};color:white;padding:16px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;line-height:1.5;max-width:400px;animation:flowscribe-slide-in 0.3s ease-out"><div style="display:flex;align-items:center;gap:12px"><div style="font-size:24px;flex-shrink:0">${ic}</div><div style="flex:1"><div style="font-weight:600;margin-bottom:4px">FlowScribe</div><div style="opacity:0.95">${m}</div></div></div></div>`;if(!document.getElementById('flowscribe-styles')){const s=document.createElement('style');s.id='flowscribe-styles';s.textContent='@keyframes flowscribe-slide-in{from{transform:translateX(400px);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes flowscribe-fade-out{from{opacity:1}to{opacity:0;transform:translateX(400px)}}';document.head.appendChild(s)}document.body.appendChild(n);setTimeout(()=>{n.firstElementChild.style.animation='flowscribe-fade-out 0.3s ease-out';setTimeout(()=>n.remove(),300)},c.notificationDuration)}function fetchWithTimeout(u,o,t){return Promise.race([fetch(u,o),new Promise((_,r)=>setTimeout(()=>r(new Error('Request timeout')),t))])}async function addToFlowScribe(){try{const u=extractUrl(),t=extractTitle();if(!u||!u.startsWith('http')){showNotification('Invalid URL format','error');return}showNotification('Adding to queue...','info');const r=await fetchWithTimeout(`${c.serverUrl}/add-url`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:u,title:t,timestamp:new Date().toISOString()})},c.timeout);const d=await r.json();if(d.status==='queued'){showNotification(`Added: ${t}\\nQueue position: ${d.position}`,'success')}else if(d.status==='duplicate'){showNotification(`Already in queue: ${d.existing_status}\\n${t}`,'warning')}else{showNotification(`Error: ${d.message}`,'error')}}catch(e){if(e.message==='Request timeout'){showNotification('Connection timeout (5s)\\nIs FlowScribe server running?','error')}else if(e.message.includes('Failed to fetch')){showNotification('Cannot connect to FlowScribe\\nPlease start the server first','error')}else{showNotification(`Unexpected error: ${e.message}`,'error')}}}addToFlowScribe()})();"""
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
