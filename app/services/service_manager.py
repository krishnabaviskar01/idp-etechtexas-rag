"""
Service manager for shared service instances
"""
from typing import Optional
from app.services.gdrive_service import GoogleDriveService

# Global Google Drive service instance
gdrive_service: Optional[GoogleDriveService] = None


def get_gdrive_service() -> GoogleDriveService:
    """
    Get the Google Drive service instance
    
    Returns:
        GoogleDriveService instance
        
    Raises:
        RuntimeError: If service is not initialized
    """
    global gdrive_service
    if gdrive_service is None:
        raise RuntimeError("Google Drive service is not available")
    return gdrive_service


def set_gdrive_service(service: GoogleDriveService) -> None:
    """
    Set the Google Drive service instance
    
    Args:
        service: GoogleDriveService instance to set
    """
    global gdrive_service
    gdrive_service = service

