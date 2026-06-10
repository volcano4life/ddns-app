"""Abstract base for DNS providers."""
from abc import ABC, abstractmethod


class DNSProvider(ABC):
    @abstractmethod
    async def update_record(self, ip: str) -> None:
        """Update the DNS A record to *ip*.  Raises on failure."""
        ...

    @abstractmethod
    async def get_current_record_ip(self) -> str | None:
        """Return the IP currently set in DNS, or None if not found."""
        ...
