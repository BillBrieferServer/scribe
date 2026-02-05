from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from openai import OpenAI
import os
import tempfile

router = APIRouter(prefix="/api", tags=["transcribe"])

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@router.post("/transcribe")
async def transcribe_audio(request: Request, audio: UploadFile = File(...)):
    """Transcribe audio using OpenAI Whisper API"""
    
    # Check authentication (not async)
    from app.auth import get_current_user
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Read file content
    content = await audio.read()
    
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="Audio file too small")
    
    if len(content) > 25 * 1024 * 1024:  # 25MB limit
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")
    
    # Determine extension from content type
    content_type = audio.content_type or ""
    ext = ".webm"
    if "mp4" in content_type or "m4a" in content_type:
        ext = ".m4a"
    elif "mpeg" in content_type or "mp3" in content_type:
        ext = ".mp3"
    elif "wav" in content_type:
        ext = ".wav"
    elif "ogg" in content_type:
        ext = ".ogg"
    
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        # Call Whisper API
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                response_format="text"
            )
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        return {"text": transcript.strip() if isinstance(transcript, str) else str(transcript)}
        
    except Exception as e:
        # Clean up on error
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
