from typing import List
from fastapi import APIRouter, HTTPException, Request, Depends

from app.database import get_db
from app.auth import require_auth
from app.models import NoteCreate, NoteResponse, NoteListItem

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.post("", response_model=NoteResponse)
async def create_note(note: NoteCreate, request: Request):
    user = require_auth(request)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notes (user_id, label, patient_age, patient_gender, visit_type, 
                             specialty, chief_complaint, raw_dictation, soap_note, encounter_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user["id"], note.label, note.patient_age, note.patient_gender, 
              note.visit_type, note.specialty, note.chief_complaint, 
              note.raw_dictation, note.soap_note, note.encounter_time))
        conn.commit()
        note_id = cursor.lastrowid
        
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
    
    return NoteResponse(
        id=row["id"],
        label=row["label"],
        patient_age=row["patient_age"],
        patient_gender=row["patient_gender"],
        visit_type=row["visit_type"],
        specialty=row["specialty"],
        chief_complaint=row["chief_complaint"],
        raw_dictation=row["raw_dictation"],
        soap_note=row["soap_note"],
        encounter_time=row["encounter_time"],
        created_at=row["created_at"]
    )

@router.get("", response_model=List[NoteListItem])
async def list_notes(request: Request):
    user = require_auth(request)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, label, patient_age, patient_gender, chief_complaint, encounter_time, created_at 
            FROM notes WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user["id"],))
        rows = cursor.fetchall()
    
    return [NoteListItem(
        id=row["id"],
        label=row["label"],
        patient_age=row["patient_age"],
        patient_gender=row["patient_gender"],
        chief_complaint=row["chief_complaint"],
        encounter_time=row["encounter_time"],
        created_at=row["created_at"]
    ) for row in rows]

@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: int, request: Request):
    user = require_auth(request)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user["id"]))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    
    return NoteResponse(
        id=row["id"],
        label=row["label"],
        patient_age=row["patient_age"],
        patient_gender=row["patient_gender"],
        visit_type=row["visit_type"],
        specialty=row["specialty"],
        chief_complaint=row["chief_complaint"],
        raw_dictation=row["raw_dictation"],
        soap_note=row["soap_note"],
        encounter_time=row["encounter_time"],
        created_at=row["created_at"]
    )

@router.delete("/{note_id}")
async def delete_note(note_id: int, request: Request):
    user = require_auth(request)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user["id"]))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        conn.commit()
    
    return {"message": "Note deleted"}

from datetime import datetime, timedelta
from app.email_service import send_soap_note_email

# Simple in-memory rate limiting
email_counts = {}  # {user_id: [(timestamp, note_id), ...]}

def check_rate_limit(user_id: int, note_id: int) -> tuple[bool, str]:
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    
    if user_id not in email_counts:
        email_counts[user_id] = []
    
    # Clean old entries
    email_counts[user_id] = [(ts, nid) for ts, nid in email_counts[user_id] if ts > hour_ago]
    
    # Check per-note limit (3 per note)
    note_emails = sum(1 for ts, nid in email_counts[user_id] if nid == note_id)
    if note_emails >= 3:
        return False, "Maximum 3 emails per note reached"
    
    # Check per-hour limit (20 per user per hour)
    if len(email_counts[user_id]) >= 20:
        return False, "Maximum 20 emails per hour reached"
    
    return True, ""

def record_email(user_id: int, note_id: int):
    if user_id not in email_counts:
        email_counts[user_id] = []
    email_counts[user_id].append((datetime.utcnow(), note_id))

@router.post("/{note_id}/email")
async def email_note(note_id: int, request: Request):
    user = require_auth(request)
    
    # Check rate limits
    allowed, msg = check_rate_limit(user["id"], note_id)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user["id"]))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Build subject line from note metadata
    parts = []
    if row["encounter_time"]:
        try:
            dt = datetime.fromisoformat(row["encounter_time"].replace("Z", "+00:00"))
            parts.append(dt.strftime("%-I:%M %p"))
        except:
            pass
    if row["patient_age"]:
        gender_char = row["patient_gender"][0].upper() if row["patient_gender"] else ""
        parts.append(f"{row['patient_age']}{gender_char}")
    if row["chief_complaint"]:
        parts.append(row["chief_complaint"][:30])
    
    subject = "Scribe Note"
    if parts:
        subject += " — " + " · ".join(parts)
    
    # Send email
    if not send_soap_note_email(user["email"], subject, row["soap_note"]):
        raise HTTPException(status_code=500, detail="Failed to send email")
    
    record_email(user["id"], note_id)
    
    return {"message": "Email sent"}
