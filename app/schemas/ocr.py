"""
OCR related schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class OCRProcessRequest(BaseModel):
    """Request schema for OCR processing"""
    dataset_name: str = Field(..., description="Name of the dataset")
    drive_folder_id: Optional[str] = Field(None, description="Google Drive folder ID (optional, defaults to env/constant)")
    doc_id: Optional[str] = Field(None, description="Optional document ID override")
    chunk_size: int = Field(512, ge=100, le=2000, description="Chunk size in characters")
    chunk_overlap: int = Field(50, ge=0, le=500, description="Chunk overlap in characters")
    force: bool = Field(False, description="Force reprocessing even if output exists")
    log_level: str = Field("INFO", description="Log level")

    class Config:
        json_schema_extra = {
            "example": {
                "dataset_name": "The Constitution Dataset",
                "drive_folder_id": "1ZT_FuaOCd6DmoAcOXbMhH2XmXCrLHovy",
                "chunk_size": 512,
                "chunk_overlap": 50,
                "force": False,
                "log_level": "INFO"
            }
        }


class DocumentStatus(BaseModel):
    """Document processing status"""
    source_path: str = Field(..., description="Path to source file")
    output_path: Optional[str] = Field(None, description="Path to output JSON file")
    status: str = Field(..., description="Status: ok|skipped|failed")
    message: str = Field("", description="Status message")
    source_drive_file_id: Optional[str] = Field(None, description="Source file ID")
    output_drive_file_id: Optional[str] = Field(None, description="Output file ID")

    class Config:
        json_schema_extra = {
            "example": {
                "source_path": "dataset_name/file.pdf",
                "output_path": "Optical Character Recognition/dataset_name/file.json",
                "status": "ok",
                "message": "Processed successfully"
            }
        }


class OCRMetrics(BaseModel):
    """OCR processing metrics"""
    files_discovered: int = Field(0, description="Number of files discovered")
    files_processed: int = Field(0, description="Number of files processed successfully")
    files_failed: int = Field(0, description="Number of files that failed")
    pages_processed: int = Field(0, description="Total pages processed")
    pages_without_text: int = Field(0, description="Pages without extractable text")
    chunks_emitted: int = Field(0, description="Total chunks emitted")
    lang_undetected_count: int = Field(0, description="Count of documents with undetected language")

    class Config:
        json_schema_extra = {
            "example": {
                "files_discovered": 10,
                "files_processed": 8,
                "files_failed": 2,
                "pages_processed": 150,
                "pages_without_text": 5,
                "chunks_emitted": 200,
                "lang_undetected_count": 1
            }
        }


class OCRProcessResponse(BaseModel):
    """Response schema for OCR processing"""
    dataset_name: str = Field(..., description="Dataset name")
    input_folder_id: str = Field(..., description="Input folder ID")
    output_folder_id: str = Field(..., description="Output folder ID")
    job_id: str = Field(..., description="MongoDB job ID")
    files_discovered: int = Field(0, description="Number of files discovered")
    files_processed: int = Field(0, description="Number of files processed successfully")
    files_failed: int = Field(0, description="Number of files that failed")
    metrics: OCRMetrics = Field(..., description="Processing metrics")
    documents: List[DocumentStatus] = Field(..., description="List of document statuses")

    class Config:
        json_schema_extra = {
            "example": {
                "dataset_name": "The Constitution Dataset",
                "input_folder_id": "1ZT_FuaOCd6DmoAcOXbMhH2XmXCrLHovy",
                "output_folder_id": "2ABC_DEF_GHI_JKL_MNO_PQR_STU_VWX",
                "job_id": "507f1f77bcf86cd799439011",
                "files_discovered": 10,
                "files_processed": 8,
                "files_failed": 2,
                "metrics": {
                    "files_discovered": 10,
                    "files_processed": 8,
                    "files_failed": 2,
                    "pages_processed": 150,
                    "pages_without_text": 5,
                    "chunks_emitted": 200,
                    "lang_undetected_count": 1
                },
                "documents": [
                    {
                        "source_path": "dataset_name/file.pdf",
                        "output_path": "Optical Character Recognition/dataset_name/file.json",
                        "status": "ok",
                        "message": "Processed successfully"
                    }
                ]
            }
        }

