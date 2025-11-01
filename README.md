# idp-etechtexas-rag

Intelligent Document Processing Pipeline with RAG and LangGraph Agents

## FastAPI Document Processing Service

A FastAPI application for uploading files to Google Drive, OCR text extraction, intelligent chunking, and progress tracking with MongoDB.

### Features

- ✅ FastAPI REST API with router-based architecture
- ✅ Multiple file upload support to Google Drive
- ✅ **OCR Text Extraction** - PDF, DOC/DOCX, TXT file support
- ✅ **Intelligent Chunking** - LangChain RecursiveCharacterTextSplitter with configurable size and overlap
- ✅ **Language Detection** - Automatic language detection using langdetect
- ✅ **MongoDB Progress Tracking** - Job and document-level progress tracking
- ✅ Google Drive integration with automatic folder creation
- ✅ Dataset-based organization (create folders by dataset name)
- ✅ Mirrored folder structure for outputs
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

4. **Environment Configuration:**
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
│   │   └── ocr.py           # OCR processing endpoints
│   ├── schemas/             # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── health.py        # Health check schemas
│   │   ├── upload.py        # Upload-related schemas
│   │   └── ocr.py           # OCR-related schemas
│   └── services/            # Business logic services
│       ├── __init__.py
│       ├── gdrive_service.py     # Google Drive API integration
│       ├── ocr_service.py         # OCR text extraction and chunking
│       ├── mongodb_service.py     # MongoDB progress tracking
│       └── service_manager.py     # Service instance management
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

**`ocr_jobs`** - One document per API run
- Fields: `dataset_name`, `input_folder_id`, `output_folder_id`, `status`, `counters`, `created_at`, `updated_at`, `tz`
- Status values: `running`, `completed`, `completed_with_errors`, `failed`
- Indexes: `{ status: 1 }`, `{ created_at: -1 }`

**`ocr_docs`** - One document per source file
- Fields: `job_id`, `dataset_name`, `source_drive_file_id`, `source_path`, `output_drive_file_id`, `output_path`, `status`, `message`, `counts`, `created_at`, `updated_at`, `tz`
- Status values: `queued`, `processing`, `ok`, `skipped`, `failed`
- Indexes: `{ job_id: 1 }`, `{ status: 1 }`

### Configuration

All configuration is managed through environment variables. The application uses `pydantic-settings` for type-safe configuration management.

**Required Environment Variables:**
- `GOOGLE_DRIVE_CLIENT_ID`: Google Drive OAuth client ID
- `GOOGLE_DRIVE_CLIENT_SECRET`: Google Drive OAuth client secret

**Optional Environment Variables:**
- `GOOGLE_DRIVE_PROJECT_ID`: Google Cloud project ID
- `GOOGLE_DRIVE_TOKEN_FILE`: Token file path (default: `token.json`)
- `GOOGLE_DRIVE_FOLDER_ID`: Default Google Drive folder ID
- `MONGO_USERNAME`, `MONGO_PASSWORD`, `MONGO_CLUSTER_URL`: MongoDB Atlas credentials
- `MONGODB_URI`: Local MongoDB connection string (alternative to Atlas)
- `MONGODB_DATABASE`: MongoDB database name (default: `central_acts`)
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
- UTC timestamps with timezone metadata
- Proper indexing for efficient queries

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
- `loguru`: Logging
- `pydantic`: Data validation

See `requirements.txt` for complete list.

### Notes

- On first run, you'll be prompted to authorize the application in your browser
- The access token will be saved to `token.json` for future use
- Credentials are stored in `.env` file (ensure it's in `.gitignore` - already included)
- Never commit your `.env` file to version control
- MongoDB indexes are automatically created on service initialization
- Output JSON files maintain strict key ordering as per schema
- Documents with no extractable text are marked as failed and don't produce empty JSON files

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

### License

[Add your license here]
