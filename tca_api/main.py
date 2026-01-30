"""
TCA RCA Agent - FastAPI Application
Main entry point for the API server
"""

import sys
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import configuration
from tca_core.config import validate_env

# Import routes
from tca_api.routes import rca, webhooks, discovery
from tca_api.models import HealthResponse

# Validate environment on startup
try:
    validate_env()
except Exception as e:
    print(f"⚠️  Environment validation warning: {e}")
    print("   Server may not function correctly without proper configuration")

# Create FastAPI app
app = FastAPI(
    title="TCA RCA Agent",
    description="AI-Powered Root Cause Analysis for Sentry Issues",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (allow dashboard to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dashboard
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        # Add production URLs when deployed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rca.router)
app.include_router(webhooks.router)
app.include_router(discovery.router)


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns server status and configuration info.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "TCA RCA Agent API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "analyze": "POST /api/rca/analyze",
            "stream": "GET /api/rca/stream/{analysis_id}",
            "history": "GET /api/rca/history",
            "stats": "GET /api/rca/stats",
            "create_pr": "POST /api/rca/{analysis_id}/create-pr",
            "scan_sentry": "POST /api/discovery/scan",
            "view_queue": "GET /api/discovery/queue",
            "webhook": "POST /api/webhooks/github",
        },
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("\n" + "=" * 70)
    print("TCA RCA Agent - Starting")
    print("=" * 70)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print("=" * 70)
    print("\n✅ Server started successfully")
    print("   API docs: http://localhost:8000/docs")
    print("   Health check: http://localhost:8000/health")
    print("\n")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("\n👋 TCA RCA Agent - Shutting down")


# Error handler for uncaught exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    return {
        "error": "Internal server error",
        "message": str(exc),
        "path": str(request.url),
    }


if __name__ == "__main__":
    # Run with uvicorn for development
    import uvicorn

    uvicorn.run(
        "tca_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
