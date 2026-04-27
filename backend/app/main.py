from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.config import settings
from app.database import create_tables
from app.routers import channels, ideas, projects, visuals, audio, video, export, islamic

app = FastAPI(title="VidFlow API", version="1.0.0", description="Internal YouTube video production platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for d in [settings.UPLOAD_DIR, settings.OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

app.include_router(channels.router, prefix="/api")
app.include_router(ideas.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(visuals.router, prefix="/api")
app.include_router(audio.router, prefix="/api")
app.include_router(video.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(islamic.router, prefix="/api")

upload_dir = settings.UPLOAD_DIR
os.makedirs(upload_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=upload_dir), name="static")


@app.on_event("startup")
async def startup():
    await create_tables()


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
async def root():
    return {"message": "VidFlow API is running", "docs": "/docs"}
