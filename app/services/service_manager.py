"""
Service manager for shared service instances
"""
from typing import Optional
from app.services.gdrive_service import GoogleDriveService
from app.services.mongodb_service import MongoDBService

# Global Google Drive service instance
gdrive_service: Optional[GoogleDriveService] = None

# Global MongoDB service instance
mongodb_service: Optional[MongoDBService] = None


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


def get_mongodb_service() -> MongoDBService:
    """
    Get the MongoDB service instance
    
    Returns:
        MongoDBService instance
        
    Raises:
        RuntimeError: If service is not initialized
    """
    global mongodb_service
    if mongodb_service is None:
        raise RuntimeError("MongoDB service is not available")
    return mongodb_service


def set_mongodb_service(service: MongoDBService) -> None:
    """
    Set the MongoDB service instance
    
    Args:
        service: MongoDBService instance to set
    """
    global mongodb_service
    mongodb_service = service


