"""Proxy handling for URL media access."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from urllib.request import ProxyHandler

from flowscribe.core.errors import DownloadError


def validate_proxy_url(proxy: str | None) -> str | None:
    if proxy is None:
        return None

    value = proxy.strip()
    if not value:
        raise DownloadError("Proxy URL cannot be empty.")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "socks4", "socks5", "socks5h"}:
        raise DownloadError(
            "Proxy URL must start with http://, https://, socks4://, socks5://, or socks5h://."
        )
    if not parsed.netloc:
        raise DownloadError("Proxy URL must include a host and port, such as http://127.0.0.1:7890.")
    return value


def yt_dlp_proxy_options(proxy: str | None) -> dict:
    value = validate_proxy_url(proxy)
    return {"proxy": value} if value else {}


def proxy_handler(proxy: str | None) -> ProxyHandler | None:
    value = validate_proxy_url(proxy)
    if value is None:
        return None
    return ProxyHandler({"http": value, "https": value})


def proxy_environment(proxy: str | None) -> dict[str, str] | None:
    value = validate_proxy_url(proxy)
    if value is None:
        return None

    env = os.environ.copy()
    env["http_proxy"] = value
    env["https_proxy"] = value
    env["HTTP_PROXY"] = value
    env["HTTPS_PROXY"] = value
    return env
