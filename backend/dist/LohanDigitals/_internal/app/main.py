import logging
import logging.handlers
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import traceback
from app.config import settings, OUTPUT_PATH
from app.routes import upload, jobs
from app.routes.auth import router as auth_router, verify_token

# --- Logging setup: console + file ---
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

log_format = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
log_level = getattr(logging, settings.log_level)

# Root logger
root_logger = logging.getLogger()
root_logger.setLevel(log_level)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(console_handler)

# Main log file — everything
file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
)
file_handler.setLevel(log_level)
file_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(file_handler)

# Error-only log file — errors and exceptions
error_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(error_handler)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Album Generator",
    version="1.0.0",
    description="Generate photo albums using AI-powered layout and story generation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for desktop app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(upload.router)
app.include_router(jobs.router)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check auth token for protected routes."""
    path = request.url.path
    # Public routes - no auth needed
    public_paths = ["/api/auth/login", "/api/health", "/docs", "/openapi.json", "/redoc"]
    if any(path.startswith(p) for p in public_paths):
        return await call_next(request)
    # OPTIONS requests (CORS preflight) - no auth
    if request.method == "OPTIONS":
        return await call_next(request)
    # Check token for all other /api/ routes
    if path.startswith("/api/"):
        # Check Authorization header first
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
        # Fallback: check query param (for img src, downloads)
        if not token:
            token = request.query_params.get("token")
        if not token:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        from app.routes.auth import _active_tokens
        import time as _time
        if token not in _active_tokens or _time.time() > _active_tokens.get(token, 0):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request and catch unhandled exceptions."""
    logger.info("%s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            logger.warning(
                "%s %s -> %d", request.method, request.url.path, response.status_code
            )
        return response
    except Exception as e:
        logger.error(
            "Unhandled exception on %s %s:\n%s",
            request.method, request.url.path, traceback.format_exc(),
        )
        return JSONResponse(status_code=500, content={"detail": str(e)})

# Serve output files (images for preview)
app.mount("/output", StaticFiles(directory=str(OUTPUT_PATH)), name="output")

# Serve frontend static files (built Next.js export)
FRONTEND_DIR = Path(__file__).parent.parent / "static"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# Run cleanup on startup
@app.on_event("startup")
async def startup_cleanup():
    from app.services.cleanup import cleanup_old_files
    logger.info("Running startup file cleanup...")
    cleanup_old_files()
