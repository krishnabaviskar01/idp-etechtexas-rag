"""
FastAPI application main file
"""
import uvicorn
from fastapi import FastAPI

from app.config import settings
from app.logger import initialize_logger
from app.services.gdrive_service import GoogleDriveService
from app.services.service_manager import set_gdrive_service
from app.routers import health, upload

# Initialize logger
logger = initialize_logger()


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI application for uploading files to Google Drive",
    debug=settings.DEBUG
)

# Include routers
app.include_router(health.router)
app.include_router(upload.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Build client config from environment variables
        client_config = {
            'client_id': settings.GOOGLE_DRIVE_CLIENT_ID,
            'client_secret': settings.GOOGLE_DRIVE_CLIENT_SECRET,
            'project_id': settings.GOOGLE_DRIVE_PROJECT_ID,
            'auth_uri': settings.GOOGLE_DRIVE_AUTH_URI,
            'token_uri': settings.GOOGLE_DRIVE_TOKEN_URI,
            'auth_provider_x509_cert_url': settings.GOOGLE_DRIVE_AUTH_PROVIDER_X509_CERT_URL,
            'redirect_uris': settings.GOOGLE_DRIVE_REDIRECT_URIS
        }
        
        # Initialize and set the global service
        initialized_service = GoogleDriveService(
            client_config=client_config,
            token_file=settings.GOOGLE_DRIVE_TOKEN_FILE
        )
        set_gdrive_service(initialized_service)
        
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}")
        logger.warning("Application started but Google Drive service is unavailable")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Application shutting down")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_config=None  # Use loguru instead
    )

