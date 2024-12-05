from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "MeowApp API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = """
    Social media API for cat lovers. 
    
    ## Features
    * User authentication and authorization
    * Post creation and management
    * Like and follow functionality
    * Profile picture management
    * Real-time chat using WebSockets
    
    ## Rate Limits
    * Login: 3 attempts per minute
    * Posts: 5 posts per minute
    * Likes: 10 like operations per minute
    """
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"
    OPENAPI_TAGS: list[dict] = [
        {
            "name": "auth",
            "description": "Authentication operations including login, logout, and 2FA"
        },
        {
            "name": "users",
            "description": "User operations including profile management and verification"
        },
        {
            "name": "posts",
            "description": "Post creation, retrieval, and management operations"
        },
        {
            "name": "social",
            "description": "Social interactions including following users and liking posts"
        },
        {
            "name": "files",
            "description": "File operations including profile picture management"
        },
        {
            "name": "admin",
            "description": "Administrative operations including logs and cache management",
        }
    ]
    CONTACT: dict = {"name": "hugoeljugo", "email": "hugougena27@gmail.com"}
    LICENSE_INFO: dict = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
        "identifier": "MIT",
        "text": """MIT License

Copyright (c) 2024 hugoeljugo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.""",
    }

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost"]

    # Database
    DB_USER: str
    DB_PASS: str
    DB_NAME: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    # Remove the direct string interpolation and add a property
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # File Upload
    UPLOAD_FOLDER: str = "uploaded_files"
    MAX_UPLOAD_SIZE: int = 10_485_760  # 10MB
    ALLOWED_IMAGE_TYPES: list[str] = ["jpg", "jpeg", "png", "webp"]

    # Cache
    CACHE_EXPIRE_TIME: int = 300  # 5 minutes

    # Rate Limiting
    LOGIN_ATTEMPTS_PER_MINUTE: int = 3
    POSTS_PER_MINUTE: int = 5
    LIKES_PER_MINUTE: int = 10

    # API Key
    API_KEY: str
    API_KEY_NAME: str = "X-API-Key"
    
    # Email Settings
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAIL_FROM_NAME: str = "MeowApp"
    EMAIL_FROM_ADDRESS: str
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    # Get the current file's directory
    current_dir = Path(__file__).resolve().parent
    # Go up one level to BACKEND directory
    backend_dir = current_dir.parent

    # Initialize settings with explicit .env path
    return Settings(_env_file=backend_dir / ".env")
