"""GoDaddy DNS provider via OTE/Production API v1."""
import httpx

from .base import DNSProvider

_BASE = "https://api.godaddy.com/v1"


class GoDaddyProvider(DNSProvider):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        domain: str,
        record_name: str,
        ttl: int = 600,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.domain = domain
        self.record_name = record_name
        self.ttl = ttl

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"sso-key {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
        }

    async def get_current_record_ip(self) -> str | None:
        url = f"{_BASE}/domains/{self.domain}/records/A/{self.record_name}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            data = r.json()
            if data:
                return data[0].get("data")
        return None

    async def update_record(self, ip: str) -> None:
        url = f"{_BASE}/domains/{self.domain}/records/A/{self.record_name}"
        payload = [{"data": ip, "ttl": self.ttl}]
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(url, json=payload, headers=self._headers)
            if r.status_code not in (200, 204):
                raise RuntimeError(
                    f"GoDaddy API error {r.status_code}: {r.text}"
                )
