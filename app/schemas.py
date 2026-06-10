"""Pydantic schemas for API request/response."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class DnsRecordBase(BaseModel):
    label: str
    provider: str
    enabled: bool = True
    api_key_expiry: Optional[datetime] = None

    # GoDaddy
    gd_api_key: Optional[str] = None
    gd_api_secret: Optional[str] = None
    gd_domain: Optional[str] = None
    gd_record_name: Optional[str] = None

    # Cloudflare
    cf_api_token: Optional[str] = None
    cf_zone_id: Optional[str] = None
    cf_record_name: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def provider_valid(cls, v: str) -> str:
        if v not in ("godaddy", "cloudflare"):
            raise ValueError("provider must be 'godaddy' or 'cloudflare'")
        return v


class DnsRecordCreate(DnsRecordBase):
    pass


class DnsRecordUpdate(DnsRecordBase):
    pass


class DnsRecordOut(DnsRecordBase):
    id: int
    current_ip: Optional[str] = None
    last_updated: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SettingsBase(BaseModel):
    check_interval_seconds: int = 300
    manual_ip: Optional[str] = None
    mj_api_key: Optional[str] = None
    mj_api_secret: Optional[str] = None
    alert_from_email: Optional[str] = None
    alert_to_email: Optional[str] = None
    expiry_warning_days: int = 14
    alert_on_ip_change: bool = True
    alert_on_update_failure: bool = True


class SettingsOut(SettingsBase):
    model_config = {"from_attributes": True}


class UpdateLogOut(BaseModel):
    id: int
    record_id: int
    record_label: str
    timestamp: datetime
    old_ip: Optional[str] = None
    new_ip: Optional[str] = None
    status: str
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class StatusOut(BaseModel):
    detected_ip: Optional[str]
    effective_ip: Optional[str]
    scheduler_running: bool
    next_run: Optional[datetime]
