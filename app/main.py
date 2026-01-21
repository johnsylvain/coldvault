"""
ColdVault - Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api import jobs, backups, restore, dashboard, notifications, test_upload, diagnostics
from app.database import engine, Base
from app.scheduler import scheduler
from app.config import settings

# Create database tables
Base.metadata.create_all(bind=engine)

# Run migrations
from app.database import migrate_database
migrate_database()

app = FastAPI(
    title="ColdVault",
    description="Self-Hosted Scheduled Backups to AWS Cold Storage",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(backups.router, prefix="/api/backups", tags=["backups"])
app.include_router(restore.router, prefix="/api/restore", tags=["restore"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(test_upload.router, prefix="/api", tags=["test"])
app.include_router(diagnostics.router, prefix="/api", tags=["diagnostics"])

# Serve static files (dashboard UI)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    # Create static directory if it doesn't exist
    os.makedirs(static_dir, exist_ok=True)

@app.get("/")
async def root():
    """Serve dashboard"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "ColdVault API", "version": "1.0.0"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Initialize scheduler on startup"""
    # Worker recovery happens in __init__, but we can also trigger it explicitly
    from app.worker import backup_worker
    backup_worker._recover_orphaned_backups()
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    scheduler.stop()
