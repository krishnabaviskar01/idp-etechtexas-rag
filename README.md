# idp-etechtexas-rag

Intelligent Document Processing Pipeline with RAG and LangGraph Agents

## FastAPI Google Drive Upload Service

A FastAPI application for uploading files to Google Drive with structured logging using Loguru.

### Features

- ✅ FastAPI REST API
- ✅ Google Drive file upload
- ✅ Loguru logging with file rotation
- ✅ Configuration management with environment variables
- ✅ Error handling and validation
- ✅ File upload endpoint

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
Upload a file via multipart form data

**Request:**
- `file`: File to upload (multipart/form-data)
- `folder_id`: (Optional) Google Drive folder ID
- `custom_name`: (Optional) Custom file name

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@/path/to/your/file.pdf" \
  -F "folder_id=your_folder_id" \
  -F "custom_name=my_file.pdf"
```

### Project Structure

```
idp-etechtexas-rag/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── logger.py            # Loguru logging setup
│   └── services/
│       ├── __init__.py
│       └── gdrive_service.py  # Google Drive service
├── logs/                     # Log files (auto-created)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### Logging

Logs are written to both console (colored) and file (`logs/app.log`) with:
- Automatic rotation at 10MB
- 7-day retention
- ZIP compression
- Thread-safe logging

### Configuration

All configuration is managed through environment variables (see `.env.example`). The application uses `pydantic-settings` for type-safe configuration management.

### Notes

- On first run, you'll be prompted to authorize the application in your browser
- The access token will be saved to `token.json` for future use
- Credentials are stored in `.env` file (ensure it's in `.gitignore` - already included)
- Never commit your `.env` file to version control
