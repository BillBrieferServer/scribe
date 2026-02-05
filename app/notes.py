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
                             specialty, chief_complaint, raw_dictation, soap_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user["id"], note.label, note.patient_age, note.patient_gender, 
              note.visit_type, note.specialty, note.chief_complaint, 
              note.raw_dictation, note.soap_note))
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
        created_at=row["created_at"]
    )

@router.get("", response_model=List[NoteListItem])
async def list_notes(request: Request):
    user = require_auth(request)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, label, chief_complaint, created_at 
            FROM notes WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user["id"],))
        rows = cursor.fetchall()
    
    return [NoteListItem(
        id=row["id"],
        label=row["label"],
        chief_complaint=row["chief_complaint"],
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
