import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from backend.routes import router as api_router
from backend.auth import router as auth_router
from backend.utils import settings
from backend.utils import setup_logger

logger = setup_logger("main_app")

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Waste Segregation & Sustainability Analytics Platform",
    version="1.0.0"
)

# BULLETPROOF CORS: Set to "*" to guarantee no browser blocking during login
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount upload directory to serve annotated images
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include REST routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(api_router, prefix="/api", tags=["EcoSort API"])

@app.get("/", include_in_schema=False)
def index_redirect():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["System Health"])
def health_check():
    """Verify backend status."""
    return {"status": "healthy", "service": settings.APP_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)