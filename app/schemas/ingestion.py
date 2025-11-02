"""
Ingestion pipeline related schemas
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    """Request schema for ingestion pipeline"""
    chunk_overlap: int = Field(50, ge=0, le=500, description="Chunk overlap in characters")
    chunk_size: int = Field(512, ge=100, le=2000, description="Chunk size in characters")
    dataset_name: str = Field(..., description="Name of the dataset")
    drive_folder_id: str = Field(..., description="Google Drive folder ID")
    force: bool = Field(False, description="Force reprocessing even if already processed")
    log_level: str = Field("INFO", description="Log level")
    metadata_keys: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional custom metadata schema. If omitted, uses default legal metadata schema."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_overlap": 50,
                "chunk_size": 512,
                "dataset_name": "Bombay Highcourt Judgements",
                "drive_folder_id": "1ZT_FuaOCd6DmoAcOXbMhH2XmXCrLHovy",
                "force": False,
                "log_level": "INFO",
                "metadata_keys": {
                    "document_id": "string",
                    "title": "string",
                    "court_name": "string",
                    "case_number": "string",
                    "case_type": "string",
                    "decision_date": "YYYY-MM-DD",
                    "coram": "string",
                    "petitioner": "string",
                    "respondent": "string",
                    "key_issues": "string"
                }
            }
        }


class IngestionResponse(BaseModel):
    """Response schema for ingestion pipeline"""
    status: str = Field(..., description="Status: success|error")
    dataset_name: str = Field(..., description="Dataset name")
    files_processed: int = Field(0, description="Number of files processed (OCR)")
    files_embedded: int = Field(0, description="Number of files embedded")
    files_skipped: int = Field(0, description="Number of files skipped (already embedded)")
    embeddings_stored: int = Field(0, description="Total embeddings stored in Pinecone")
    metadata_extracted: bool = Field(False, description="Whether metadata extraction was successful")
    pinecone_index: str = Field(..., description="Pinecone index name")
    job_id: Optional[str] = Field(None, description="MongoDB job ID")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if status is error")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "dataset_name": "Bombay Highcourt Judgements",
                "files_processed": 10,
                "files_embedded": 10,
                "files_skipped": 0,
                "embeddings_stored": 1800,
                "metadata_extracted": True,
                "pinecone_index": "idp-etechtexas-rag",
                "job_id": "507f1f77bcf86cd799439011",
                "message": "Ingestion pipeline completed successfully."
            }
        }

