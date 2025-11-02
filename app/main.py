"""
FastAPI application main file
"""
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logger import initialize_logger
from app.services.gdrive_service import GoogleDriveService
from app.services.mongodb_service import MongoDBService
from app.services.service_manager import set_gdrive_service, set_mongodb_service
from app.routers import health, upload, ocr, ingestion, chat
from app.langgraph import build_chat_graph

# Initialize logger
logger = initialize_logger()


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI application for uploading files to Google Drive",
    debug=settings.DEBUG
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to specific origins when done testing
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(ocr.router)
app.include_router(ingestion.router)
app.include_router(chat.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    # Initialize Google Drive service
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
        logger.info("Google Drive service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}")
        logger.warning("Application started but Google Drive service is unavailable")
    
    # Initialize MongoDB service
    try:
        mongodb_service = MongoDBService(
            database_name=settings.MONGODB_DATABASE
        )
        set_mongodb_service(mongodb_service)
        logger.info("MongoDB service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB service: {e}")
        logger.warning("Application started but MongoDB service is unavailable")
    
    # Compile LangGraph chat workflow
    try:
        app.state.chat_graph = build_chat_graph()
        logger.info("Chat workflow graph compiled successfully")
    except Exception as e:
        logger.error(f"Failed to compile chat workflow graph: {e}")
        app.state.chat_graph = None

    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    from app.services.service_manager import mongodb_service
    if mongodb_service:
        mongodb_service.close()
    logger.info("Application shutting down")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_config=None  # Use loguru instead
    )

