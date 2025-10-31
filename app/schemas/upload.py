"""
Upload related schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    """Google Drive file metadata"""
    file_id: str = Field(..., description="Google Drive file ID")
    name: str = Field(..., description="File name")
    size: Optional[str] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="File MIME type")
    web_view_link: Optional[str] = Field(None, description="Web view link")
    web_content_link: Optional[str] = Field(None, description="Web content link")
    created_time: Optional[str] = Field(None, description="File creation time")
    modified_time: Optional[str] = Field(None, description="File modification time")

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "1a2b3c4d5e6f7g8h9i0j",
                "name": "example.pdf",
                "size": "1024",
                "mime_type": "application/pdf",
                "web_view_link": "https://drive.google.com/file/d/...",
                "web_content_link": "https://drive.google.com/uc?export=download&id=...",
                "created_time": "2025-01-01T00:00:00.000Z",
                "modified_time": "2025-01-01T00:00:00.000Z"
            }
        }


class UploadedFile(BaseModel):
    """Successfully uploaded file information"""
    filename: str = Field(..., description="Name of the uploaded file")
    status: str = Field(default="success", description="Upload status")
    data: FileMetadata = Field(..., description="File metadata from Google Drive")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "example.pdf",
                "status": "success",
                "data": {
                    "file_id": "1a2b3c4d5e6f7g8h9i0j",
                    "name": "example.pdf",
                    "size": "1024",
                    "mime_type": "application/pdf"
                }
            }
        }


class FailedFile(BaseModel):
    """Failed file upload information"""
    filename: Optional[str] = Field(None, description="Name of the file that failed to upload")
    error: str = Field(..., description="Error message")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "example.pdf",
                "error": "File upload failed: Connection timeout"
            }
        }


class DatasetFolder(BaseModel):
    """Dataset folder information"""
    name: str = Field(..., description="Dataset folder name")
    id: str = Field(..., description="Google Drive folder ID")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "my_dataset",
                "id": "1a2b3c4d5e6f7g8h9i0j"
            }
        }


class UploadResponse(BaseModel):
    """Upload response schema"""
    success: bool = Field(..., description="Whether all files were uploaded successfully")
    message: str = Field(..., description="Response message")
    uploaded_files: List[UploadedFile] = Field(..., description="List of successfully uploaded files")
    total_files: int = Field(..., description="Total number of files in the request")
    successful_uploads: int = Field(..., description="Number of successfully uploaded files")
    failed_uploads: int = Field(..., description="Number of failed uploads")
    failed_files: Optional[List[FailedFile]] = Field(None, description="List of failed files")
    dataset_folder: Optional[DatasetFolder] = Field(None, description="Dataset folder information if dataset_name was provided")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Uploaded 2 of 2 file(s)",
                "uploaded_files": [
                    {
                        "filename": "file1.pdf",
                        "status": "success",
                        "data": {
                            "file_id": "1a2b3c4d5e6f7g8h9i0j",
                            "name": "file1.pdf"
                        }
                    }
                ],
                "total_files": 2,
                "successful_uploads": 2,
                "failed_uploads": 0,
                "dataset_folder": {
                    "name": "my_dataset",
                    "id": "1a2b3c4d5e6f7g8h9i0j"
                }
            }
        }

