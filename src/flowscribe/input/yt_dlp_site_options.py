"""Site-specific yt-dlp request options."""

from __future__ import annotations

from urllib.parse import urlparse

BILIBILI_HOST_SUFFIXES = ("bilibili.com", "b23.tv")


def yt_dlp_site_options(url: str) -> dict:
    hostname = (urlparse(url).hostname or "").lower()
    if hostname.endswith(BILIBILI_HOST_SUFFIXES):
        return {
            "http_headers": {
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
            }
        }
    return {}
