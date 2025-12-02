# =============================================================================
# backend/app/main.py
# =============================================================================
# This is the entry point for the FastAPI backend. It sets up the web server,
# configures CORS (Cross-Origin Resource Sharing) to allow the frontend to
# communicate with the backend, and includes all the API routes.
#
# When you run `uvicorn app.main:app`, Python loads this file and starts
# the server using the `app` object we create here.
# =============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import our route modules - these contain the actual API endpoints
from app.routes import optimizer

# =============================================================================
# Create the FastAPI Application
# =============================================================================
# The FastAPI() call creates our web application. The parameters here provide
# metadata that shows up in the auto-generated documentation at /docs.

app = FastAPI(
    title="Bar Hopping Optimizer API",
    description="""
    An intelligent bar hopping assistant for Lubbock, TX.
    
    Features:
    - Natural language understanding for casual requests
    - Route optimization to minimize wait times  
    - Fine-tuned LLM for conversational responses
    
    Try requests like: "yo let's hit chimys and crickets at 9pm"
    """,
    version="1.0.0",
    docs_url="/docs",      # Swagger UI documentation
    redoc_url="/redoc"     # ReDoc documentation
)

# =============================================================================
# CORS Configuration
# =============================================================================
# CORS (Cross-Origin Resource Sharing) is a security feature in browsers.
# By default, a webpage can only make requests to the same domain it was 
# loaded from. Since our frontend (Vercel) and backend (Railway) are on
# different domains, we need to explicitly allow the frontend to connect.
#
# The ALLOWED_ORIGINS environment variable should contain a comma-separated
# list of frontend URLs that are allowed to access this API.

# Get allowed origins from environment, with defaults for local development
allowed_origins_str = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
)
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_str.split(",")]

# Add the CORS middleware to our application
# Middleware is code that runs on every request before it reaches our routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Which domains can access the API
    allow_credentials=True,          # Allow cookies and auth headers
    allow_methods=["*"],            # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],            # Allow all headers
)

# =============================================================================
# Include Route Modules
# =============================================================================
# Routes are organized in separate files for cleaner code. We include them
# here with a prefix - all routes in the optimizer module will start with /api
# For example: POST /api/optimize, GET /api/bars

app.include_router(
    optimizer.router,
    prefix="/api",
    tags=["optimizer"]  # Groups these endpoints together in the docs
)

# =============================================================================
# Root Endpoints
# =============================================================================
# These basic endpoints help verify the API is running. The health endpoint
# is particularly important - Railway uses it to check if the service is alive.

@app.get("/", tags=["status"])
async def root():
    """
    Root endpoint - confirms the API is running.
    Visit this URL to quickly check if the server started successfully.
    """
    return {
        "message": "Bar Hopping Optimizer API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["status"])
async def health_check():
    """
    Health check endpoint for deployment platforms.
    Railway and other hosting services ping this URL periodically to verify
    the service is healthy. If it returns anything other than 200 OK,
    the service may be restarted.
    """
    return {
        "status": "healthy",
        "service": "bar-hopping-api"
    }


# =============================================================================
# Development Mode Entry Point
# =============================================================================
# This block allows running the server directly with `python main.py`
# In production, you'll use uvicorn directly instead, but this is convenient
# for quick testing during development.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload when code changes (dev only)
    )
