"""
MongoDB service for OCR progress tracking
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from bson import ObjectId
from dotenv import load_dotenv
from loguru import logger
from pymongo import MongoClient
from pymongo.database import Database
from urllib.parse import quote_plus

from app.config import settings


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
        # Use provided URI if explicitly supplied
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000
        )
    else:
        # Construct URI from application settings
        username = settings.MONGO_USERNAME or ""
        password = settings.MONGO_PASSWORD or ""
        cluster_url = settings.MONGO_CLUSTER_URL or ""
        app_name = settings.MONGO_APP_NAME or ""

        if not all([username, password, cluster_url]):
            raise ValueError(
                "Missing MongoDB credentials in configuration. Required: "
                "MONGO_USERNAME, MONGO_PASSWORD, MONGO_CLUSTER_URL"
            )

        encoded_username = quote_plus(username)
        encoded_password = quote_plus(password)
        app_name_param = quote_plus(app_name) if app_name else ""

        # Construct MongoDB Atlas connection string
        if app_name_param:
            uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{cluster_url}/?appName={app_name_param}"
        else:
            uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{cluster_url}/"
        
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
        
        # Use provided URI if supplied; otherwise construct from settings during connection
        self.uri = uri
        
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
            self.db.ocr_jobs.create_index([("status", 1)], background=True)
            self.db.ocr_jobs.create_index([("created_at", -1)], background=True)
            
            # Unique index on dataset_name to ensure only one job per dataset
            # Note: If duplicates exist, this will fail - clean up duplicates first
            try:
                self.db.ocr_jobs.create_index([("dataset_name", 1)], unique=True, background=True)
                logger.info("Created unique index on ocr_jobs.dataset_name")
            except Exception as e:
                if "duplicate key" in str(e).lower() or "E11000" in str(e):
                    logger.error(
                        "Failed to create unique index on dataset_name: Duplicate records exist. "
                        "Please clean up duplicate job records before proceeding."
                    )
                    raise
                else:
                    logger.warning(f"Index on dataset_name may already exist: {e}")
            
            # Indexes for ocr_docs collection
            self.db.ocr_docs.create_index([("job_id", 1)], background=True)
            self.db.ocr_docs.create_index([("status", 1)], background=True)
            self.db.ocr_docs.create_index([("source_drive_file_id", 1)], background=True)
            
            # Unique compound index on dataset_name + source_drive_file_id
            # Note: If duplicates exist, this will fail - clean up duplicates first
            try:
                self.db.ocr_docs.create_index(
                    [("dataset_name", 1), ("source_drive_file_id", 1)], 
                    unique=True,
                    background=True
                )
                logger.info("Created unique compound index on ocr_docs (dataset_name, source_drive_file_id)")
            except Exception as e:
                if "duplicate key" in str(e).lower() or "E11000" in str(e):
                    logger.error(
                        "Failed to create unique index on (dataset_name, source_drive_file_id): "
                        "Duplicate records exist. Please clean up duplicate document records before proceeding."
                    )
                    raise
                else:
                    logger.warning(f"Compound index may already exist: {e}")
            
            logger.info("MongoDB indexes created/verified successfully")
        except Exception as e:
            logger.warning(f"Failed to create some indexes (may already exist or duplicates present): {e}")
    
    def create_job(
        self,
        dataset_name: str,
        input_folder_id: str,
        output_folder_id: str
    ) -> str:
        """
        Create or update an OCR job record for a dataset (idempotent by dataset_name)
        
        If a job already exists for this dataset_name, it will be updated with new status
        and folder IDs. Counters will be reset for a new run.
        
        Args:
            dataset_name: Name of the dataset (must be unique)
            input_folder_id: Google Drive input folder ID
            output_folder_id: Google Drive output folder ID
            
        Returns:
            Job ID (MongoDB ObjectId as string)
        """
        now = datetime.now(timezone.utc)
        
        # Check if job already exists for this dataset
        existing_job = self.db.ocr_jobs.find_one({"dataset_name": dataset_name})
        
        if existing_job:
            # Update existing job - reset status and counters for new run
            # Preserve created_at to track when dataset was first processed
            job_id = str(existing_job["_id"])
            logger.info(f"Found existing job: {job_id} for dataset: {dataset_name}, updating for new run")
            
            update = {
                "$set": {
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
                    "embedding_counters": {
                        "files_embedded": 0,
                        "embeddings_stored": 0,
                        "files_embedding_failed": 0
                    },
                    "updated_at": now
                }
            }
            
            # Preserve created_at if it exists, otherwise set it
            if "created_at" not in existing_job:
                update["$set"]["created_at"] = now
            
            self.db.ocr_jobs.update_one(
                {"_id": ObjectId(job_id) if isinstance(job_id, str) else existing_job["_id"]},
                update
            )
            
            return job_id
        else:
            # Create new job
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
                "embedding_counters": {
                    "files_embedded": 0,
                    "embeddings_stored": 0,
                    "files_embedding_failed": 0
                },
                "created_at": now,
                "updated_at": now,
                "tz": "Asia/Kolkata"
            }
            
            result = self.db.ocr_jobs.insert_one(job)
            job_id = str(result.inserted_id)
            logger.info(f"Created new OCR job: {job_id} for dataset: {dataset_name}")
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
        source_path: str,
        source_url: Optional[str] = None
    ) -> str:
        """
        Create or update a document record (idempotent by dataset_name + source_drive_file_id)
        
        If a document already exists for this dataset_name + source_drive_file_id combination,
        it will be updated with the new job_id and source_path, and status reset to "queued".
        
        Args:
            job_id: Parent job ID
            dataset_name: Dataset name
            source_drive_file_id: Google Drive source file ID
            source_path: Path to source file
            source_url: Optional Google Drive public view URL
            
        Returns:
            Document ID (MongoDB ObjectId as string)
        """
        now = datetime.now(timezone.utc)
        
        # Check if document already exists for this file in this dataset
        existing_doc = self.db.ocr_docs.find_one({
            "dataset_name": dataset_name,
            "source_drive_file_id": source_drive_file_id
        })
        
        if existing_doc:
            # Update existing document - reset status and counts for new run
            # Preserve created_at to track when document was first processed
            doc_id = str(existing_doc["_id"])
            logger.debug(f"Found existing doc: {doc_id} for file: {source_path}, updating for new run")
            
            update = {
                "$set": {
                    "job_id": job_id,
                    "source_path": source_path,
                    "status": "queued",
                    "message": "",
                    "counts": {
                        "pages_total": 0,
                        "pages_without_text": 0,
                        "chunks_emitted": 0,
                        "lang_undetected_count": 0
                    },
                    # Reset embedding status for new run
                    "embedded": False,
                    "embeddings_count": None,
                    "pinecone_index": None,
                    "embedded_at": None,
                    "updated_at": now
                }
            }
            
            # Update source_url if provided
            if source_url:
                update["$set"]["source_url"] = source_url
            
            # Preserve created_at if it exists, otherwise set it
            if "created_at" not in existing_doc:
                update["$set"]["created_at"] = now
            
            self.db.ocr_docs.update_one(
                {"_id": ObjectId(doc_id) if isinstance(doc_id, str) else existing_doc["_id"]},
                update
            )
            
            return doc_id
        else:
            # Create new document
            doc = {
                "job_id": job_id,
                "dataset_name": dataset_name,
                "source_drive_file_id": source_drive_file_id,
                "source_path": source_path,
                "source_url": source_url,
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
                "embedded": False,
                "embeddings_count": None,
                "pinecone_index": None,
                "embedded_at": None,
                "created_at": now,
                "updated_at": now,
                "tz": "Asia/Kolkata"
            }
            
            result = self.db.ocr_docs.insert_one(doc)
            doc_id = str(result.inserted_id)
            logger.debug(f"Created new OCR doc: {doc_id} for file: {source_path}")
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
    
    def mark_doc_embedded(self, doc_id: str, embeddings_count: int, pinecone_index: str):
        """
        Mark a document as embedded in Pinecone
        
        Args:
            doc_id: Document ID
            embeddings_count: Number of embeddings stored
            pinecone_index: Pinecone index name
        """
        self.db.ocr_docs.update_one(
            {"_id": ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
            {
                "$set": {
                    "embedded": True,
                    "embeddings_count": embeddings_count,
                    "pinecone_index": pinecone_index,
                    "embedded_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    
    def is_doc_embedded(self, source_drive_file_id: str, dataset_name: str) -> bool:
        """
        Check if a document has already been embedded
        
        Args:
            source_drive_file_id: Google Drive source file ID
            dataset_name: Dataset name
            
        Returns:
            True if document is already embedded, False otherwise
        """
        doc = self.db.ocr_docs.find_one(
            {
                "source_drive_file_id": source_drive_file_id,
                "dataset_name": dataset_name,
                "embedded": True
            }
        )
        return doc is not None
    
    def update_job_embedding_counters(
        self,
        job_id: str,
        counters: Dict[str, int]
    ):
        """
        Update job counters for embedding operations
        
        Args:
            job_id: Job ID
            counters: Dictionary with counter updates (incremental values)
        """
        update = {"$inc": {}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        
        for key, value in counters.items():
            update["$inc"][f"embedding_counters.{key}"] = value
        
        self.db.ocr_jobs.update_one(
            {"_id": ObjectId(job_id) if isinstance(job_id, str) else job_id},
            update
        )
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

