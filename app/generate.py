import json
from fastapi import APIRouter, HTTPException, Request
import anthropic

from app.config import settings
from app.auth import require_auth
from app.models import ExtractRequest, ExtractResponse, GenerateRequest, GenerateResponse

router = APIRouter(prefix="/api/generate", tags=["generate"])

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

EXTRACT_SYSTEM_PROMPT = """You are a medical transcription assistant. Analyze the following physician dictation and extract patient demographics and visit information.

Return a JSON object with these fields:
- gender: "Male", "Female", or null if not mentioned
- age: Patient age as string (e.g., "45", "3 months") or null if not mentioned
- visitType: One of "New Patient", "Follow-up", "Annual Exam", "Urgent", "Consultation", or null if unclear
- specialty: Medical specialty if apparent (e.g., "Family Medicine", "Cardiology", "Pediatrics") or null
- chiefComplaint: Brief chief complaint (e.g., "chest pain", "annual wellness") or null
- confidence: Float 0-1 indicating overall confidence in extractions

Only return valid JSON, no other text."""

SOAP_SYSTEM_PROMPT = """You are a medical scribe assistant helping physicians create SOAP notes from their dictations.

Generate a properly formatted SOAP note following this structure:

**SUBJECTIVE**
- Chief Complaint (CC)
- History of Present Illness (HPI)
- Review of Systems (ROS)
- Past Medical History (PMH) if mentioned
- Medications if mentioned
- Allergies if mentioned
- Social/Family History if mentioned

**OBJECTIVE**
- Vital Signs if mentioned
- Physical Exam findings
- Lab/Imaging results if mentioned

**ASSESSMENT**
- Primary diagnosis or differential diagnoses
- Problem list

**PLAN**
- Treatment plan
- Medications prescribed/changed
- Follow-up instructions
- Patient education
- Referrals if applicable

Guidelines:
- Use professional medical terminology
- Be concise but complete
- Include only information explicitly stated or clearly implied
- Use standard medical abbreviations appropriately
- Format with clear sections and bullet points
- If information for a section is not provided, omit that section
- Do not fabricate or assume information not in the dictation"""

@router.post("/extract", response_model=ExtractResponse)
async def extract_demographics(data: ExtractRequest, request: Request):
    require_auth(request)
    
    if not data.dictation or len(data.dictation.strip()) < 10:
        raise HTTPException(status_code=400, detail="Dictation too short")
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": data.dictation}]
        )
        
        result_text = response.content[0].text.strip()
        # Handle potential markdown code blocks
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
        result_text = result_text.strip()
        
        result = json.loads(result_text)
        
        return ExtractResponse(
            gender=result.get("gender"),
            age=result.get("age"),
            visitType=result.get("visitType"),
            specialty=result.get("specialty"),
            chiefComplaint=result.get("chiefComplaint"),
            confidence=float(result.get("confidence", 0.5))
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {e}")
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {e}")

@router.post("/soap", response_model=GenerateResponse)
async def generate_soap(data: GenerateRequest, request: Request):
    require_auth(request)
    
    if not data.dictation or len(data.dictation.strip()) < 10:
        raise HTTPException(status_code=400, detail="Dictation too short")
    
    # Build context from demographics
    context_parts = []
    if data.gender:
        context_parts.append(f"Patient Gender: {data.gender}")
    if data.age:
        context_parts.append(f"Patient Age: {data.age}")
    if data.visitType:
        context_parts.append(f"Visit Type: {data.visitType}")
    if data.specialty:
        context_parts.append(f"Specialty: {data.specialty}")
    if data.chiefComplaint:
        context_parts.append(f"Chief Complaint: {data.chiefComplaint}")
    
    context = "\n".join(context_parts) if context_parts else ""
    
    user_message = f"""Patient Context:
{context}

Physician Dictation:
{data.dictation}

Please generate a complete SOAP note from this dictation."""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SOAP_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        
        soap_note = response.content[0].text.strip()
        return GenerateResponse(soap_note=soap_note)
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {e}")
