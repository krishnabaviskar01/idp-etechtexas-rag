"""
MongoDB service for OCR progress tracking
"""
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pymongo import MongoClient
from pymongo.database import Database
from bson import ObjectId
from urllib.parse import quote_plus
from dotenv import load_dotenv
from loguru import logger

from app.config import settings

# Load environment variables from .env file
load_dotenv()


def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    """
    Creates and returns a secure MongoDB client using credentials from .env
    
    Args:
        uri: Optional MongoDB URI (if provided, uses this instead of constructing from env vars)
        
    Returns:
        MongoClient instance
        
    Raises:
        ValueError: If required credentials are missing
        Exception: If connection fails
    """
    if uri:
        # Use provided URI (fallback for local development)
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000
        )
    else:
        # Construct URI from environment variables
        username = quote_plus(os.getenv("MONGO_USERNAME", ""))
        password = quote_plus(os.getenv("MONGO_PASSWORD", ""))
        cluster_url = os.getenv("MONGO_CLUSTER_URL", "")
        app_name = os.getenv("MONGO_APP_NAME", "")
        
        if not all([username, password, cluster_url]):
            raise ValueError("Missing MongoDB credentials in environment variables. "
                           "Required: MONGO_USERNAME, MONGO_PASSWORD, MONGO_CLUSTER_URL")
        
        # Construct MongoDB Atlas connection string
        if app_name:
            uri = f"mongodb+srv://{username}:{password}@{cluster_url}/?appName={app_name}"
        else:
            uri = f"mongodb+srv://{username}:{password}@{cluster_url}/"
        
        # Recommended connection options
        client = MongoClient(
            uri,
            tls=True,  # Enables TLS (SSL)
            serverSelectionTimeoutMS=5000  # Fails fast if server not reachable
        )
    
    try:
        # Ping the database to ensure connection is successful
        client.admin.command("ping")
        logger.info("✅ MongoDB connection successful!")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    return client


class MongoDBService:
    """Service for MongoDB operations related to OCR progress tracking"""
    
    def __init__(self, uri: Optional[str] = None, database_name: Optional[str] = None):
        """
        Initialize MongoDB service
        
        Args:
            uri: Optional MongoDB connection URI (if not provided, constructs from env vars)
            database_name: Database name (defaults to settings.MONGODB_DATABASE)
        """
        self.database_name = database_name or settings.MONGODB_DATABASE
        
        # Use provided URI or construct from environment variables
        if uri:
            self.uri = uri
        elif settings.MONGODB_URI and not (settings.MONGO_USERNAME and settings.MONGO_PASSWORD):
            # Fallback to MONGODB_URI if credentials not provided
            self.uri = settings.MONGODB_URI
        else:
            # Will construct URI in get_mongo_client
            self.uri = None
        
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self._connect()
        self._create_indexes()
    
    def _connect(self):
        """Connect to MongoDB and initialize database"""
        try:
            self.client = get_mongo_client(self.uri)
            self.db = self.client[self.database_name]
            logger.info(f"Connected to MongoDB database: {self.database_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def _create_indexes(self):
        """Create necessary indexes for OCR collections"""
        try:
            # Indexes for ocr_jobs collection
            self.db.ocr_jobs.create_index([("status", 1)])
            self.db.ocr_jobs.create_index([("created_at", -1)])
            
            # Indexes for ocr_docs collection
            self.db.ocr_docs.create_index([("job_id", 1)])
            self.db.ocr_docs.create_index([("status", 1)])
            
            logger.info("Created MongoDB indexes")
        except Exception as e:
            logger.warning(f"Failed to create indexes (may already exist): {e}")
    
    def create_job(
        self,
        dataset_name: str,
        input_folder_id: str,
        output_folder_id: str
    ) -> str:
        """
        Create a new OCR job record
        
        Args:
            dataset_name: Name of the dataset
            input_folder_id: Google Drive input folder ID
            output_folder_id: Google Drive output folder ID
            
        Returns:
            Job ID (MongoDB ObjectId as string)
        """
        now = datetime.now(timezone.utc)
        job = {
            "dataset_name": dataset_name,
            "input_folder_id": input_folder_id,
            "output_folder_id": output_folder_id,
            "status": "running",
            "counters": {
                "files_discovered": 0,
                "files_processed": 0,
                "files_failed": 0,
                "pages_processed": 0,
                "pages_without_text": 0,
                "chunks_emitted": 0,
                "lang_undetected_count": 0
            },
            "created_at": now,
            "updated_at": now,
            "tz": "Asia/Kolkata"
        }
        
        result = self.db.ocr_jobs.insert_one(job)
        job_id = str(result.inserted_id)
        logger.info(f"Created OCR job: {job_id} for dataset: {dataset_name}")
        return job_id
    
    def update_job_counters(
        self,
        job_id: str,
        counters: Dict[str, int]
    ):
        """
        Update job counters
        
        Args:
            job_id: Job ID
            counters: Dictionary with counter updates (incremental values)
        """
        update = {"$inc": {}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        
        for key, value in counters.items():
            update["$inc"][f"counters.{key}"] = value
        
        self.db.ocr_jobs.update_one(
            {"_id": ObjectId(job_id) if isinstance(job_id, str) else job_id},
            update
        )
    
    def finish_job(
        self,
        job_id: str,
        status: str
    ):
        """
        Finish a job by updating its status
        
        Args:
            job_id: Job ID
            status: Final status (completed|completed_with_errors|failed)
        """
        self.db.ocr_jobs.update_one(
            {"_id": ObjectId(job_id) if isinstance(job_id, str) else job_id},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        logger.info(f"Finished OCR job: {job_id} with status: {status}")
    
    def create_doc(
        self,
        job_id: str,
        dataset_name: str,
        source_drive_file_id: str,
        source_path: str
    ) -> str:
        """
        Create a new document record
        
        Args:
            job_id: Parent job ID
            dataset_name: Dataset name
            source_drive_file_id: Google Drive source file ID
            source_path: Path to source file
            
        Returns:
            Document ID (MongoDB ObjectId as string)
        """
        now = datetime.now(timezone.utc)
        doc = {
            "job_id": job_id,
            "dataset_name": dataset_name,
            "source_drive_file_id": source_drive_file_id,
            "source_path": source_path,
            "output_drive_file_id": None,
            "output_path": None,
            "status": "queued",
            "message": "",
            "counts": {
                "pages_total": 0,
                "pages_without_text": 0,
                "chunks_emitted": 0,
                "lang_undetected_count": 0
            },
            "created_at": now,
            "updated_at": now,
            "tz": "Asia/Kolkata"
        }
        
        result = self.db.ocr_docs.insert_one(doc)
        doc_id = str(result.inserted_id)
        logger.debug(f"Created OCR doc: {doc_id} for file: {source_path}")
        return doc_id
    
    def update_doc_status(
        self,
        doc_id: str,
        status: str,
        message: str = ""
    ):
        """
        Update document status
        
        Args:
            doc_id: Document ID
            status: New status (queued|processing|ok|skipped|failed)
            message: Optional status message
        """
        self.db.ocr_docs.update_one(
            {"_id": ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
            {
                "$set": {
                    "status": status,
                    "message": message,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    
    def update_doc_output(
        self,
        doc_id: str,
        output_drive_file_id: str,
        output_path: str
    ):
        """
        Update document with output file information
        
        Args:
            doc_id: Document ID
            output_drive_file_id: Google Drive output file ID
            output_path: Path to output file
        """
        self.db.ocr_docs.update_one(
            {"_id": ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
            {
                "$set": {
                    "output_drive_file_id": output_drive_file_id,
                    "output_path": output_path,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    
    def update_doc_counts(
        self,
        doc_id: str,
        counts: Dict[str, int]
    ):
        """
        Update document counts
        
        Args:
            doc_id: Document ID
            counts: Dictionary with count updates
        """
        update = {"$set": {"updated_at": datetime.now(timezone.utc)}}
        
        for key, value in counts.items():
            update["$set"][f"counts.{key}"] = value
        
        self.db.ocr_docs.update_one(
            {"_id": ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
            update
        )
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

