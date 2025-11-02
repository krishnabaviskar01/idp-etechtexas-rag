"""
Ingestion service for end-to-end pipeline: OCR, metadata extraction, embedding, and Pinecone storage
"""
import json
import os
from typing import List, Dict, Any, Optional
from loguru import logger

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.service_manager import get_gdrive_service, get_mongodb_service
from app.services.gdrive_service import GoogleDriveService
from app.services.ocr_service import OCRService
from app.services.mongodb_service import MongoDBService
from app.config import settings
from dotenv import load_dotenv

load_dotenv()

class IngestionService:
    """Service for end-to-end ingestion pipeline"""
    
    def __init__(self):
        """Initialize ingestion service with OpenAI and Pinecone clients"""
        # Initialize OpenAI client
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.openai_client = OpenAI(api_key=openai_api_key)
        
        # Initialize Pinecone client
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")
        self.pinecone_client = Pinecone(api_key=pinecone_api_key)
        
        pinecone_index_name = os.getenv("PINECONE_INDEX_NAME", "idp-etechtexas-rag")
        self.pinecone_index_name = pinecone_index_name
        
        # Get or create Pinecone index
        try:
            existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]
            if pinecone_index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {pinecone_index_name}")
                self.pinecone_client.create_index(
                    name=pinecone_index_name,
                    dimension=1536,  # text-embedding-3-small dimension
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                logger.success(f"Created Pinecone index: {pinecone_index_name}")
            else:
                logger.info(f"Using existing Pinecone index: {pinecone_index_name}")
            
            self.pinecone_index = self.pinecone_client.Index(pinecone_index_name)
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone index: {e}")
            raise
    
    def _get_default_metadata_schema(self) -> Dict[str, Any]:
        """Get default legal metadata schema"""
        return {
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
    
    def _generate_metadata_extraction_prompt(
        self,
        full_text: str,
        metadata_keys: Dict[str, Any]
    ) -> str:
        """
        Generate GPT prompt for metadata extraction
        
        Args:
            full_text: Full OCR text from document
            metadata_keys: Metadata schema dictionary
            
        Returns:
            Formatted prompt string
        """
        schema_json = json.dumps(metadata_keys, indent=2)
        
        prompt = f"""You are an expert legal document analyst.

Extract the following structured metadata from the provided legal document text. Return ONLY valid JSON matching the exact schema below. Do not include any explanatory text or markdown formatting, only the JSON object.

Important: All fields should be strings (not arrays or objects). For multiple values (like multiple parties or issues), combine them into a single comma-separated string.

Schema:
{schema_json}

Document Text:
{full_text[:15000]}

Return the extracted metadata as a JSON object matching the schema exactly. All values must be strings."""
        
        return prompt
    
    async def extract_metadata(
        self,
        full_text: str,
        metadata_keys: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured metadata from document text using GPT-4o-mini
        
        Args:
            full_text: Full OCR text from document
            metadata_keys: Optional custom metadata schema (uses default if None)
            
        Returns:
            Extracted metadata dictionary
        """
        # Use default schema if not provided
        if metadata_keys is None:
            metadata_keys = self._get_default_metadata_schema()
        
        # Generate prompt
        prompt = self._generate_metadata_extraction_prompt(full_text, metadata_keys)
        
        try:
            logger.info("Extracting metadata using GPT-4o-mini")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert legal document analyst. Extract structured metadata and return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            metadata_json = response.choices[0].message.content
            metadata = json.loads(metadata_json)
            
            # Ensure all values are strings (handle cases where GPT returns arrays)
            normalized_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, list):
                    # Convert list to comma-separated string
                    normalized_metadata[key] = ", ".join(str(item) for item in value if item)
                elif isinstance(value, dict):
                    # Convert dict to JSON string
                    normalized_metadata[key] = json.dumps(value)
                elif value is None:
                    normalized_metadata[key] = ""
                else:
                    normalized_metadata[key] = str(value)
            
            logger.success(f"Extracted metadata: {list(normalized_metadata.keys())}")
            return normalized_metadata
        
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            # Return empty metadata with defaults
            return {
                "document_id": "",
                "title": "",
                "court_name": "",
                "case_number": "",
                "case_type": "",
                "decision_date": "",
                "coram": "",
                "petitioner": "",
                "respondent": "",
                "key_issues": ""
            }
    
    def _normalize_metadata_for_pinecone(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize metadata values to be compatible with Pinecone requirements.
        Pinecone only accepts: string, number, boolean, or list of strings.
        
        Args:
            metadata: Metadata dictionary that may contain arrays or nested structures
            
        Returns:
            Normalized metadata dictionary compatible with Pinecone
        """
        normalized = {}
        
        for key, value in metadata.items():
            if value is None:
                # Skip None values or convert to empty string
                normalized[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                # Primitive types are fine, but ensure strings are not too long
                if isinstance(value, str) and len(value) > 1000:
                    # Truncate very long strings (Pinecone has metadata size limits)
                    normalized[key] = value[:1000]
                else:
                    normalized[key] = value
            elif isinstance(value, list):
                # Lists: convert to comma-separated string (Pinecone accepts list of strings but simpler to use string)
                if all(isinstance(item, str) for item in value):
                    normalized[key] = ", ".join(value) if value else ""
                else:
                    # Convert list items to strings and join
                    normalized[key] = ", ".join(str(item) for item in value if item)
            elif isinstance(value, dict):
                # Nested dictionaries: convert to JSON string
                normalized[key] = json.dumps(value)
            else:
                # Other types: convert to string
                normalized[key] = str(value)
        
        return normalized
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using text-embedding-3-small
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (1536 dimensions)
        """
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def run_pipeline(
        self,
        dataset_name: str,
        drive_folder_id: str,
        chunk_size: int,
        chunk_overlap: int,
        force: bool = False,
        metadata_keys: Optional[Dict[str, Any]] = None,
        mongodb_service: Optional[MongoDBService] = None,
        gdrive_service: Optional[GoogleDriveService] = None
    ) -> Dict[str, Any]:
        """
        Run end-to-end ingestion pipeline
        
        Args:
            dataset_name: Name of the dataset
            drive_folder_id: Google Drive folder ID
            chunk_size: Chunk size in characters
            chunk_overlap: Chunk overlap in characters
            force: Force reprocessing even if already processed
            metadata_keys: Optional custom metadata schema
            mongodb_service: Optional MongoDB service (will get from service manager if None)
            gdrive_service: Optional Google Drive service (will get from service manager if None)
            
        Returns:
            Dictionary with pipeline results
        """
        logger.info(f"Starting ingestion pipeline for dataset: {dataset_name}")
        
        # Get services
        if gdrive_service is None:
            gdrive_service = get_gdrive_service()
        if mongodb_service is None:
            mongodb_service = get_mongodb_service()
        
        # Resolve root folder (same logic as OCR endpoint)
        root_folder_id = drive_folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        if not root_folder_id:
            raise ValueError("drive_folder_id must be provided or set in environment")
        
        # Ensure output root folder exists (mirror structure)
        output_root_folder_id = gdrive_service.create_or_get_folder(
            folder_name="Optical Character Recognition",
            parent_folder_id=root_folder_id
        )
        
        # Ensure output dataset folder exists
        output_dataset_folder_id = gdrive_service.create_or_get_folder(
            folder_name=dataset_name,
            parent_folder_id=output_root_folder_id
        )
        
        # Create job in MongoDB
        job_id = mongodb_service.create_job(
            dataset_name=dataset_name,
            input_folder_id=drive_folder_id,
            output_folder_id=output_dataset_folder_id
        )
        
        # Initialize OCR service
        ocr_service = OCRService(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # List files in folder
        try:
            files = gdrive_service.list_files_in_folder(
                folder_id=drive_folder_id,
                recursive=True
            )
            logger.info(f"Found {len(files)} files to process")
        except Exception as e:
            logger.error(f"Failed to list files in folder '{drive_folder_id}': {e}")
            mongodb_service.finish_job(job_id, "failed")
            error_msg = str(e)
            if "not found" in error_msg.lower() or "404" in error_msg:
                raise ValueError(
                    f"Folder '{drive_folder_id}' not found or inaccessible. "
                    f"Please verify the folder ID and ensure you have access to it."
                )
            raise ValueError(f"Failed to access folder '{drive_folder_id}': {error_msg}")
        
        mongodb_service.update_job_counters(job_id, {"files_discovered": len(files)})
        
        files_processed = 0
        files_skipped = 0
        files_failed = 0
        embeddings_stored = 0
        files_embedded = 0
        files_embedding_failed = 0
        
        # Process each file
        for file_info in files:
            file_id = file_info['id']
            file_name = file_info['name']
            file_path = file_info['path']
            mime_type = file_info.get('mimeType')
            
            logger.info(f"Processing file: {file_name}")
            
            # Construct Google Drive public view URL
            source_url = f"https://drive.google.com/file/d/{file_id}/view"
            
            # Create document record in MongoDB
            doc_id = mongodb_service.create_doc(
                job_id=job_id,
                dataset_name=dataset_name,
                source_drive_file_id=file_id,
                source_path=file_path,
                source_url=source_url
            )
            
            # Determine output path (mirror structure under "Optical Character Recognition")
            # Same logic as OCR endpoint
            if file_path.startswith(f"{dataset_name}/"):
                relative_path = file_path[len(f"{dataset_name}/"):]
            elif file_path == dataset_name:
                relative_path = ""
            else:
                relative_path = file_path
            
            # Get directory and filename
            if relative_path:
                dir_path = os.path.dirname(relative_path)
                base_name = os.path.splitext(file_name)[0]
                output_file_name = f"{base_name}.json"
                
                if dir_path:
                    output_path = f"{dataset_name}/{dir_path}/{output_file_name}"
                    output_dir_path = f"{dataset_name}/{dir_path}"
                else:
                    output_path = f"{dataset_name}/{output_file_name}"
                    output_dir_path = dataset_name
            else:
                base_name = os.path.splitext(file_name)[0]
                output_file_name = f"{base_name}.json"
                output_path = f"{dataset_name}/{output_file_name}"
                output_dir_path = dataset_name
            
            # Ensure output folder hierarchy exists
            output_parent_folder_id = output_dataset_folder_id
            if output_dir_path and output_dir_path != dataset_name:
                subfolder_path = output_dir_path.replace(f"{dataset_name}/", "")
                if subfolder_path:
                    output_parent_folder_id = gdrive_service.ensure_folder_hierarchy(
                        folder_path=subfolder_path,
                        parent_folder_id=output_dataset_folder_id
                    )
            
            # Check if already embedded (unless force)
            skip_embedding = False
            if not force:
                if mongodb_service.is_doc_embedded(file_id, dataset_name):
                    logger.info(f"Skipping embedding for {file_name}: already embedded")
                    skip_embedding = True
            
            # Check if OCR JSON already exists (unless force)
            existing_json_file_id = None
            if not force:
                existing_json_file_id = gdrive_service.file_exists_in_folder(
                    file_name=output_file_name,
                    folder_id=output_parent_folder_id
                )
            
            try:
                mongodb_service.update_doc_status(doc_id, "processing", "Downloading file")
                
                # Download file
                file_bytes = gdrive_service.download_file(file_id)
                
                # Process OCR document
                ocr_result = ocr_service.process_document(
                    file_bytes=file_bytes,
                    file_name=file_name,
                    mime_type=mime_type
                )
                
                # Check if document has no chunks
                if ocr_result['chunks_emitted'] == 0:
                    mongodb_service.update_doc_status(doc_id, "failed", "No extractable text found")
                    mongodb_service.update_doc_counts(doc_id, {
                        "pages_total": ocr_result['total_page_count'],
                        "pages_without_text": ocr_result['pages_without_text'],
                        "chunks_emitted": 0,
                        "lang_undetected_count": 1 if ocr_result['lang_undetected'] else 0
                    })
                    mongodb_service.update_job_counters(job_id, {
                        "files_failed": 1,
                        "pages_processed": ocr_result['total_page_count'],
                        "pages_without_text": ocr_result['pages_without_text'],
                        "lang_undetected_count": 1 if ocr_result['lang_undetected'] else 0
                    })
                    files_failed += 1
                    continue
                
                # Store OCR JSON file (if not exists or force)
                if not existing_json_file_id or force:
                    json_chunks = []
                    for chunk in ocr_result['chunks']:
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
                    
                    json_content = json.dumps(json_chunks, ensure_ascii=False, indent=2)
                    json_bytes = json_content.encode('utf-8')
                    
                    output_file_info = gdrive_service.upload_file_from_bytes(
                        file_bytes=json_bytes,
                        file_name=output_file_name,
                        folder_id=output_parent_folder_id,
                        mime_type="application/json"
                    )
                    
                    output_drive_file_id = output_file_info['file_id']
                    mongodb_service.update_doc_output(doc_id, output_drive_file_id, output_path)
                else:
                    logger.info(f"OCR JSON already exists for {file_name}, skipping upload")
                    output_drive_file_id = existing_json_file_id
                    mongodb_service.update_doc_output(doc_id, output_drive_file_id, output_path)
                    mongodb_service.update_doc_status(doc_id, "skipped", "OCR JSON already exists")
                
                # Update OCR counts
                mongodb_service.update_doc_counts(doc_id, {
                    "pages_total": ocr_result['total_page_count'],
                    "pages_without_text": ocr_result['pages_without_text'],
                    "chunks_emitted": ocr_result['chunks_emitted'],
                    "lang_undetected_count": 1 if ocr_result['lang_undetected'] else 0
                })
                
                mongodb_service.update_job_counters(job_id, {
                    "files_processed": 1,
                    "pages_processed": ocr_result['total_page_count'],
                    "pages_without_text": ocr_result['pages_without_text'],
                    "chunks_emitted": ocr_result['chunks_emitted'],
                    "lang_undetected_count": 1 if ocr_result['lang_undetected'] else 0
                })
                
                files_processed += 1
                
                # Extract metadata for embedding
                if not skip_embedding:
                    try:
                        mongodb_service.update_doc_status(doc_id, "processing", "Extracting metadata and generating embeddings")
                        
                        # Extract full text for metadata extraction
                        full_text, _, _ = ocr_service.extract_text(
                            file_bytes=file_bytes,
                            file_name=file_name,
                            mime_type=mime_type
                        )
                        
                        # Extract metadata using GPT
                        metadata = await self.extract_metadata(full_text, metadata_keys)
                        
                        # Generate embeddings and upsert to Pinecone
                        vectors_to_upsert = []
                        for chunk in ocr_result['chunks']:
                            chunk_text = chunk['text']
                            chunk_index = chunk['chunk_index']
                            page_index = chunk['page_index']
                            
                            # Generate embedding
                            embedding = self.generate_embedding(chunk_text)
                            
                            # Prepare metadata for Pinecone
                            chunk_metadata = {
                                "dataset_name": dataset_name,
                                "source_file": file_name,
                                "text": chunk_text,
                                "chunk_index": chunk_index,
                                "page_index": page_index,
                                "source_url": source_url
                            }
                            
                            # Add extracted metadata
                            chunk_metadata.update(metadata)
                            
                            # Normalize metadata for Pinecone compatibility
                            chunk_metadata = self._normalize_metadata_for_pinecone(chunk_metadata)
                            
                            # Generate unique ID with page_index for better idempotence
                            doc_id_str = metadata.get("document_id", f"doc_{file_name}_{files_processed}")
                            doc_id_str = str(doc_id_str).replace(" ", "_").replace("/", "_")[:50]
                            vector_id = f"{doc_id_str}_p{page_index}_c{chunk_index}"
                            
                            vectors_to_upsert.append({
                                "id": vector_id,
                                "values": embedding,
                                "metadata": chunk_metadata
                            })
                            
                            embeddings_stored += 1
                        
                        # Upsert to Pinecone
                        if vectors_to_upsert:
                            self.pinecone_index.upsert(vectors=vectors_to_upsert)
                            
                            # Mark as embedded in MongoDB
                            mongodb_service.mark_doc_embedded(
                                doc_id=doc_id,
                                embeddings_count=len(vectors_to_upsert),
                                pinecone_index=self.pinecone_index_name
                            )
                            
                            mongodb_service.update_job_embedding_counters(job_id, {
                                "files_embedded": 1,
                                "embeddings_stored": len(vectors_to_upsert)
                            })
                            
                            files_embedded += 1
                            logger.success(
                                f"Upserted {len(vectors_to_upsert)} vectors to Pinecone for: {file_name}"
                            )
                        
                        mongodb_service.update_doc_status(doc_id, "ok", "Processed and embedded successfully")
                        
                    except Exception as e:
                        logger.error(f"Error embedding file {file_name}: {e}")
                        mongodb_service.update_doc_status(doc_id, "ok", f"OCR completed but embedding failed: {str(e)}")
                        mongodb_service.update_job_embedding_counters(job_id, {"files_embedding_failed": 1})
                        files_embedding_failed += 1
                        if force:
                            raise
                else:
                    mongodb_service.update_doc_status(doc_id, "ok", "OCR completed, embedding skipped (already embedded)")
                    files_skipped += 1
                
            except Exception as e:
                logger.error(f"Error processing file {file_name}: {e}")
                mongodb_service.update_doc_status(doc_id, "failed", str(e))
                mongodb_service.update_job_counters(job_id, {"files_failed": 1})
                files_failed += 1
                if force:
                    raise
        
        # Determine final job status
        if files_failed == 0:
            job_status = "completed"
        elif files_processed > 0 or files_embedded > 0:
            job_status = "completed_with_errors"
        else:
            job_status = "failed"
        
        mongodb_service.finish_job(job_id, job_status)
        
        logger.success(
            f"Ingestion pipeline completed: {files_processed} files processed, "
            f"{files_embedded} embedded, {embeddings_stored} embeddings stored"
        )
        
        return {
            "status": "success",
            "dataset_name": dataset_name,
            "files_processed": files_processed,
            "files_embedded": files_embedded,
            "files_skipped": files_skipped,
            "embeddings_stored": embeddings_stored,
            "metadata_extracted": True,
            "pinecone_index": self.pinecone_index_name,
            "job_id": job_id,
            "message": "Ingestion pipeline completed successfully."
        }

