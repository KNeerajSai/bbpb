"""
Data visualization API endpoints.
Provides optimized data endpoints for interactive charts and analysis.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.fermentation_service import FermentationService
from app.schemas.fermentation import VisualizationData, RunTimeSeriesDataResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/{run_id}/data", response_model=VisualizationData)
async def get_visualization_data(
    run_id: str,
    parameters: Optional[List[str]] = Query(
        default=None,
        description="Filter by specific parameters (e.g., pH, Temperature)"
    ),
    start_timestamp: Optional[float] = Query(
        default=None,
        ge=0.0,
        description="Start timestamp for time range filtering"
    ),
    end_timestamp: Optional[float] = Query(
        default=None,
        ge=0.0,
        description="End timestamp for time range filtering"
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=100000,
        description="Maximum number of data points to return"
    ),
    session: AsyncSession = Depends(get_session)
) -> VisualizationData:
    """
    Get comprehensive data for interactive visualization.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Query Parameters:**
    - `parameters`: Filter by specific parameters (can be repeated)
    - `start_timestamp`: Start of time range filter
    - `end_timestamp`: End of time range filter  
    - `limit`: Maximum data points to return (performance optimization)
    
    **Returns:**
    - Complete visualization dataset including:
      - Run metadata and configuration
      - Filtered time-series data points
      - Available parameters list
      - Time range information
      - Statistical summary per parameter
    
    **Usage Examples:**
    ```
    # Get all data for a run
    GET /api/v1/visualization/{run_id}/data
    
    # Filter by specific parameters
    GET /api/v1/visualization/{run_id}/data?parameters=pH&parameters=Temperature
    
    # Time range filtering
    GET /api/v1/visualization/{run_id}/data?start_timestamp=0&end_timestamp=3600
    
    # Limit data points for performance
    GET /api/v1/visualization/{run_id}/data?limit=10000
    ```
    
    **Performance Notes:**
    - Use `limit` parameter for large datasets
    - Parameter filtering reduces data transfer
    - Time range filtering improves query performance
    
    **Errors:**
    - 404: Run not found
    """
    try:
        service = FermentationService(session)
        
        # Validate timestamp range
        if (start_timestamp is not None and 
            end_timestamp is not None and 
            start_timestamp > end_timestamp):
            raise HTTPException(
                status_code=400,
                detail="start_timestamp cannot be greater than end_timestamp"
            )
        
        visualization_data = await service.get_visualization_data(
            run_id=run_id,
            parameters=parameters,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit
        )
        
        logger.info(
            f"Retrieved visualization data for run {run_id}: "
            f"{len(visualization_data.data_points)} data points"
        )
        
        return visualization_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get visualization data for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve visualization data for run {run_id}"
        )


@router.get("/{run_id}/data/raw", response_model=List[RunTimeSeriesDataResponse])
async def get_raw_time_series_data(
    run_id: str,
    parameters: Optional[List[str]] = Query(
        default=None,
        description="Filter by specific parameters"
    ),
    start_timestamp: Optional[float] = Query(
        default=None,
        ge=0.0,
        description="Start timestamp for filtering"
    ),
    end_timestamp: Optional[float] = Query(
        default=None,
        ge=0.0,
        description="End timestamp for filtering"
    ),
    limit: Optional[int] = Query(
        default=10000,
        ge=1,
        le=100000,
        description="Maximum number of data points (default: 10000)"
    ),
    exclude_outliers: bool = Query(
        default=False,
        description="Exclude data points flagged as outliers"
    ),
    session: AsyncSession = Depends(get_session)
) -> List[RunTimeSeriesDataResponse]:
    """
    Get raw time-series data points with advanced filtering.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Query Parameters:**
    - `parameters`: Filter by specific parameters
    - `start_timestamp`: Start of time range
    - `end_timestamp`: End of time range
    - `limit`: Maximum data points (default: 10000)
    - `exclude_outliers`: Remove outlier data points
    
    **Returns:**
    - Raw time-series data points with all metadata
    - Ordered by timestamp for time-series analysis
    - Includes data quality flags and scores
    
    **Use Cases:**
    - Data export and analysis
    - Custom visualization requirements
    - Statistical analysis and modeling
    - Quality assurance workflows
    
    **Performance:**
    - Optimized queries with database indexes
    - Configurable limits for large datasets
    - Parameter and time filtering at database level
    
    **Errors:**
    - 404: Run not found
    """
    try:
        service = FermentationService(session)
        
        # Validate run exists
        await service.validate_run_access(run_id)
        
        # Get raw data through repository with additional filtering
        time_series_data = await service.repository.get_time_series_data(
            run_id=run_id,
            parameters=parameters,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit
        )
        
        # Apply outlier filtering if requested
        if exclude_outliers:
            time_series_data = [data for data in time_series_data if not data.is_outlier]
        
        # Convert to response format
        data_points = [
            RunTimeSeriesDataResponse.model_validate(data_point)
            for data_point in time_series_data
        ]
        
        logger.info(
            f"Retrieved {len(data_points)} raw data points for run {run_id}"
        )
        
        return data_points
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get raw data for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve raw data for run {run_id}"
        )


@router.get("/{run_id}/export")
async def export_data(
    run_id: str,
    format: str = Query(
        default="json",
        regex="^(json|csv)$",
        description="Export format: json or csv"
    ),
    parameters: Optional[List[str]] = Query(
        default=None,
        description="Filter by specific parameters"
    ),
    start_timestamp: Optional[float] = Query(
        default=None,
        description="Start timestamp for filtering"
    ),
    end_timestamp: Optional[float] = Query(
        default=None,
        description="End timestamp for filtering"
    ),
    session: AsyncSession = Depends(get_session)
):
    """
    Export fermentation data in various formats.
    
    **Path Parameters:**
    - `run_id`: Unique identifier for the fermentation run
    
    **Query Parameters:**
    - `format`: Export format (json, csv)
    - `parameters`: Filter by specific parameters
    - `start_timestamp`: Start of time range
    - `end_timestamp`: End of time range
    
    **Returns:**
    - Data in requested format with appropriate content type
    - CSV format suitable for Excel and analysis tools
    - JSON format for programmatic access
    
    **Headers:**
    - Content-Disposition: attachment with suggested filename
    - Content-Type: appropriate MIME type for format
    """
    try:
        service = FermentationService(session)
        
        # Get data
        visualization_data = await service.get_visualization_data(
            run_id=run_id,
            parameters=parameters,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp
        )
        
        if format == "csv":
            import io
            import csv
            
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "timestamp", "parameter", "process_value", "units", 
                "is_outlier", "data_quality_score"
            ])
            
            # Write data
            for point in visualization_data.data_points:
                writer.writerow([
                    point.timestamp,
                    point.parameter,
                    point.process_value,
                    point.units,
                    point.is_outlier,
                    point.data_quality_score or ""
                ])
            
            # Return CSV response
            from fastapi.responses import Response
            
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={run_id}_data.csv"
                }
            )
        
        else:  # JSON format
            from fastapi.responses import JSONResponse
            
            export_data = {
                "run_info": visualization_data.run_info.model_dump(),
                "data_points": [point.model_dump() for point in visualization_data.data_points],
                "metadata": {
                    "exported_at": logger.info.__name__,  # Current timestamp
                    "parameters": visualization_data.parameters,
                    "time_range": visualization_data.time_range,
                    "total_points": len(visualization_data.data_points)
                }
            }
            
            return JSONResponse(
                content=export_data,
                headers={
                    "Content-Disposition": f"attachment; filename={run_id}_data.json"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export data for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export data for run {run_id}"
        )