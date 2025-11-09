"""
Main FastAPI application entry point for Boston Bioprocess Fermentation Data Platform.
Configures the application with proper middleware, error handling, and lifecycle management.
"""

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.database import database_lifespan, db_manager
from app.schemas.fermentation import ErrorResponse


# Configure logging
def setup_logging():
    """Configure application logging."""
    settings = get_settings()
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log')
        ]
    )
    
    # Set specific logger levels
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )


setup_logging()
logger = logging.getLogger(__name__)

# Application startup time for uptime calculation
APP_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Boston Bioprocess Fermentation Data Platform")
    
    try:
        # Database lifecycle management
        async with database_lifespan():
            logger.info("Application startup completed successfully")
            yield
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    finally:
        logger.info("Application shutdown completed")


# Initialize FastAPI application
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A comprehensive platform for uploading, storing, and visualizing fermentation time-series data",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add middleware
if settings.enable_gzip:
    app.add_middleware(
        GZipMiddleware, 
        minimum_size=settings.gzip_minimum_size
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing information."""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Log request details
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with structured error responses."""
    error_response = ErrorResponse(
        message=exc.detail,
        error_code=f"HTTP_{exc.status_code}",
        details={"status_code": exc.status_code, "url": str(request.url)}
    )
    
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - URL: {request.url}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    error_response = ErrorResponse(
        message="Invalid request data",
        error_code="VALIDATION_ERROR",
        details={
            "validation_errors": exc.errors(),
            "url": str(request.url)
        }
    )
    
    logger.warning(f"Validation error: {exc.errors()} - URL: {request.url}")
    
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    error_response = ErrorResponse(
        message="An unexpected error occurred",
        error_code="INTERNAL_ERROR",
        details={"url": str(request.url)} if not settings.debug else {
            "url": str(request.url),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }
    )
    
    logger.error(f"Unexpected error: {exc} - URL: {request.url}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


# Health check endpoints
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.app_version,
        "uptime_seconds": round(time.time() - APP_START_TIME, 2)
    }


@app.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check including database connectivity."""
    db_status = "unknown"
    try:
        db_healthy = await db_manager.health_check()
        db_status = "healthy" if db_healthy else "unhealthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.error(f"Database health check failed: {e}")
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": time.time(),
        "version": settings.app_version,
        "uptime_seconds": round(time.time() - APP_START_TIME, 2),
        "database": db_status,
        "debug_mode": settings.debug
    }


# Root endpoint
@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "message": "Welcome to Boston Bioprocess Fermentation Data Platform",
        "version": settings.app_version,
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_schema": "/openapi.json"
        },
        "endpoints": {
            "health": "/health",
            "api": "/api/v1"
        }
    }


# Include API routers
from app.api.v1 import upload, visualization, runs

app.include_router(upload.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1") 
app.include_router(visualization.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )