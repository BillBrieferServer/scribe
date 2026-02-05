from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from contextlib import asynccontextmanager

from app.database import init_db
from app.auth import router as auth_router
from app.notes import router as notes_router
from app.generate import router as generate_router
from app.transcribe import router as transcribe_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="QIScribe", lifespan=lifespan)

# Include routers
app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(generate_router)
app.include_router(transcribe_router)

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html for root and any non-API routes (SPA)
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html", media_type="text/html")

@app.get("/{path:path}")
async def catch_all(path: str):
    if not path.startswith("api/"):
        return FileResponse("static/index.html", media_type="text/html")
