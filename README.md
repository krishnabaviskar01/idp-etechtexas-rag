# idp-etechtexas-rag

Intelligent Document Processing Pipeline with RAG and LangGraph Agents

## FastAPI Document Processing Service

A FastAPI application for uploading files to Google Drive, OCR text extraction, intelligent chunking, progress tracking with MongoDB, metadata extraction using GPT-4o-mini, embedding generation, and Pinecone vector storage for RAG applications.

### Features

- ✅ FastAPI REST API with router-based architecture
- ✅ Multiple file upload support to Google Drive
- ✅ **OCR Text Extraction** - PDF, DOC/DOCX, TXT file support
- ✅ **Intelligent Chunking** - LangChain RecursiveCharacterTextSplitter with configurable size and overlap
- ✅ **Language Detection** - Automatic language detection using langdetect
- ✅ **MongoDB Progress Tracking** - Job and document-level progress tracking with idempotent operations (one job per dataset, one doc per file)
- ✅ Google Drive integration with automatic folder creation
- ✅ Dataset-based organization (create folders by dataset name)
- ✅ Mirrored folder structure for outputs
- ✅ **End-to-End Ingestion Pipeline** - OCR, metadata extraction (GPT-4o-mini), embeddings (text-embedding-3-small), and Pinecone vector storage
- ✅ **Source URL Tracking** - Google Drive public URLs stored in MongoDB, OCR JSON, and Pinecone metadata
- ✅ **Page Index Tracking** - Page index included in Pinecone metadata and vector IDs for better idempotence
- ✅ **Idempotent Operations** - Re-running pipelines updates existing records instead of creating duplicates
- ✅ Pydantic schemas for request/response validation
- ✅ Loguru logging with environment-based configuration
- ✅ Configuration management with environment variables
- ✅ Comprehensive error handling and validation
- ✅ Type-safe API documentation (OpenAPI/Swagger)

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   **Note:** If you're using Python 3.13, some packages may require Visual Studio Build Tools for compilation. Consider using Python 3.11 or 3.12 for better wheel support.

2. **Google Drive API Setup:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Drive API
   - Create OAuth 2.0 credentials (Desktop application)
   - Copy the following values from your credentials JSON:
     - `client_id` → `GOOGLE_DRIVE_CLIENT_ID`
     - `client_secret` → `GOOGLE_DRIVE_CLIENT_SECRET`
     - `project_id` → `GOOGLE_DRIVE_PROJECT_ID` (optional)

3. **MongoDB Setup:**
   
   **Option 1: MongoDB Atlas (Recommended for Production)**
   - Create a MongoDB Atlas account at [mongodb.com](https://www.mongodb.com/cloud/atlas)
   - Create a cluster and get your connection details
   - Add the following to your `.env` file:
     ```env
     MONGO_USERNAME=your_username
     MONGO_PASSWORD=your_password
     MONGO_CLUSTER_URL=your-cluster.mongodb.net
     MONGO_APP_NAME=your_app_name  # Optional
     MONGODB_DATABASE=central_acts
     ```
   
   **Option 2: Local MongoDB (For Development)**
   - Install MongoDB locally
   - Add to your `.env` file:
     ```env
     MONGODB_URI=mongodb://localhost:27017
     MONGODB_DATABASE=central_acts
     ```

4. **OpenAI Setup:**
   - Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
   - Add to your `.env` file:
     ```env
     OPENAI_API_KEY=sk-your-api-key-here
     ```

5. **Pinecone Setup:**
   - Create a Pinecone account at [pinecone.io](https://www.pinecone.io/)
   - Get your API key from the dashboard
   - Add to your `.env` file:
     ```env
     PINECONE_API_KEY=your-pinecone-api-key
     PINECONE_INDEX_NAME=idp-etechtexas-rag  # Optional, defaults to this
     ```
   - The index will be automatically created if it doesn't exist (1536 dimensions for text-embedding-3-small)

6. **Environment Configuration:**
   - Create a `.env` file in the project root
   - Add your configuration:
     ```env
     # Application
     ENV=local  # Set to 'local' for file logging, otherwise stdout logging
     
     # Google Drive API Credentials
     GOOGLE_DRIVE_CLIENT_ID=your_client_id_here
     GOOGLE_DRIVE_CLIENT_SECRET=your_client_secret_here
     GOOGLE_DRIVE_PROJECT_ID=your_project_id  # Optional
     GOOGLE_DRIVE_TOKEN_FILE=token.json
     GOOGLE_DRIVE_FOLDER_ID=1ZT_FuaOCd6DmoAcOXbMhH2XmXCrLHovy  # Default folder ID
     
     # MongoDB Configuration (choose one option)
     # Option 1: MongoDB Atlas
     MONGO_USERNAME=your_username
     MONGO_PASSWORD=your_password
     MONGO_CLUSTER_URL=your-cluster.mongodb.net
     MONGO_APP_NAME=your_app_name  # Optional
     MONGODB_DATABASE=central_acts
     
     # Option 2: Local MongoDB
     # MONGODB_URI=mongodb://localhost:27017
     # MONGODB_DATABASE=central_acts
     
     # OpenAI Configuration
     OPENAI_API_KEY=sk-your-api-key-here
     
     # Pinecone Configuration
     PINECONE_API_KEY=your-pinecone-api-key
     PINECONE_INDEX_NAME=idp-etechtexas-rag  # Optional
     ```

5. **Run the application:**
   ```bash
   python -m app.main
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn app.main:app --reload
   ```

### API Endpoints

#### `GET /`
Root endpoint - Returns application information

#### `GET /health`
Health check endpoint - Returns service status

#### `POST /upload`
Upload one or multiple files to Google Drive

**Request:**
- `files`: List of files to upload (multipart/form-data) - **supports multiple files**
- `folder_id`: (Optional) Google Drive folder ID (parent folder)
- `dataset_name`: (Optional) Dataset name - creates a folder with this name and uploads all files inside

**Example using curl (single file):**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "files=@/path/to/your/file.pdf" \
  -F "dataset_name=my_dataset"
```

**Example using curl (multiple files):**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "files=@/path/to/file1.pdf" \
  -F "files=@/path/to/file2.pdf" \
  -F "files=@/path/to/file3.pdf" \
  -F "dataset_name=my_dataset" \
  -F "folder_id=parent_folder_id"
```

**Response:**
Returns a structured response with:
- Upload status for each file
- Google Drive file metadata (file_id, links, etc.)
- Dataset folder information (if `dataset_name` provided)
- Error details for any failed uploads

#### `POST /ocr/process`
Process OCR and chunking for files in a Google Drive dataset folder

**Request Body (JSON):**
```json
{
  "dataset_name": "The Constitution Dataset",
  "drive_folder_id": "optional; defaults to env/constant",
  "doc_id": "optional; auto-generated if not provided",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "force": false,
  "log_level": "INFO"
}
```

**Request Parameters:**
- `dataset_name` (required): Name of the dataset folder to process
- `drive_folder_id` (optional): Google Drive folder ID (defaults to `GOOGLE_DRIVE_FOLDER_ID`)
- `doc_id` (optional): Override document ID generation (auto-generated if not provided)
- `chunk_size` (optional): Chunk size in characters (default: 512)
- `chunk_overlap` (optional): Chunk overlap in characters (default: 50)
- `force` (optional): Force reprocessing even if output exists (default: false)
- `log_level` (optional): Log level (default: "INFO")

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/ocr/process" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "The Constitution Dataset",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "force": false
  }'
```

**Response:**
Returns a structured response with:
- `dataset_name`: Name of the processed dataset
- `input_folder_id`: Google Drive input folder ID
- `output_folder_id`: Google Drive output folder ID
- `job_id`: MongoDB job ID for tracking
- `files_discovered`: Number of files discovered
- `files_processed`: Number of files processed successfully
- `files_failed`: Number of files that failed
- `metrics`: Processing metrics (pages, chunks, language detection, etc.)
- `documents`: List of document statuses with paths and status

**Output Structure:**
- Output files are written to: `/<root>/Optical Character Recognition/<dataset_name>/.../<basename>.json`
- Folder structure is mirrored from input
- Each source file produces exactly one JSON file with chunked data

**JSON Output Schema:**
Each chunk record contains (in strict order):
1. `doc_id`: Document identifier (format: `doc:{slug}@{YYYY-MM-DD}`)
2. `file_name`: Original file name
3. `language`: Detected language code (2-letter ISO or "und")
4. `total_page_count`: Total number of pages
5. `page_index`: Page index (0-based)
6. `chunk_index`: Chunk index (0-based)
7. `text`: Chunk text content
8. `source_url`: Google Drive public view URL (`https://drive.google.com/file/d/{file_id}/view`)

#### `POST /ingestion/pipeline`
End-to-end ingestion pipeline: OCR, metadata extraction, embedding generation, and Pinecone storage

**Request Body (JSON):**
```json
{
  "chunk_overlap": 50,
  "chunk_size": 512,
  "dataset_name": "Bombay Highcourt Judgements",
  "drive_folder_id": "1ZT_FuaOCd6DmoAcOXbMhH2XmXCrLHovy",
  "force": false,
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
```

**Request Parameters:**
- `dataset_name` (required): Name of the dataset
- `drive_folder_id` (required): Google Drive folder ID containing documents
- `chunk_size` (optional): Chunk size in characters (default: 512)
- `chunk_overlap` (optional): Chunk overlap in characters (default: 50)
- `force` (optional): Force reprocessing even if already processed (default: false)
- `log_level` (optional): Log level (default: "INFO")
- `metadata_keys` (optional): Custom metadata schema. If omitted, uses default legal metadata schema.

**Pipeline Flow:**
1. **Google Drive Input**: Reads files from the specified folder (recursively)
2. **OCR + Chunking**: Performs OCR extraction and intelligent chunking using existing `OCRService`
3. **OCR JSON Storage**: Stores OCR JSON files in mirror folder structure (`Optical Character Recognition/<dataset_name>/...`)
4. **MongoDB Tracking**: Creates/updates job and document records (idempotent by dataset_name)
5. **Metadata Extraction**: Concatenates full text and extracts structured metadata using GPT-4o-mini
6. **Embedding Generation**: Generates embeddings for each chunk using text-embedding-3-small
7. **Pinecone Storage**: Upserts embeddings with metadata to Pinecone vector database
8. **Embedding Tracking**: Marks documents as embedded in MongoDB to prevent re-embedding

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/ingestion/pipeline" \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_overlap": 50,
    "chunk_size": 512,
    "dataset_name": "Bombay Highcourt Judgements",
    "drive_folder_id": "1ZT_FuaOCd6DmoAcOXbMhH2XmXCrLHovy",
    "force": false,
    "log_level": "INFO"
  }'
```

**Response:**
```json
{
  "status": "success",
  "dataset_name": "Bombay Highcourt Judgements",
  "files_processed": 10,
  "files_embedded": 10,
  "files_skipped": 0,
  "embeddings_stored": 1800,
  "metadata_extracted": true,
  "pinecone_index": "idp-etechtexas-rag",
  "job_id": "507f1f77bcf86cd799439011",
  "message": "Ingestion pipeline completed successfully."
}
```

**Pinecone Vector Structure:**
Each vector stored in Pinecone includes:
- `id`: Unique identifier (`{document_id}_p{page_index}_c{chunk_index}`)
  - Example: `doc_case123_p0_c5` (page 0, chunk 5)
  - Includes page_index for proper disambiguation and idempotence
- `values`: Embedding vector (1536 dimensions)
- `metadata`: Dictionary containing:
  - `dataset_name`: Dataset name
  - `source_file`: Original file name
  - `text`: Chunk text content
  - `chunk_index`: Chunk index (0-based)
  - `page_index`: Page index (0-based)
  - `source_url`: Google Drive public view URL
  - All extracted metadata fields (document_id, title, court_name, case_number, etc.)

**Metadata Extraction:**
- Uses GPT-4o-mini with JSON response format
- Dynamically adapts to custom `metadata_keys` schema if provided
- Default schema includes legal document fields (flat structure):
  - `document_id`, `title`, `court_name`, `case_number`, `case_type`, `decision_date`, `coram`, `petitioner`, `respondent`, `key_issues`
- All metadata values are strings (arrays converted to comma-separated strings)
- Metadata is attached to all chunks of the same document
- If extraction fails, empty metadata is used with default values

**OCR JSON Storage:**
- Ingestion pipeline stores OCR JSON files in the same mirror folder structure as the OCR endpoint
- Output location: `Optical Character Recognition/<dataset_name>/.../<basename>.json`
- JSON files include `source_url` for each chunk
- Skips upload if JSON already exists (unless `force=true`)

**MongoDB Integration:**
- Creates/updates job records idempotently (one job per dataset_name)
- Creates/updates document records idempotently (one doc per file per dataset)
- Tracks both OCR and embedding progress separately
- Marks documents as embedded to prevent re-embedding (unless `force=true`)
- Stores `source_url` in document records for easy access

**Notes:**
- The Pinecone index is automatically created if it doesn't exist (1536 dimensions, cosine similarity)
- Embeddings are generated on-the-fly and upserted immediately (no batching delay)
- All chunks from a document share the same extracted metadata
- Documents with no extractable text are skipped
- Re-running the pipeline for the same dataset updates existing MongoDB records instead of creating duplicates
- Vector IDs include page_index for proper idempotence and disambiguation

### Idempotent Operations

The ingestion pipeline is designed to be idempotent:

**MongoDB Job Management:**
- Only one job record exists per `dataset_name` (enforced by unique index)
- Re-running the pipeline updates the existing job instead of creating a new one
- Job counters are reset at the start of each run
- `created_at` timestamp is preserved to track when the dataset was first processed

**MongoDB Document Management:**
- Only one document record exists per `source_drive_file_id` + `dataset_name` combination (enforced by unique compound index)
- Re-running the pipeline updates existing documents instead of creating duplicates
- Document status and counts are reset for new runs
- `created_at` timestamp is preserved

**Embedding Prevention:**
- Documents marked as `embedded: true` in MongoDB are skipped during embedding (unless `force=true`)
- Prevents duplicate embeddings in Pinecone
- Allows selective re-embedding of specific documents when needed

**Vector ID Format:**
- Format: `{document_id}_p{page_index}_c{chunk_index}`
- Example: `doc_case123_p0_c5` (document "case123", page 0, chunk 5)
- Includes page_index for proper disambiguation
- Ensures re-runs overwrite existing vectors (upsert behavior)

### Data Fields

**Source URL (`source_url`):**
- Google Drive public view URL format: `https://drive.google.com/file/d/{file_id}/view`
- Stored in:
  - MongoDB `ocr_docs` collection
  - OCR JSON files (each chunk)
  - Pinecone metadata (each vector)
- Enables deep linking to source documents from search results

**Page Index (`page_index`):**
- Included in OCR JSON chunks (already present)
- Added to Pinecone metadata for each vector
- Included in vector ID for proper disambiguation
- Helps identify which page a chunk came from

### Supported File Types

- **PDF**: Extracted using PyMuPDF with reading order preference
- **DOC/DOCX**: Extracted using python-docx
- **TXT**: UTF-8 text files

**Note:** Image-only PDFs are handled gracefully - pages without text are counted but don't produce chunks. Google Docs native files are skipped in v1.

### Project Structure

```
idp-etechtexas-rag/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management (Pydantic Settings)
│   ├── logger.py            # Loguru logging setup
│   ├── routers/             # API route handlers
│   │   ├── __init__.py
│   │   ├── health.py        # Health check endpoints
│   │   ├── upload.py        # File upload endpoints
│   │   ├── ocr.py           # OCR processing endpoints
│   │   └── ingestion.py     # Ingestion pipeline endpoints
│   ├── schemas/             # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── health.py        # Health check schemas
│   │   ├── upload.py        # Upload-related schemas
│   │   ├── ocr.py           # OCR-related schemas
│   │   └── ingestion.py     # Ingestion-related schemas
│   └── services/            # Business logic services
│       ├── __init__.py
│       ├── gdrive_service.py     # Google Drive API integration
│       ├── ocr_service.py         # OCR text extraction and chunking
│       ├── mongodb_service.py     # MongoDB progress tracking (idempotent)
│       ├── ingestion_service.py   # End-to-end ingestion pipeline
│       └── service_manager.py     # Service instance management
│   └── langgraph/           # LangGraph agents (future)
│       └── __init__.py
├── logs/                     # Log files (auto-created, organized by date/hour)
├── requirements.txt
├── .env                      # Environment variables (not in git)
├── .gitignore
└── README.md
```

### Logging

Logging behavior depends on the `ENV` environment variable:

**When `ENV=local`:**
- Logs are written to files in `logs/YYYY-MM-DD/HH-MM.log` structure
- Automatic rotation at 2MB
- 10-day retention
- Thread-safe logging with `enqueue=True`

**When `ENV` is not set or set to other values:**
- Logs are written to stdout (console)
- Colored output for better readability
- Thread-safe logging

**Log Format:**
```
{time:YYYY-MM-DD HH:mm:ss.SSS} |{level: <7}| {name}:{function}:{line} | {message}
```

### MongoDB Collections

The application uses two MongoDB collections for progress tracking:

**`ocr_jobs`** - One document per dataset (idempotent)
- Fields: `dataset_name`, `input_folder_id`, `output_folder_id`, `status`, `counters`, `embedding_counters`, `created_at`, `updated_at`, `tz`
- Status values: `running`, `completed`, `completed_with_errors`, `failed`
- Unique index: `{ dataset_name: 1 }` (ensures only one job per dataset)
- Indexes: `{ status: 1 }`, `{ created_at: -1 }`
- Counters track OCR progress: `files_discovered`, `files_processed`, `files_failed`, `pages_processed`, `chunks_emitted`, etc.
- Embedding counters track vector storage: `files_embedded`, `embeddings_stored`, `files_embedding_failed`

**`ocr_docs`** - One document per source file per dataset (idempotent)
- Fields: `job_id`, `dataset_name`, `source_drive_file_id`, `source_path`, `source_url`, `output_drive_file_id`, `output_path`, `status`, `message`, `counts`, `embedded`, `embeddings_count`, `pinecone_index`, `embedded_at`, `created_at`, `updated_at`, `tz`
- Status values: `queued`, `processing`, `ok`, `skipped`, `failed`
- Unique compound index: `{ dataset_name: 1, source_drive_file_id: 1 }` (ensures one doc per file per dataset)
- Indexes: `{ job_id: 1 }`, `{ status: 1 }`, `{ source_drive_file_id: 1 }`
- `source_url`: Google Drive public view URL for easy access
- `embedded`: Boolean flag indicating if document has been embedded in Pinecone
- `embeddings_count`: Number of embeddings stored for this document
- `pinecone_index`: Name of Pinecone index where embeddings are stored

### Configuration

All configuration is managed through environment variables. The application uses `pydantic-settings` for type-safe configuration management.

**Required Environment Variables:**
- `GOOGLE_DRIVE_CLIENT_ID`: Google Drive OAuth client ID
- `GOOGLE_DRIVE_CLIENT_SECRET`: Google Drive OAuth client secret
- `OPENAI_API_KEY`: OpenAI API key for embeddings and metadata extraction
- `PINECONE_API_KEY`: Pinecone API key for vector storage

**Optional Environment Variables:**
- `GOOGLE_DRIVE_PROJECT_ID`: Google Cloud project ID
- `GOOGLE_DRIVE_TOKEN_FILE`: Token file path (default: `token.json`)
- `GOOGLE_DRIVE_FOLDER_ID`: Default Google Drive folder ID
- `MONGO_USERNAME`, `MONGO_PASSWORD`, `MONGO_CLUSTER_URL`: MongoDB Atlas credentials
- `MONGODB_URI`: Local MongoDB connection string (alternative to Atlas)
- `MONGODB_DATABASE`: MongoDB database name (default: `central_acts`)
- `PINECONE_INDEX_NAME`: Pinecone index name (default: `idp-etechtexas-rag`)
- `ENV`: Environment setting for logging (`local` for file logging)

### Architecture

The application follows FastAPI best practices:

- **Router-based structure**: Endpoints organized by feature in separate router files
- **Pydantic schemas**: Request/response models defined in `schemas/` folder for validation and documentation
- **Service layer**: Business logic separated into service classes
- **Dependency injection**: Services managed centrally and injected into routes
- **Type safety**: Full type hints and Pydantic validation throughout
- **Error handling**: Comprehensive error handling with appropriate HTTP status codes
- **Logging**: Structured logging using Loguru throughout

### Key Features Details

**Text Extraction:**
- PDF: Uses PyMuPDF with block-based extraction for better reading order, falls back to regular text extraction
- DOC/DOCX: Extracts paragraphs using python-docx
- TXT: Reads as UTF-8 text files
- Text normalization: Unicode NFC, space collapsing, paragraph preservation

**Chunking:**
- Uses LangChain `RecursiveCharacterTextSplitter`
- Configurable chunk size and overlap (default: 512 chars, 50 overlap)
- Separator priority: paragraph breaks (`\n\n`), line breaks (`\n`), sentence endings (`. `, `? `, `! `), spaces
- Per-page chunking for PDFs; single-page for DOC/DOCX/TXT
- Empty chunks are automatically filtered out

**Language Detection:**
- Uses `langdetect` library
- Falls back to `detect_langs()` with probability threshold (≥0.75)
- Returns "und" if language cannot be detected

**Progress Tracking:**
- Real-time job and document status tracking in MongoDB
- Counters for files, pages, chunks, and language detection
- Separate embedding counters for tracking vector storage progress
- Idempotent operations: re-running pipelines updates existing records instead of creating duplicates
- UTC timestamps with timezone metadata
- Proper indexing for efficient queries
- Unique constraints ensure data integrity (one job per dataset, one doc per file per dataset)

### Dependencies

Key dependencies:
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `google-api-python-client`: Google Drive API
- `pymupdf`: PDF text extraction
- `python-docx`: DOC/DOCX text extraction
- `langchain-text-splitters`: Text chunking
- `langdetect`: Language detection
- `pymongo`: MongoDB driver
- `openai`: OpenAI API client for embeddings and GPT
- `pinecone-client`: Pinecone vector database client
- `loguru`: Logging
- `pydantic`: Data validation

See `requirements.txt` for complete list.

### Notes

- On first run, you'll be prompted to authorize the application in your browser
- The access token will be saved to `token.json` for future use
- Credentials are stored in `.env` file (ensure it's in `.gitignore` - already included)
- Never commit your `.env` file to version control
- MongoDB indexes are automatically created on service initialization
- Unique indexes enforce one job per dataset and one document per file per dataset
- Output JSON files maintain strict key ordering as per schema
- Documents with no extractable text are marked as failed and don't produce empty JSON files
- Source URLs (`source_url`) are stored in MongoDB, OCR JSON, and Pinecone metadata for easy access
- Vector IDs include page_index for proper disambiguation (`{doc_id}_p{page_index}_c{chunk_index}`)
- Re-running ingestion pipelines updates existing MongoDB records instead of creating duplicates

### Troubleshooting

**MongoDB Connection Issues:**
- Verify MongoDB credentials in `.env` file
- Check network connectivity to MongoDB Atlas
- Ensure MongoDB is running (for local installations)

**Google Drive API Issues:**
- Verify OAuth credentials in `.env`
- Check token.json file permissions
- Re-authenticate if token expires

**Python 3.13 Compatibility:**
- Some packages may require Visual Studio Build Tools
- Consider using Python 3.11 or 3.12 for better compatibility
- Use `pip install --only-binary :all:` to force wheel-only installation

**Ingestion Pipeline Issues:**
- **Duplicate records**: If you see duplicate job/document errors, ensure unique indexes are created properly. Existing duplicates may need manual cleanup before unique indexes can be applied.
- **Missing source_url**: Older documents may not have `source_url`. The pipeline will add it on the next run.
- **Pinecone metadata errors**: Ensure all metadata values are strings, numbers, booleans, or lists of strings. Nested objects are automatically converted to JSON strings.
- **Vector ID conflicts**: Vector IDs include page_index to prevent conflicts. Format: `{doc_id}_p{page_index}_c{chunk_index}`

**Pinecone Issues:**
- Verify `PINECONE_API_KEY` is set correctly in `.env`
- Check that the index name matches (`PINECONE_INDEX_NAME` defaults to `idp-etechtexas-rag`)
- The index is automatically created if it doesn't exist (1536 dimensions, cosine similarity)
- Ensure metadata values don't exceed Pinecone's size limits (very long strings are truncated to 1000 chars)

### License

[Add your license here]
