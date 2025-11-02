"""
Ingestion pipeline router
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from app.schemas.ingestion import IngestionRequest, IngestionResponse
from app.services.service_manager import get_gdrive_service, get_mongodb_service
from app.services.gdrive_service import GoogleDriveService
from app.services.mongodb_service import MongoDBService
from app.services.ingestion_service import IngestionService


router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_ingestion_service() -> IngestionService:
    """Get ingestion service instance"""
    try:
        return IngestionService()
    except ValueError as e:
        logger.error(f"Failed to initialize ingestion service: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/pipeline", response_model=IngestionResponse)
async def run_ingestion_pipeline(
    payload: IngestionRequest,
    gdrive_service: GoogleDriveService = Depends(get_gdrive_service),
    mongodb_service: MongoDBService = Depends(get_mongodb_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """
    Run end-to-end ingestion pipeline:
    1. Read files from Google Drive
    2. Perform OCR + intelligent chunking (stores JSON in mirror folder)
    3. Extract structured metadata using GPT-4o-mini
    4. Generate embeddings using text-embedding-3-small
    5. Store embeddings and metadata in Pinecone
    6. Track all progress in MongoDB
    
    Args:
        payload: Ingestion pipeline request
        gdrive_service: Google Drive service dependency
        mongodb_service: MongoDB service dependency
        ingestion_service: Ingestion service dependency
        
    Returns:
        IngestionResponse with pipeline results
    """
    logger.info(f"Starting ingestion pipeline for dataset: {payload.dataset_name}")
    
    try:
        # Run pipeline (folder verification will happen when listing files)
        result = await ingestion_service.run_pipeline(
            dataset_name=payload.dataset_name,
            drive_folder_id=payload.drive_folder_id,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
            force=payload.force,
            metadata_keys=payload.metadata_keys,
            mongodb_service=mongodb_service,
            gdrive_service=gdrive_service
        )
        
        response = IngestionResponse(**result)
        logger.success(
            f"Ingestion pipeline completed: {response.files_processed} files, "
            f"{response.embeddings_stored} embeddings"
        )
        return response
    
    except HTTPException:
        raise
    except ValueError as e:
        # Handle folder access errors
        logger.error(f"Ingestion pipeline validation failed: {e}")
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")
        return IngestionResponse(
            status="error",
            dataset_name=payload.dataset_name,
            files_processed=0,
            files_embedded=0,
            files_skipped=0,
            embeddings_stored=0,
            metadata_extracted=False,
            pinecone_index=ingestion_service.pinecone_index_name,
            job_id=None,
            message="Ingestion pipeline failed",
            error=str(e)
        )

