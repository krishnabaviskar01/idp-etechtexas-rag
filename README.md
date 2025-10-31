# idp-etechtexas-rag

Intelligent Document Processing Pipeline with RAG and LangGraph Agents

## FastAPI Google Drive Upload Service

A FastAPI application for uploading files to Google Drive with structured logging using Loguru.

### Features

- ✅ FastAPI REST API with router-based architecture
- ✅ Multiple file upload support
- ✅ Google Drive integration with automatic folder creation
- ✅ Dataset-based organization (create folders by dataset name)
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

2. **Google Drive API Setup:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Drive API
   - Create OAuth 2.0 credentials (Desktop application)
   - Copy the following values from your credentials JSON:
     - `client_id` → `GOOGLE_DRIVE_CLIENT_ID`
     - `client_secret` → `GOOGLE_DRIVE_CLIENT_SECRET`
     - `project_id` → `GOOGLE_DRIVE_PROJECT_ID` (optional)

3. **Environment Configuration:**
   - Copy `.env.example` to `.env`
   - Add your Google Drive credentials:
     ```env
     ENV=local  # Set to 'local' for file logging, otherwise stdout logging
     GOOGLE_DRIVE_CLIENT_ID=your_client_id_here
     GOOGLE_DRIVE_CLIENT_SECRET=your_client_secret_here
     GOOGLE_DRIVE_PROJECT_ID=your_project_id  # Optional
     GOOGLE_DRIVE_TOKEN_FILE=token.json
     GOOGLE_DRIVE_FOLDER_ID=your_folder_id  # Optional
     ```

4. **Run the application:**
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

**Features:**
- Upload multiple files in a single request
- Automatic folder creation if `dataset_name` is provided
- Detailed response with success/failure status for each file

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
│   │   └── upload.py        # File upload endpoints
│   ├── schemas/             # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── health.py        # Health check schemas
│   │   └── upload.py        # Upload-related schemas
│   └── services/            # Business logic services
│       ├── __init__.py
│       ├── gdrive_service.py     # Google Drive API integration
│       └── service_manager.py    # Service instance management
├── logs/                     # Log files (auto-created, organized by date/hour)
├── requirements.txt
├── .env.example
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

### Configuration

All configuration is managed through environment variables (see `.env.example`). The application uses `pydantic-settings` for type-safe configuration management.

### Architecture

The application follows FastAPI best practices:

- **Router-based structure**: Endpoints organized by feature in separate router files
- **Pydantic schemas**: Request/response models defined in `schemas/` folder for validation and documentation
- **Service layer**: Business logic separated into service classes
- **Dependency injection**: Services managed centrally and injected into routes
- **Type safety**: Full type hints and Pydantic validation throughout

### Notes

- On first run, you'll be prompted to authorize the application in your browser
- The access token will be saved to `token.json` for future use
- Credentials are stored in `.env` file (ensure it's in `.gitignore` - already included)
- Never commit your `.env` file to version control
