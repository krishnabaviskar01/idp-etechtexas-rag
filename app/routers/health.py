"""
Health and root endpoints router
"""
from fastapi import APIRouter
from app.config import settings
from app.schemas.health import RootResponse, HealthResponse

router = APIRouter(prefix="", tags=["health"])


@router.get("/", response_model=RootResponse)
async def root():
    """Root endpoint"""
    return RootResponse(
        message=f"Welcome to {settings.APP_NAME}",
        version=settings.APP_VERSION,
        status="running"
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    from app.services.service_manager import gdrive_service
    
    return HealthResponse(
        status="healthy",
        gdrive_service="available" if gdrive_service else "unavailable"
    )

