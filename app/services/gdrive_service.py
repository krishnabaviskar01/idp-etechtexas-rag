"""
Google Drive service for file uploads
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from loguru import logger


class GoogleDriveService:
    """Service for interacting with Google Drive API"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    @staticmethod
    def _parse_redirect_uris(redirect_uris: Any) -> list:
        """Parse redirect URIs from string or list"""
        if isinstance(redirect_uris, str):
            # Split by comma and strip whitespace
            return [uri.strip() for uri in redirect_uris.split(',')]
        elif isinstance(redirect_uris, list):
            return redirect_uris
        else:
            return ['http://localhost']
    
    def __init__(self, client_config: Dict[str, Any], token_file: str):
        """
        Initialize Google Drive service
        
        Args:
            client_config: Dictionary containing Google OAuth client configuration
            token_file: Path to store access token
        """
        self.client_config = client_config
        self.token_file = token_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate and build Google Drive service"""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                logger.info("Loaded existing credentials from token file")
            except Exception as e:
                logger.warning(f"Failed to load credentials from token file: {e}")
        
        # If there are no valid credentials, request authorization
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed expired credentials")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None
            
            if not creds:
                # Validate required fields
                if not self.client_config.get('client_id') or not self.client_config.get('client_secret'):
                    raise ValueError(
                        "Google Drive credentials not found in environment variables. "
                        "Please set GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET in .env file."
                    )
                
                # Create client config dict for OAuth flow
                oauth_client_config = {
                    "installed": {
                        "client_id": self.client_config['client_id'],
                        "client_secret": self.client_config['client_secret'],
                        "auth_uri": self.client_config.get('auth_uri', 'https://accounts.google.com/o/oauth2/auth'),
                        "token_uri": self.client_config.get('token_uri', 'https://oauth2.googleapis.com/token'),
                        "auth_provider_x509_cert_url": self.client_config.get(
                            'auth_provider_x509_cert_url',
                            'https://www.googleapis.com/oauth2/v1/certs'
                        ),
                        "redirect_uris": self._parse_redirect_uris(self.client_config.get('redirect_uris', 'http://localhost')),
                        "project_id": self.client_config.get('project_id', '')
                    }
                }
                
                flow = InstalledAppFlow.from_client_config(oauth_client_config, self.SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info("Obtained new credentials via OAuth flow")
            
            # Save credentials for future use
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
            logger.info(f"Saved credentials to {self.token_file}")
        
        # Build the service
        try:
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to build Google Drive service: {e}")
            raise
    
    def upload_file(
        self,
        file_path: str,
        folder_id: Optional[str] = None,
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive
        
        Args:
            file_path: Path to the file to upload
            folder_id: Optional Google Drive folder ID to upload to
            file_name: Optional custom file name (uses original if not provided)
            mime_type: Optional MIME type (auto-detected if not provided)
        
        Returns:
            Dictionary with file metadata including file_id, name, webViewLink, etc.
        
        Raises:
            FileNotFoundError: If file doesn't exist
            HttpError: If Google Drive API error occurs
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_name = file_name or file_path_obj.name
        
        # Auto-detect MIME type if not provided
        if not mime_type:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path_obj))
            if not mime_type:
                mime_type = 'application/octet-stream'
        
        logger.info(f"Uploading file: {file_name} to Google Drive")
        
        try:
            # Prepare file metadata
            file_metadata = {'name': file_name}
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
                logger.debug(f"Uploading to folder ID: {folder_id}")
            
            # Upload file
            media = MediaFileUpload(
                str(file_path_obj),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,mimeType,webViewLink,webContentLink,createdTime,modifiedTime'
            ).execute()
            
            logger.success(
                f"File uploaded successfully: {file.get('name')} "
                f"(ID: {file.get('id')})"
            )
            
            return {
                'file_id': file.get('id'),
                'name': file.get('name'),
                'size': file.get('size'),
                'mime_type': file.get('mimeType'),
                'web_view_link': file.get('webViewLink'),
                'web_content_link': file.get('webContentLink'),
                'created_time': file.get('createdTime'),
                'modified_time': file.get('modifiedTime')
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {e}")
            raise
    
    def upload_file_from_bytes(
        self,
        file_bytes: bytes,
        file_name: str,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file from bytes to Google Drive
        
        Args:
            file_bytes: File content as bytes
            file_name: Name of the file
            folder_id: Optional Google Drive folder ID to upload to
            mime_type: Optional MIME type (auto-detected if not provided)
        
        Returns:
            Dictionary with file metadata
        """
        import tempfile
        
        # Auto-detect MIME type if not provided
        if not mime_type:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file_name)
            if not mime_type:
                mime_type = 'application/octet-stream'
        
        logger.info(f"Uploading file from bytes: {file_name} to Google Drive")
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            
            try:
                # Upload using the temporary file
                return self.upload_file(
                    temp_path,
                    folder_id=folder_id,
                    file_name=file_name,
                    mime_type=mime_type
                )
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temporary file: {temp_path}")
        
        except Exception as e:
            logger.error(f"Error uploading file from bytes: {e}")
            raise
    
    def create_or_get_folder(
        self,
        folder_name: str,
        parent_folder_id: Optional[str] = None
    ) -> str:
        """
        Create a folder in Google Drive or return existing folder ID
        
        Args:
            folder_name: Name of the folder to create or find
            parent_folder_id: Optional parent folder ID (if None, creates in root)
        
        Returns:
            Folder ID (existing or newly created)
        """
        logger.info(f"Creating or finding folder: {folder_name}")
        
        try:
            # Escape single quotes in folder name for query
            escaped_folder_name = folder_name.replace("'", "\\'").replace("\\", "\\\\")
            
            # Search for existing folder with the same name
            query = f"name='{escaped_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            else:
                # Search in root (files with no parents)
                query += " and 'root' in parents"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                # Folder exists, return its ID
                folder_id = items[0]['id']
                logger.info(f"Found existing folder '{folder_name}' with ID: {folder_id}")
                return folder_id
            
            # Folder doesn't exist, create it
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                folder_metadata['parents'] = [parent_folder_id]
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id, name'
            ).execute()
            
            folder_id = folder.get('id')
            logger.success(f"Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        
        except HttpError as e:
            logger.error(f"Google Drive API error while creating/finding folder: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while creating/finding folder: {e}")
            raise

