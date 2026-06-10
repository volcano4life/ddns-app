"""Background scheduler: IP checks, DNS updates, expiry alerts."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .database import SessionLocal, DnsRecord, Settings, UpdateLog
from .email_service import maybe_send
from .ip_service import detect_public_ip
from .providers.cloudflare import CloudflareProvider
from .providers.godaddy import GoDaddyProvider

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_last_detected_ip: str | None = None


def get_last_detected_ip() -> str | None:
    return _last_detected_ip


def _build_provider(record: DnsRecord):
    if record.provider == "godaddy":
        return GoDaddyProvider(
            api_key=record.gd_api_key,
            api_secret=record.gd_api_secret,
            domain=record.gd_domain,
            record_name=record.gd_record_name,
        )
    elif record.provider == "cloudflare":
        return CloudflareProvider(
            api_token=record.cf_api_token,
            zone_id=record.cf_zone_id,
            record_name=record.cf_record_name,
            record_id=record.cf_record_id,
        )
    raise ValueError(f"Unknown provider: {record.provider}")


async def run_update_cycle() -> None:
    global _last_detected_ip
    db = SessionLocal()
    try:
        settings: Settings | None = db.query(Settings).first()
        if not settings:
            return

        # Determine effective IP
        if settings.manual_ip:
            ip = settings.manual_ip
        else:
            ip = await detect_public_ip()
            if not ip:
                logger.error("Could not detect public IP; skipping cycle.")
                return
            _last_detected_ip = ip

        records = db.query(DnsRecord).filter(DnsRecord.enabled == True).all()  # noqa: E712

        for record in records:
            now = datetime.utcnow()
            record.last_checked = now
            try:
                provider = _build_provider(record)
                old_ip = record.current_ip

                if old_ip == ip:
                    # No change needed
                    db.add(UpdateLog(
                        record_id=record.id,
                        record_label=record.label,
                        old_ip=old_ip,
                        new_ip=ip,
                        status="unchanged",
                        message="IP unchanged",
                    ))
                else:
                    await provider.update_record(ip)

                    # Persist resolved CF record_id for next run
                    if record.provider == "cloudflare":
                        rid = getattr(provider, "resolved_record_id", None)
                        if rid:
                            record.cf_record_id = rid

                    record.current_ip = ip
                    record.last_updated = now
                    record.last_error = None
                    db.add(UpdateLog(
                        record_id=record.id,
                        record_label=record.label,
                        old_ip=old_ip,
                        new_ip=ip,
                        status="updated",
                        message=f"Updated from {old_ip} → {ip}",
                    ))

                    if settings.alert_on_ip_change:
                        maybe_send(
                            settings,
                            subject=f"[DDNS] IP changed for {record.label}",
                            body=(
                                f"Record: {record.label}\n"
                                f"Old IP: {old_ip}\n"
                                f"New IP: {ip}\n"
                                f"Time: {now.isoformat()}"
                            ),
                        )

            except Exception as exc:
                logger.error("Update failed for %s: %s", record.label, exc)
                record.last_error = str(exc)
                db.add(UpdateLog(
                    record_id=record.id,
                    record_label=record.label,
                    old_ip=record.current_ip,
                    new_ip=None,
                    status="error",
                    message=str(exc),
                ))
                if settings.alert_on_update_failure:
                    maybe_send(
                        settings,
                        subject=f"[DDNS] Update failed for {record.label}",
                        body=(
                            f"Record: {record.label}\n"
                            f"Error: {exc}\n"
                            f"Time: {now.isoformat()}"
                        ),
                    )

        # Check API key expiry dates
        _check_expiry_alerts(records, settings, db)

        db.commit()

    except Exception as exc:
        logger.exception("Unhandled error in update cycle: %s", exc)
        db.rollback()
    finally:
        db.close()


def _check_expiry_alerts(records, settings: Settings, db) -> None:
    """Send alerts for records whose API key expires soon."""
    if not settings.expiry_warning_days:
        return
    threshold = datetime.utcnow() + timedelta(days=settings.expiry_warning_days)
    for record in records:
        if record.api_key_expiry and record.api_key_expiry <= threshold:
            days_left = (record.api_key_expiry - datetime.utcnow()).days
            maybe_send(
                settings,
                subject=f"[DDNS] API key expiring soon: {record.label}",
                body=(
                    f"Record: {record.label}\n"
                    f"Provider: {record.provider}\n"
                    f"Expiry: {record.api_key_expiry.date()}\n"
                    f"Days remaining: {days_left}\n"
                    "Please update your API credentials."
                ),
            )


def start_scheduler(interval_seconds: int = 300) -> None:
    if scheduler.running:
        # Reschedule with new interval
        scheduler.reschedule_job(
            "ddns_update",
            trigger=IntervalTrigger(seconds=interval_seconds),
        )
        logger.info("Rescheduled DDNS job every %ds", interval_seconds)
        return

    scheduler.add_job(
        run_update_cycle,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id="ddns_update",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),  # run immediately on start
    )
    scheduler.start()
    logger.info("Scheduler started (every %ds)", interval_seconds)


def reschedule(interval_seconds: int) -> None:
    if scheduler.running:
        scheduler.reschedule_job(
            "ddns_update",
            trigger=IntervalTrigger(seconds=interval_seconds),
        )


def get_next_run() -> datetime | None:
    if not scheduler.running:
        return None
    job = scheduler.get_job("ddns_update")
    return job.next_run_time if job else None
