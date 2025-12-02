# =============================================================================
# backend/app/main.py - FIXED CORS (accepts ALL origins)
# =============================================================================

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

from app.routes import optimizer

# =============================================================================
# Create the FastAPI Application
# =============================================================================

app = FastAPI(
    title="Bar Hopping Optimizer API",
    description="An intelligent bar hopping assistant for Lubbock, TX.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# =============================================================================
# CORS Configuration - ALLOW ALL ORIGINS
# =============================================================================
# This fixes the CORS errors by allowing any frontend URL to connect.
# For production, you would want to restrict this, but for demo it's fine.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # Allow ALL origins
    allow_credentials=False,           # Must be False when using "*"
    allow_methods=["*"],              # Allow all HTTP methods
    allow_headers=["*"],              # Allow all headers
    expose_headers=["*"],             # Expose all headers to frontend
)

# =============================================================================
# Include Route Modules
# =============================================================================

app.include_router(
    optimizer.router,
    prefix="/api",
    tags=["optimizer"]
)

# =============================================================================
# Root Endpoints
# =============================================================================

@app.get("/", tags=["status"])
async def root():
    """Root endpoint - confirms the API is running."""
    return {
        "message": "Bar Hopping Optimizer API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["status"])
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "service": "bar-hopping-api"
    }


# =============================================================================
# Development Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
