"""
Fermentation runs API endpoints.
Manages CRUD operations for fermentation run data.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.fermentation_service import FermentationService
from app.schemas.fermentation import RunClientResponse, RunStatistics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/", response_model=List[RunClientResponse])
async def get_all_runs(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of runs to return"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of runs to skip for pagination"
    ),
    client_name: Optional[str] = Query(
        default=None,
        description="Filter runs by client name (partial match)"
    ),
    session: AsyncSession = Depends(get_session)
) -> List[RunClientResponse]:
    """
    Get all fermentation runs with optional filtering and pagination.
    
    **Query Parameters:**
    - `limit`: Maximum number of runs to return (1-1000, default: 100)
    - `offset`: Number of runs to skip for pagination (default: 0)
    - `client_name`: Filter by client name (partial match, case-insensitive)
    
    **Returns:**
    - List of fermentation runs ordered by creation date (newest first)
    - Each run includes metadata, processing status, and configuration
    
    **Example:**
    ```
    GET /api/v1/runs?limit=50&offset=0&client_name=ClientABC
    ```
    """
    try:
        service = FermentationService(session)
        runs = await service.get_all_runs(
            limit=limit,
            offset=offset,
            client_name_filter=client_name
        )
        
        logger.info(f"Retrieved {len(runs)} runs (limit={limit}, offset={offset})")
        return runs
        
    except Exception as e:
        logger.error(f"Failed to get runs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve fermentation runs"
        )


@router.get("/{run_id}", response_model=RunClientResponse)
async def get_run_by_id(
    run_id: str,
    session: AsyncSession = Depends(get_session)
) -> RunClientResponse:
    """
    Get specific fermentation run by ID.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Returns:**
    - Complete run information including metadata and configuration
    - Processing status and data quality metrics
    
    **Errors:**
    - 404: Run not found
    """
    try:
        service = FermentationService(session)
        run = await service.get_run_by_id(run_id)
        
        if not run:
            raise HTTPException(
                status_code=404,
                detail=f"Run {run_id} not found"
            )
        
        logger.info(f"Retrieved run details: {run_id}")
        return run
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve run {run_id}"
        )


@router.get("/{run_id}/statistics", response_model=RunStatistics)
async def get_run_statistics(
    run_id: str,
    session: AsyncSession = Depends(get_session)
) -> RunStatistics:
    """
    Get comprehensive statistics for a fermentation run.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Returns:**
    - Statistical summary for each parameter (count, mean, min, max, stddev)
    - Data quality metrics and outlier detection results
    - Temporal analysis (duration, sampling frequency)
    - Overall run health indicators
    
    **Statistics Include:**
    - Total data points and run duration
    - Per-parameter descriptive statistics
    - Outlier detection and data quality scores
    - Sampling frequency analysis
    
    **Errors:**
    - 404: Run not found
    """
    try:
        service = FermentationService(session)
        statistics = await service.get_run_statistics(run_id)
        
        logger.info(f"Generated statistics for run: {run_id}")
        return statistics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get statistics for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics for run {run_id}"
        )


@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Delete a fermentation run and all associated time-series data.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Warning:**
    This operation permanently deletes:
    - Run metadata and configuration
    - All time-series data points
    - Processing history and statistics
    
    **Returns:**
    - Deletion confirmation message
    
    **Errors:**
    - 404: Run not found
    - 500: Deletion failed
    """
    try:
        service = FermentationService(session)
        result = await service.delete_run(run_id)
        
        logger.info(f"Deleted run: {run_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete run {run_id}"
        )


@router.get("/{run_id}/parameters")
async def get_run_parameters(
    run_id: str,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, List[str]]:
    """
    Get available parameters for a specific run.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Returns:**
    - List of unique parameters available in the run data
    - Used for filtering and visualization configuration
    
    **Errors:**
    - 404: Run not found
    """
    try:
        service = FermentationService(session)
        
        # Validate run exists
        await service.validate_run_access(run_id)
        
        # Get parameters through repository
        parameters = await service.repository.get_run_parameters(run_id)
        
        logger.info(f"Retrieved parameters for run {run_id}: {parameters}")
        return {"parameters": parameters}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get parameters for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve parameters for run {run_id}"
        )


@router.get("/{run_id}/time-range")
async def get_run_time_range(
    run_id: str,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, float]:
    """
    Get time range (min, max timestamps) for a specific run.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Returns:**
    - Minimum and maximum timestamp values in the dataset
    - Used for time-based filtering and visualization scaling
    
    **Errors:**
    - 404: Run not found
    """
    try:
        service = FermentationService(session)
        
        # Validate run exists
        await service.validate_run_access(run_id)
        
        # Get time range through repository
        time_range = await service.repository.get_run_time_range(run_id)
        
        logger.info(f"Retrieved time range for run {run_id}: {time_range}")
        return time_range
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get time range for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve time range for run {run_id}"
        )