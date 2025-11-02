"""
OCR processing router
"""
import json
import os
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from app.config import settings
from app.schemas.ocr import OCRProcessRequest, OCRProcessResponse, DocumentStatus, OCRMetrics
from app.services.service_manager import get_gdrive_service, get_mongodb_service
from app.services.gdrive_service import GoogleDriveService
from app.services.mongodb_service import MongoDBService
from app.services.ocr_service import OCRService


router = APIRouter(prefix="/ocr", tags=["ocr"])


def get_ocr_service(
    chunk_size: int = 512,
    chunk_overlap: int = 50
) -> OCRService:
    """Get OCR service instance"""
    return OCRService(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )


@router.post("/process", response_model=OCRProcessResponse)
async def process_ocr(
    request: OCRProcessRequest,
    gdrive_service: GoogleDriveService = Depends(get_gdrive_service),
    mongodb_service: MongoDBService = Depends(get_mongodb_service)
):
    """
    Process OCR and chunking for files in a Google Drive dataset folder
    
    Args:
        request: OCR processing request
        gdrive_service: Google Drive service dependency
        mongodb_service: MongoDB service dependency
        
    Returns:
        OCRProcessResponse with processing results
    """
    logger.info(f"Starting OCR processing for dataset: {request.dataset_name}")
    
    # Resolve root folder
    root_folder_id = request.drive_folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
    
    if not root_folder_id:
        raise HTTPException(
            status_code=400,
            detail="drive_folder_id must be provided or set in environment"
        )
    
    # Find dataset folder
    try:
        dataset_folder_id = gdrive_service.create_or_get_folder(
            folder_name=request.dataset_name,
            parent_folder_id=root_folder_id
        )
    except Exception as e:
        logger.error(f"Failed to find/create dataset folder: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Dataset folder '{request.dataset_name}' not found and could not be created"
        )
    
    # Ensure output root folder exists
    output_root_folder_id = gdrive_service.create_or_get_folder(
        folder_name="Optical Character Recognition",
        parent_folder_id=root_folder_id
    )
    
    # Ensure output dataset folder exists
    output_dataset_folder_id = gdrive_service.create_or_get_folder(
        folder_name=request.dataset_name,
        parent_folder_id=output_root_folder_id
    )
    
    # Create job in MongoDB
    job_id = mongodb_service.create_job(
        dataset_name=request.dataset_name,
        input_folder_id=dataset_folder_id,
        output_folder_id=output_dataset_folder_id
    )
    
    # Initialize OCR service
    ocr_service = get_ocr_service(
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap
    )
    
    # Discover files
    try:
        files = gdrive_service.list_files_in_folder(
            folder_id=dataset_folder_id,
            recursive=True
        )
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        mongodb_service.finish_job(job_id, "failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files in dataset folder: {e}"
        )
    
    mongodb_service.update_job_counters(job_id, {"files_discovered": len(files)})
    
    logger.info(f"Discovered {len(files)} files to process")
    
    # Process files
    documents = []
    files_processed = 0
    files_failed = 0
    files_skipped = 0
    total_pages_processed = 0
    total_pages_without_text = 0
    total_chunks_emitted = 0
    total_lang_undetected = 0
    
    for file_info in files:
        file_id = file_info['id']
        file_name = file_info['name']
        file_path = file_info['path']
        mime_type = file_info.get('mimeType')
        
        # Construct Google Drive public view URL
        source_url = f"https://drive.google.com/file/d/{file_id}/view"
        
        # Create document record
        doc_id = mongodb_service.create_doc(
            job_id=job_id,
            dataset_name=request.dataset_name,
            source_drive_file_id=file_id,
            source_path=file_path,
            source_url=source_url
        )
        
        # Determine output path (mirror structure under "Optical Character Recognition")
        # Example: dataset_name/subfolder/file.pdf -> Optical Character Recognition/dataset_name/subfolder/file.json
        
        # Get relative path within dataset
        if file_path.startswith(f"{request.dataset_name}/"):
            relative_path = file_path[len(f"{request.dataset_name}/"):]
        elif file_path == request.dataset_name:
            relative_path = ""
        else:
            # Path doesn't start with dataset name, use as-is
            relative_path = file_path
        
        # Get directory and filename
        if relative_path:
            dir_path = os.path.dirname(relative_path)
            base_name = os.path.splitext(file_name)[0]
            output_file_name = f"{base_name}.json"
            
            # Build full output path
            if dir_path:
                output_path = f"{request.dataset_name}/{dir_path}/{output_file_name}"
                output_dir_path = f"{request.dataset_name}/{dir_path}"
            else:
                output_path = f"{request.dataset_name}/{output_file_name}"
                output_dir_path = request.dataset_name
        else:
            # File is directly in dataset root
            base_name = os.path.splitext(file_name)[0]
            output_file_name = f"{base_name}.json"
            output_path = f"{request.dataset_name}/{output_file_name}"
            output_dir_path = request.dataset_name
        
        # Ensure output folder hierarchy exists (needed for file existence check)
        output_parent_folder_id = output_dataset_folder_id
        if output_dir_path and output_dir_path != request.dataset_name:
            # Create subfolder hierarchy (remove dataset_name prefix)
            subfolder_path = output_dir_path.replace(f"{request.dataset_name}/", "")
            if subfolder_path:
                output_parent_folder_id = gdrive_service.ensure_folder_hierarchy(
                    folder_path=subfolder_path,
                    parent_folder_id=output_dataset_folder_id
                )
        
        # Check if output already exists
        if not request.force:
            # Check if file exists in output folder
            existing_file_id = gdrive_service.file_exists_in_folder(
                file_name=output_file_name,
                folder_id=output_parent_folder_id
            )
            if existing_file_id:
                logger.info(f"Skipping {file_name}: output already exists")
                mongodb_service.update_doc_status(
                    doc_id,
                    "skipped",
                    "Output file already exists"
                )
                mongodb_service.update_doc_output(doc_id, existing_file_id, output_path)
                
                documents.append(DocumentStatus(
                    source_path=file_path,
                    output_path=output_path,
                    status="skipped",
                    message="Output file already exists",
                    source_drive_file_id=file_id,
                    output_drive_file_id=existing_file_id
                ))
                files_skipped += 1
                continue
        
        mongodb_service.update_doc_status(doc_id, "processing", "Downloading file")
        
        try:
            # Download file
            file_bytes = gdrive_service.download_file(file_id)
            
            # Process document
            result = ocr_service.process_document(
                file_bytes=file_bytes,
                file_name=file_name,
                doc_id=request.doc_id,
                mime_type=mime_type
            )
            
            # Check if document has no chunks (empty or failed)
            if result['chunks_emitted'] == 0:
                mongodb_service.update_doc_status(
                    doc_id,
                    "failed",
                    "No extractable text found"
                )
                mongodb_service.update_doc_counts(doc_id, {
                    "pages_total": result['total_page_count'],
                    "pages_without_text": result['pages_without_text'],
                    "chunks_emitted": 0,
                    "lang_undetected_count": 1 if result['lang_undetected'] else 0
                })
                mongodb_service.update_job_counters(job_id, {
                    "files_failed": 1,
                    "pages_processed": result['total_page_count'],
                    "pages_without_text": result['pages_without_text'],
                    "lang_undetected_count": 1 if result['lang_undetected'] else 0
                })
                
                documents.append(DocumentStatus(
                    source_path=file_path,
                    output_path=None,
                    status="failed",
                    message="No extractable text found",
                    source_drive_file_id=file_id,
                    output_drive_file_id=None
                ))
                files_failed += 1
                continue
            
            # Prepare JSON output (strict key order)
            json_chunks = []
            for chunk in result['chunks']:
                json_chunks.append({
                    "doc_id": chunk['doc_id'],
                    "file_name": chunk['file_name'],
                    "language": chunk['language'],
                    "total_page_count": chunk['total_page_count'],
                    "page_index": chunk['page_index'],
                    "chunk_index": chunk['chunk_index'],
                    "text": chunk['text'],
                    "source_url": source_url
                })
            
            # Upload JSON to Drive
            json_content = json.dumps(json_chunks, ensure_ascii=False, indent=2)
            json_bytes = json_content.encode('utf-8')
            
            # Upload JSON file (output_parent_folder_id already set above)
            output_file_info = gdrive_service.upload_file_from_bytes(
                file_bytes=json_bytes,
                file_name=output_file_name,
                folder_id=output_parent_folder_id,
                mime_type="application/json"
            )
            
            output_drive_file_id = output_file_info['file_id']
            
            # Update document record
            mongodb_service.update_doc_status(doc_id, "ok", "Processed successfully")
            mongodb_service.update_doc_output(doc_id, output_drive_file_id, output_path)
            mongodb_service.update_doc_counts(doc_id, {
                "pages_total": result['total_page_count'],
                "pages_without_text": result['pages_without_text'],
                "chunks_emitted": result['chunks_emitted'],
                "lang_undetected_count": 1 if result['lang_undetected'] else 0
            })
            
            # Update job counters
            mongodb_service.update_job_counters(job_id, {
                "files_processed": 1,
                "pages_processed": result['total_page_count'],
                "pages_without_text": result['pages_without_text'],
                "chunks_emitted": result['chunks_emitted'],
                "lang_undetected_count": 1 if result['lang_undetected'] else 0
            })
            
            documents.append(DocumentStatus(
                source_path=file_path,
                output_path=output_path,
                status="ok",
                message="Processed successfully",
                source_drive_file_id=file_id,
                output_drive_file_id=output_drive_file_id
            ))
            
            files_processed += 1
            total_pages_processed += result['total_page_count']
            total_pages_without_text += result['pages_without_text']
            total_chunks_emitted += result['chunks_emitted']
            if result['lang_undetected']:
                total_lang_undetected += 1
            
            logger.success(f"Processed file: {file_name} ({result['chunks_emitted']} chunks)")
        
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            mongodb_service.update_doc_status(doc_id, "failed", str(e))
            mongodb_service.update_job_counters(job_id, {"files_failed": 1})
            
            documents.append(DocumentStatus(
                source_path=file_path,
                output_path=None,
                status="failed",
                message=str(e),
                source_drive_file_id=file_id,
                output_drive_file_id=None
            ))
            files_failed += 1
    
    # Determine final job status
    if files_failed == 0:
        job_status = "completed"
    elif files_processed > 0:
        job_status = "completed_with_errors"
    else:
        job_status = "failed"
    
    mongodb_service.finish_job(job_id, job_status)
    
    logger.info(
        f"OCR processing completed: {files_processed} processed, "
        f"{files_failed} failed, {total_chunks_emitted} chunks emitted"
    )
    
    # Build response
    response = OCRProcessResponse(
        dataset_name=request.dataset_name,
        input_folder_id=dataset_folder_id,
        output_folder_id=output_dataset_folder_id,
        job_id=job_id,
        files_discovered=len(files),
        files_processed=files_processed,
        files_failed=files_failed,
        metrics=OCRMetrics(
            files_discovered=len(files),
            files_processed=files_processed,
            files_failed=files_failed,
            pages_processed=total_pages_processed,
            pages_without_text=total_pages_without_text,
            chunks_emitted=total_chunks_emitted,
            lang_undetected_count=total_lang_undetected
        ),
        documents=documents
    )
    
    return response

