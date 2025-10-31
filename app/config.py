"""
Application configuration
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "IDP EtechTexas RAG"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENV: str = ""  # Environment variable for logger configuration
    
    
    # Google Drive API Credentials (from .env)
    GOOGLE_DRIVE_CLIENT_ID: Optional[str] = None
    GOOGLE_DRIVE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_DRIVE_PROJECT_ID: Optional[str] = None
    GOOGLE_DRIVE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_DRIVE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_DRIVE_AUTH_PROVIDER_X509_CERT_URL: str = "https://www.googleapis.com/oauth2/v1/certs"
    GOOGLE_DRIVE_REDIRECT_URIS: str = "http://localhost"  # Comma-separated or single URI
    
    # Google Drive API Configuration
    GOOGLE_DRIVE_TOKEN_FILE: Optional[str] = os.getenv("GOOGLE_DRIVE_TOKEN_FILE", "token.json")
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

