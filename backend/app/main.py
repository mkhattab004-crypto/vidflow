import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import create_tables, engine
from app.logging_config import setup_logging
from app.routers import channels, ideas, projects, visuals, audio, video, export, islamic
from app.routers import automation, thumbnail

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_is_prod = os.getenv("RAILWAY_ENVIRONMENT") is not None
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    json_logs=_is_prod,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VidFlow starting up...")
    for d in [settings.UPLOAD_DIR, settings.OUTPUT_DIR]:
        os.makedirs(d, exist_ok=True)
    try:
        await create_tables()
        logger.info("Database tables ready")
    except Exception as e:
        logger.warning(f"Database unavailable on startup: {e}")
        logger.warning("Add a PostgreSQL service to Railway and set DATABASE_URL to enable DB features.")
    yield
    logger.info("VidFlow shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="VidFlow API",
    version="1.0.0",
    description="Internal YouTube video production platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.1f}ms)")
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

PREFIX = "/api"
app.include_router(channels.router,    prefix=PREFIX)
app.include_router(ideas.router,       prefix=PREFIX)
app.include_router(projects.router,    prefix=PREFIX)
app.include_router(visuals.router,     prefix=PREFIX)
app.include_router(audio.router,       prefix=PREFIX)
app.include_router(video.router,       prefix=PREFIX)
app.include_router(export.router,      prefix=PREFIX)
app.include_router(islamic.router,     prefix=PREFIX)
app.include_router(automation.router,  prefix=PREFIX)
app.include_router(thumbnail.router,   prefix=PREFIX)

# Static file serving — create the dir first so StaticFiles doesn't crash on import
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")


# ---------------------------------------------------------------------------
# Health + root
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["system"])
async def health():
    db_ok = False
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "db": "connected" if db_ok else "disconnected — add PostgreSQL on Railway",
        "version": "1.0.0",
        "environment": "production" if _is_prod else "development",
    }


@app.get("/", tags=["system"])
async def root():
    return {"message": "VidFlow API", "docs": "/docs", "health": "/api/health"}
