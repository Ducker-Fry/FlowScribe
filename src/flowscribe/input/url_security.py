"""Safety checks for remote URL inputs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from flowscribe.core.errors import DownloadError


def validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise DownloadError("URL input only supports http and https URLs.")
    if not parsed.hostname:
        raise DownloadError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise DownloadError("URL credentials are not allowed.")

    host = parsed.hostname.strip().lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise DownloadError("Localhost URLs are blocked for safety.")

    try:
        addresses = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DownloadError(f"Could not resolve URL host: {host}") from exc

    if not addresses:
        raise DownloadError(f"Could not resolve URL host: {host}")

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if _is_blocked_ip(ip):
            raise DownloadError(f"URL host resolves to a blocked network address: {ip}")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
