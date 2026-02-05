from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# Auth models
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class VerifyRequest(BaseModel):
    email: str
    code: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    email_verified: bool

# Note models
class NoteCreate(BaseModel):
    label: Optional[str] = None
    patient_age: Optional[str] = None
    patient_gender: Optional[str] = None
    visit_type: Optional[str] = None
    specialty: Optional[str] = None
    chief_complaint: Optional[str] = None
    raw_dictation: Optional[str] = None
    soap_note: Optional[str] = None

class NoteResponse(BaseModel):
    id: int
    label: Optional[str]
    patient_age: Optional[str]
    patient_gender: Optional[str]
    visit_type: Optional[str]
    specialty: Optional[str]
    chief_complaint: Optional[str]
    raw_dictation: Optional[str]
    soap_note: Optional[str]
    created_at: str

class NoteListItem(BaseModel):
    id: int
    label: Optional[str]
    chief_complaint: Optional[str]
    created_at: str

# Generate models
class ExtractRequest(BaseModel):
    dictation: str

class ExtractResponse(BaseModel):
    gender: Optional[str]
    age: Optional[str]
    visitType: Optional[str]
    specialty: Optional[str]
    chiefComplaint: Optional[str]
    confidence: float

class GenerateRequest(BaseModel):
    dictation: str
    gender: Optional[str] = None
    age: Optional[str] = None
    visitType: Optional[str] = None
    specialty: Optional[str] = None
    chiefComplaint: Optional[str] = None

class GenerateResponse(BaseModel):
    soap_note: str
