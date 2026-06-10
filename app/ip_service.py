"""Public IP detection via multiple fallback sources."""
import logging

import httpx

logger = logging.getLogger(__name__)

_SOURCES = [
    "https://api.ipify.org",
    "https://api4.my-ip.io/ip",
    "https://ipv4.icanhazip.com",
]


async def detect_public_ip() -> str | None:
    for url in _SOURCES:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(url)
                ip = r.text.strip()
                if ip:
                    return ip
        except Exception as exc:
            logger.warning("IP source %s failed: %s", url, exc)
    return None
