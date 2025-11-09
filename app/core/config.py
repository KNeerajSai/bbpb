"""
Core configuration module for the Boston Bioprocess application.
Handles environment variables, database settings, and application configuration.
"""

import os
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings with validation and type safety."""
    
    # Application
    app_name: str = "Boston Bioprocess Fermentation Data Platform"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/fermentation_db",
        description="PostgreSQL database connection URL"
    )
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_max_overflow: int = Field(default=20, description="Database max overflow connections")
    database_pool_pre_ping: bool = Field(default=True, description="Enable pool pre ping")
    database_pool_recycle: int = Field(default=300, description="Pool recycle time in seconds")
    
    # File Upload Configuration
    upload_dir: str = Field(default="./uploads", description="File upload directory")
    max_file_size: int = Field(default=10_485_760, description="Maximum file size in bytes (10MB)")
    allowed_file_extensions: List[str] = Field(default=[".csv"], description="Allowed file extensions")
    
    # Security & CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_allow_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"], description="Allowed CORS methods")
    cors_allow_headers: List[str] = Field(default=["*"], description="Allowed CORS headers")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    
    # Performance Settings
    enable_gzip: bool = Field(default=True, description="Enable gzip compression")
    gzip_minimum_size: int = Field(default=1000, description="Minimum size for gzip compression")
    
    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_endpoint: str = Field(default="/metrics", description="Metrics endpoint path")
    
    @validator("database_url")
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        allowed_schemes = (
            "postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://",
            "sqlite://", "sqlite+aiosqlite://"
        )
        if not v.startswith(allowed_schemes):
            raise ValueError(f"Database URL must start with one of: {allowed_schemes}")
        return v
    
    @validator("max_file_size")
    def validate_max_file_size(cls, v: int) -> int:
        """Validate maximum file size is within reasonable limits."""
        if v <= 0:
            raise ValueError("Maximum file size must be positive")
        if v > 100_000_000:  # 100MB
            raise ValueError("Maximum file size cannot exceed 100MB")
        return v
    
    @validator("cors_origins")
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """Validate CORS origins format."""
        for origin in v:
            if origin != "*" and not origin.startswith(("http://", "https://")):
                raise ValueError(f"Invalid CORS origin format: {origin}")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_prefix = "BBPF_"  # Boston Bioprocess Fermentation prefix
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings


# Database configuration for SQLAlchemy
def get_database_url() -> str:
    """Get formatted database URL for SQLAlchemy."""
    return settings.database_url


# Environment helpers
def is_development() -> bool:
    """Check if running in development mode."""
    return settings.debug


def is_production() -> bool:
    """Check if running in production mode."""
    return not settings.debug


def get_upload_directory() -> str:
    """Get upload directory path, creating it if it doesn't exist."""
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir