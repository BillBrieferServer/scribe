import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, Request, Depends
import bcrypt

from app.database import get_db
from app.config import settings
from app.models import RegisterRequest, VerifyRequest, LoginRequest, UserResponse
from app.email_service import send_verification_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def generate_verification_code() -> str:
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    token_hash = hash_token(token)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.email, u.name, u.email_verified 
            FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
        ''', (token_hash, datetime.utcnow().isoformat()))
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None

def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@router.post("/register")
async def register(data: RegisterRequest):
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    code = generate_verification_code()
    code_hash = hash_token(code)
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        # Check if user exists
        cursor.execute("SELECT id, email_verified FROM users WHERE email = ?", (data.email.lower(),))
        existing = cursor.fetchone()
        
        if existing:
            if existing["email_verified"]:
                raise HTTPException(status_code=400, detail="Email already registered")
            # Update existing unverified user
            cursor.execute('''
                UPDATE users SET password_hash = ?, name = ?, 
                verification_code_hash = ?, verification_expires = ?
                WHERE email = ?
            ''', (password_hash, data.name, code_hash, expires, data.email.lower()))
        else:
            cursor.execute('''
                INSERT INTO users (email, password_hash, name, verification_code_hash, verification_expires)
                VALUES (?, ?, ?, ?, ?)
            ''', (data.email.lower(), password_hash, data.name, code_hash, expires))
        
        conn.commit()
    
    if not send_verification_email(data.email, code, data.name):
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    
    return {"message": "Verification code sent to your email"}

@router.post("/verify")
async def verify(data: VerifyRequest, response: Response):
    code_hash = hash_token(data.code)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, verification_expires FROM users 
            WHERE email = ? AND verification_code_hash = ?
        ''', (data.email.lower(), code_hash))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=400, detail="Invalid verification code")
        
        if datetime.fromisoformat(user["verification_expires"]) < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Verification code expired")
        
        # Mark as verified
        cursor.execute('''
            UPDATE users SET email_verified = 1, verification_code_hash = NULL, verification_expires = NULL
            WHERE id = ?
        ''', (user["id"],))
        
        # Create session
        token = secrets.token_urlsafe(32)
        token_hash = hash_token(token)
        expires = (datetime.utcnow() + timedelta(days=settings.SESSION_EXPIRE_DAYS)).isoformat()
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        ''', (user["id"], token_hash, expires))
        
        conn.commit()
    
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.SESSION_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    return {"message": "Email verified successfully"}

@router.post("/login")
async def login(data: LoginRequest, response: Response):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, email, password_hash, name, email_verified FROM users WHERE email = ?
        ''', (data.email.lower(),))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if not bcrypt.checkpw(data.password.encode(), user["password_hash"].encode()):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if not user["email_verified"]:
            raise HTTPException(status_code=401, detail="Please verify your email first")
        
        # Create session
        token = secrets.token_urlsafe(32)
        token_hash = hash_token(token)
        expires = (datetime.utcnow() + timedelta(days=settings.SESSION_EXPIRE_DAYS)).isoformat()
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        ''', (user["id"], token_hash, expires))
        conn.commit()
    
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.SESSION_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    return {"message": "Login successful", "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}

@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        token_hash = hash_token(token)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            conn.commit()
    
    response.delete_cookie("session_token")
    return {"message": "Logged out"}

@router.get("/me")
async def me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        email_verified=bool(user["email_verified"])
    )

@router.post("/forgot-password")
async def forgot_password(data: dict):
    email = data.get("email", "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email_verified FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user or not user["email_verified"]:
            # Don't reveal if user exists
            return {"message": "If an account exists with that email, a reset code has been sent"}
        
        code = generate_verification_code()
        code_hash = hash_token(code)
        expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        
        cursor.execute('''
            UPDATE users SET reset_code_hash = ?, reset_code_expires = ?
            WHERE id = ?
        ''', (code_hash, expires, user["id"]))
        conn.commit()
    
    from app.email_service import send_reset_email
    send_reset_email(email, code, user["name"])
    
    return {"message": "If an account exists with that email, a reset code has been sent"}

@router.post("/reset-password")
async def reset_password(data: dict):
    email = data.get("email", "").lower().strip()
    code = data.get("code", "").strip()
    new_password = data.get("new_password", "")
    
    if not email or not code or not new_password:
        raise HTTPException(status_code=400, detail="Email, code, and new password are required")
    
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    code_hash = hash_token(code)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, reset_code_expires FROM users 
            WHERE email = ? AND reset_code_hash = ?
        ''', (email, code_hash))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=400, detail="Invalid reset code")
        
        if datetime.fromisoformat(user["reset_code_expires"]) < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Reset code expired")
        
        password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        
        cursor.execute('''
            UPDATE users SET password_hash = ?, reset_code_hash = NULL, reset_code_expires = NULL
            WHERE id = ?
        ''', (password_hash, user["id"]))
        conn.commit()
    
    return {"message": "Password reset successfully"}
