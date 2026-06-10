"""Cloudflare DNS provider via API v4."""
import httpx

from .base import DNSProvider

_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareProvider(DNSProvider):
    def __init__(
        self,
        api_token: str,
        zone_id: str,
        record_name: str,
        record_id: str | None = None,
        ttl: int = 1,       # 1 = automatic in CF
        proxied: bool = False,
    ):
        self.api_token = api_token
        self.zone_id = zone_id
        self.record_name = record_name
        self._record_id = record_id
        self.ttl = ttl
        self.proxied = proxied

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def _resolve_record_id(self) -> str:
        """Look up the DNS record ID by name (cached after first call)."""
        if self._record_id:
            return self._record_id
        url = f"{_BASE}/zones/{self.zone_id}/dns_records"
        params = {"type": "A", "name": self.record_name}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=self._headers, params=params)
            r.raise_for_status()
            results = r.json().get("result", [])
            if not results:
                raise RuntimeError(
                    f"Cloudflare: no A record found for '{self.record_name}'"
                )
            self._record_id = results[0]["id"]
            return self._record_id

    async def get_current_record_ip(self) -> str | None:
        rid = await self._resolve_record_id()
        url = f"{_BASE}/zones/{self.zone_id}/dns_records/{rid}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            return r.json()["result"].get("content")

    async def update_record(self, ip: str) -> None:
        rid = await self._resolve_record_id()
        url = f"{_BASE}/zones/{self.zone_id}/dns_records/{rid}"
        payload = {
            "type": "A",
            "name": self.record_name,
            "content": ip,
            "ttl": self.ttl,
            "proxied": self.proxied,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(url, json=payload, headers=self._headers)
            data = r.json()
            if not data.get("success"):
                errors = data.get("errors", [])
                raise RuntimeError(f"Cloudflare API error: {errors}")

    @property
    def resolved_record_id(self) -> str | None:
        return self._record_id
