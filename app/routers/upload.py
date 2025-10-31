"""
File upload router
"""
from typing import Optional, List
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from app.config import settings
from app.schemas.upload import UploadResponse, UploadedFile, FailedFile, DatasetFolder, FileMetadata
from app.services.service_manager import get_gdrive_service
from app.services.gdrive_service import GoogleDriveService
from app.logger import initialize_logger

logger = initialize_logger()
router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    folder_id: Optional[str] = Form(None),
    dataset_name: Optional[str] = Form(None),
    gdrive_service: GoogleDriveService = Depends(get_gdrive_service)
):
    """
    Upload one or multiple files to Google Drive
    
    Args:
        files: List of files to upload
        folder_id: Optional Google Drive folder ID (parent folder)
        dataset_name: Optional dataset name - creates a folder with this name and uploads all files inside
        gdrive_service: Google Drive service dependency
    
    Returns:
        UploadResponse with file metadata for all uploaded files
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required"
        )
    
    logger.info(f"Received upload request for {len(files)} file(s), dataset_name: {dataset_name}")
    
    # Determine target folder (same for all files if dataset_name is provided)
    target_folder_id = None
    
    # If dataset_name is provided, create or get the folder
    if dataset_name:
        # Get parent folder (either provided folder_id or default from settings)
        parent_folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        # Create or get the dataset folder
        target_folder_id = gdrive_service.create_or_get_folder(
            folder_name=dataset_name,
            parent_folder_id=parent_folder_id
        )
        logger.info(f"Using dataset folder: {dataset_name} (ID: {target_folder_id})")
    else:
        # Use provided folder_id or default from settings
        target_folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
    
    uploaded_files = []
    failed_files = []
    
    # Process each file
    for file in files:
        file_name = file.filename
        
        if not file_name:
            logger.warning("Skipping file with no filename")
            failed_files.append(
                FailedFile(
                    filename=None,
                    error="File name is required"
                )
            )
            continue
        
        try:
            logger.info(f"Processing file: {file_name}")
            
            # Read file content
            file_content = await file.read()
            logger.debug(f"File size: {len(file_content)} bytes")
            
            # Upload to Google Drive
            result = gdrive_service.upload_file_from_bytes(
                file_bytes=file_content,
                file_name=file_name,
                folder_id=target_folder_id,
                mime_type=file.content_type
            )
            
            uploaded_files.append(
                UploadedFile(
                    filename=file_name,
                    status="success",
                    data=FileMetadata(**result)
                )
            )
            logger.success(f"Successfully uploaded: {file_name}")
        
        except Exception as e:
            logger.error(f"Error uploading file {file_name}: {e}")
            failed_files.append(
                FailedFile(
                    filename=file_name,
                    error=str(e)
                )
            )
    
    # Prepare response
    response = UploadResponse(
        success=len(failed_files) == 0,
        message=f"Uploaded {len(uploaded_files)} of {len(files)} file(s)",
        uploaded_files=uploaded_files,
        total_files=len(files),
        successful_uploads=len(uploaded_files),
        failed_uploads=len(failed_files),
        failed_files=failed_files if failed_files else None,
        dataset_folder=DatasetFolder(name=dataset_name, id=target_folder_id) if dataset_name else None
    )
    
    # Return appropriate status code
    status_code = 200 if len(uploaded_files) > 0 else 500
    
    if len(failed_files) > 0 and len(uploaded_files) == 0:
        # All files failed
        raise HTTPException(
            status_code=500,
            detail=response.model_dump()
        )
    
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True)
    )

