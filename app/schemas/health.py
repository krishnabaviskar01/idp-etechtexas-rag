"""
Health check related schemas
"""
from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """Root endpoint response schema"""
    message: str = Field(..., description="Welcome message")
    version: str = Field(..., description="Application version")
    status: str = Field(..., description="Application status")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Welcome to IDP EtechTexas RAG",
                "version": "0.1.0",
                "status": "running"
            }
        }


class HealthResponse(BaseModel):
    """Health check response schema"""
    status: str = Field(..., description="Health status")
    gdrive_service: str = Field(..., description="Google Drive service availability")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "gdrive_service": "available"
            }
        }

