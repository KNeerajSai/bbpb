"""
File upload API endpoints for fermentation data.
Handles CSV file uploads with validation and processing.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.fermentation_service import FermentationService
from app.schemas.fermentation import (
    FileUploadResponse, PumpParameter, PumpSelection, PumpOptions
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/", response_model=FileUploadResponse)
async def upload_fermentation_data(
    file: UploadFile = File(
        ...,
        description="CSV file containing fermentation time-series data"
    ),
    pump1: PumpParameter = Form(
        ...,
        description="Parameter selection for Pump1 (Glucose or Glycerol)"
    ),
    pump2: PumpParameter = Form(
        ...,
        description="Parameter selection for Pump2 (Base or Acid)"
    ),
    session: AsyncSession = Depends(get_session)
) -> FileUploadResponse:
    """
    Upload and process fermentation CSV file.
    
    **File Requirements:**
    - Format: CSV with columns [Time Stamp, Parameter, Process value, Units]
    - Filename format: ClientName_RunID_*.csv
    - Parameters: pH, Temperature, Pump1, Pump2
    - Maximum size: 10MB
    
    **Processing:**
    1. Validates file format and structure
    2. Extracts client name and run ID from filename
    3. Replaces Pump1/Pump2 with selected parameters
    4. Stores data in database with quality analysis
    5. Returns processing results and statistics
    
    **Returns:**
    - Upload success status and processing details
    - Generated run ID and client information
    - Data quality metrics and file metadata
    """
    try:
        # Create pump selection from form data
        pump_selection = PumpSelection(pump1=pump1, pump2=pump2)
        
        # Process upload through service layer
        service = FermentationService(session)
        result = await service.upload_and_process_file(file, pump_selection)
        
        logger.info(f"Upload successful: {result.run_id} - {result.total_data_points} data points")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process upload"
        )


@router.get("/pump-options", response_model=PumpOptions)
async def get_pump_options() -> PumpOptions:
    """
    Get available pump parameter options.
    
    **Returns:**
    - Available options for Pump1 and Pump2 configuration
    - Used by frontend for dropdown selections
    """
    return PumpOptions()


@router.post("/validate")
async def validate_file_format(
    file: UploadFile = File(..., description="CSV file to validate")
) -> Dict[str, Any]:
    """
    Validate file format without processing.
    
    **Validation checks:**
    - File extension and size
    - Filename format (ClientName_RunID_*.csv)
    - CSV structure and required columns
    - Data format and types
    
    **Returns:**
    - Validation results and potential issues
    - Extracted metadata (client name, run ID)
    - File analysis summary
    """
    try:
        from app.services.file_processor import FileProcessorService
        
        processor = FileProcessorService()
        
        # Basic file validation
        await processor._validate_file(file)
        
        # Extract metadata
        client_name, run_id = processor._extract_metadata_from_filename(file.filename)
        
        # Read and validate CSV structure (without full processing)
        file_content = await file.read()
        file.file.seek(0)  # Reset file position
        
        df = processor._read_csv_robust(file_content)
        
        validation_results = {
            "valid": True,
            "filename": file.filename,
            "extracted_metadata": {
                "client_name": client_name,
                "run_id": run_id
            },
            "file_info": {
                "size_bytes": len(file_content),
                "size_mb": round(len(file_content) / 1_000_000, 2),
                "rows": len(df),
                "columns": len(df.columns)
            },
            "csv_structure": {
                "columns": df.columns.tolist(),
                "sample_data": df.head(3).to_dict("records") if not df.empty else []
            },
            "warnings": []
        }
        
        # Check for potential issues
        if len(df) == 0:
            validation_results["warnings"].append("CSV file appears to be empty")
        
        if len(df.columns) < 4:
            validation_results["warnings"].append("CSV should have at least 4 columns")
        
        required_params = {"pH", "Temperature", "Pump1", "Pump2"}
        if "Parameter" in df.columns:
            found_params = set(df["Parameter"].dropna().unique())
            missing_params = required_params - found_params
            if missing_params:
                validation_results["warnings"].append(
                    f"Missing expected parameters: {', '.join(missing_params)}"
                )
        
        return validation_results
        
    except HTTPException as e:
        return {
            "valid": False,
            "error": e.detail,
            "filename": file.filename if file.filename else "unknown"
        }
    except Exception as e:
        logger.error(f"File validation failed: {e}")
        return {
            "valid": False,
            "error": f"Validation failed: {str(e)}",
            "filename": file.filename if file.filename else "unknown"
        }