"""Database models and session management."""
import os
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ddns.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class DnsRecord(Base):
    __tablename__ = "dns_records"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(120), nullable=False)          # human-friendly name
    provider = Column(String(20), nullable=False)        # "godaddy" | "cloudflare"

    # GoDaddy fields
    gd_api_key = Column(String(256), nullable=True)
    gd_api_secret = Column(String(256), nullable=True)
    gd_domain = Column(String(253), nullable=True)       # e.g. example.com
    gd_record_name = Column(String(253), nullable=True)  # e.g. @ or home

    # Cloudflare fields
    cf_api_token = Column(String(256), nullable=True)
    cf_zone_id = Column(String(64), nullable=True)
    cf_record_id = Column(String(64), nullable=True)     # populated on first run
    cf_record_name = Column(String(253), nullable=True)  # e.g. home.example.com

    # API key expiry date (optional, used for alerts)
    api_key_expiry = Column(DateTime, nullable=True)

    # Runtime state
    current_ip = Column(String(45), nullable=True)
    last_updated = Column(DateTime, nullable=True)
    last_checked = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    check_interval_seconds = Column(Integer, default=300)   # 5 min default
    manual_ip = Column(String(45), nullable=True)            # override; None = auto

    # Mailjet
    mj_api_key = Column(String(256), nullable=True)
    mj_api_secret = Column(String(256), nullable=True)
    alert_from_email = Column(String(256), nullable=True)
    alert_to_email = Column(String(256), nullable=True)

    # Alert thresholds
    expiry_warning_days = Column(Integer, default=14)        # warn N days before expiry
    alert_on_ip_change = Column(Boolean, default=True)
    alert_on_update_failure = Column(Boolean, default=True)


class UpdateLog(Base):
    __tablename__ = "update_logs"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, nullable=False)
    record_label = Column(String(120), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    old_ip = Column(String(45), nullable=True)
    new_ip = Column(String(45), nullable=True)
    status = Column(String(20), nullable=False)   # "updated" | "unchanged" | "error"
    message = Column(Text, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure a default Settings row exists
    db = SessionLocal()
    try:
        if not db.query(Settings).first():
            db.add(Settings(id=1))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
