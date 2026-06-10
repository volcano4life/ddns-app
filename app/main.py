"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import DnsRecord, Settings, UpdateLog, get_db, init_db
from .email_service import send_alert
from .ip_service import detect_public_ip
from .scheduler import (
    get_last_detected_ip,
    get_next_run,
    reschedule,
    run_update_cycle,
    scheduler,
    start_scheduler,
)
from .schemas import (
    DnsRecordCreate,
    DnsRecordOut,
    DnsRecordUpdate,
    SettingsOut,
    StatusOut,
    UpdateLogOut,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Start scheduler with saved interval
    from .database import SessionLocal
    db = SessionLocal()
    try:
        s = db.query(Settings).first()
        interval = s.check_interval_seconds if s else 300
    finally:
        db.close()
    start_scheduler(interval)
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="DDNS Manager", version="1.0.0", lifespan=lifespan)

# ── Static files ────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── Status ──────────────────────────────────────────────────────────────────

@app.get("/api/status", response_model=StatusOut)
async def get_status(db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    detected = get_last_detected_ip()
    effective = (settings.manual_ip or detected) if settings else detected
    return StatusOut(
        detected_ip=detected,
        effective_ip=effective,
        scheduler_running=scheduler.running,
        next_run=get_next_run(),
    )


@app.post("/api/update-now", status_code=202)
async def trigger_update():
    asyncio.create_task(run_update_cycle())
    return {"detail": "Update triggered"}


# ── DNS Records ─────────────────────────────────────────────────────────────

@app.get("/api/records", response_model=List[DnsRecordOut])
def list_records(db: Session = Depends(get_db)):
    return db.query(DnsRecord).all()


@app.post("/api/records", response_model=DnsRecordOut, status_code=201)
def create_record(payload: DnsRecordCreate, db: Session = Depends(get_db)):
    record = DnsRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/api/records/{record_id}", response_model=DnsRecordOut)
def get_record(record_id: int, db: Session = Depends(get_db)):
    r = db.query(DnsRecord).filter(DnsRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    return r


@app.put("/api/records/{record_id}", response_model=DnsRecordOut)
def update_record(
    record_id: int, payload: DnsRecordUpdate, db: Session = Depends(get_db)
):
    r = db.query(DnsRecord).filter(DnsRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@app.delete("/api/records/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    r = db.query(DnsRecord).filter(DnsRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(r)
    db.commit()


# ── Settings ────────────────────────────────────────────────────────────────

@app.get("/api/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    s = db.query(Settings).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not initialised")
    return s


@app.put("/api/settings", response_model=SettingsOut)
def update_settings(payload: SettingsOut, db: Session = Depends(get_db)):
    s = db.query(Settings).first()
    changed_interval = False
    for k, v in payload.model_dump(exclude_unset=True).items():
        if k == "check_interval_seconds" and v != s.check_interval_seconds:
            changed_interval = True
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    if changed_interval:
        reschedule(s.check_interval_seconds)
    return s


# ── Logs ─────────────────────────────────────────────────────────────────────

@app.get("/api/logs", response_model=List[UpdateLogOut])
def get_logs(
    limit: int = 100,
    record_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(UpdateLog)
    if record_id:
        q = q.filter(UpdateLog.record_id == record_id)
    return q.order_by(UpdateLog.timestamp.desc()).limit(limit).all()


# ── Email test ───────────────────────────────────────────────────────────────

@app.post("/api/test-email")
def test_email(db: Session = Depends(get_db)):
    s = db.query(Settings).first()
    if not all([s.mj_api_key, s.mj_api_secret, s.alert_from_email, s.alert_to_email]):
        raise HTTPException(
            status_code=400,
            detail="Mailjet credentials not configured in Settings",
        )
    ok = send_alert(
        mj_api_key=s.mj_api_key,
        mj_api_secret=s.mj_api_secret,
        from_email=s.alert_from_email,
        to_email=s.alert_to_email,
        subject="[DDNS] Test email",
        text_body="This is a test email from your DDNS Manager.",
    )
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to send test email")
    return {"detail": "Test email sent"}


# ── Detect current public IP (one-shot) ─────────────────────────────────────

@app.get("/api/detect-ip")
async def detect_ip_endpoint():
    ip = await detect_public_ip()
    return {"ip": ip}
