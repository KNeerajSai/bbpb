"""
Business logic service for fermentation data operations.
Coordinates between file processing, database operations, and response formatting.
"""

import logging
import time
from typing import List, Optional, Dict, Any, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.fermentation_repository import FermentationRepository
from app.services.file_processor import FileProcessorService
from app.schemas.fermentation import (
    PumpSelection, FileUploadResponse, RunClientResponse, 
    VisualizationData, RunStatistics, PumpOptions
)
from app.models.fermentation import RunClient

logger = logging.getLogger(__name__)


class FermentationService:
    """Service layer for fermentation data business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = FermentationRepository(session)
        self.file_processor = FileProcessorService()
    
    async def upload_and_process_file(
        self, 
        file: UploadFile, 
        pump_selection: PumpSelection
    ) -> FileUploadResponse:
        """
        Process uploaded file and store fermentation data.
        
        Args:
            file: Uploaded CSV file
            pump_selection: User-selected pump parameters
            
        Returns:
            FileUploadResponse with processing results
            
        Raises:
            HTTPException: If processing fails
        """
        start_time = time.time()
        
        try:
            # Check if run already exists
            client_name, run_id, data_points, file_metadata = await self.file_processor.process_uploaded_file(
                file, pump_selection
            )
            
            # Check for duplicate run ID
            existing_run = await self.repository.get_run_client_by_run_id(run_id)
            if existing_run:
                raise HTTPException(
                    status_code=409,
                    detail=f"Run ID '{run_id}' already exists. Each run must have a unique identifier."
                )
            
            # Create run client record
            run_client = await self.repository.create_run_client(
                run_id=run_id,
                client_name=client_name,
                original_filename=file_metadata["original_filename"],
                file_size_bytes=file_metadata["file_size_bytes"],
                pump_selection=pump_selection,
                total_data_points=len(data_points)
            )
            
            # Bulk insert time series data
            await self.repository.create_time_series_data_bulk(run_id, data_points)
            
            # Update processing status
            await self.repository.update_run_client_processing_complete(
                run_id, len(data_points)
            )
            
            # Commit transaction
            await self.session.commit()
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Successfully processed upload for run {run_id}: "
                f"{len(data_points)} data points in {processing_time:.2f}s"
            )
            
            return FileUploadResponse(
                success=True,
                message=f"Successfully processed {len(data_points)} data points",
                run_id=run_id,
                client_name=client_name,
                total_data_points=len(data_points),
                processing_time_seconds=round(processing_time, 3),
                file_info=file_metadata,
                pump_configuration=pump_selection
            )
            
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error during file processing: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal error processing file: {str(e)}"
            )
    
    async def get_all_runs(
        self, 
        limit: int = 100, 
        offset: int = 0,
        client_name_filter: Optional[str] = None
    ) -> List[RunClientResponse]:
        """Get all fermentation runs with optional filtering."""
        try:
            run_clients = await self.repository.get_all_run_clients(
                limit=limit, 
                offset=offset,
                client_name_filter=client_name_filter
            )
            
            return [
                RunClientResponse.model_validate(run_client)
                for run_client in run_clients
            ]
            
        except Exception as e:
            logger.error(f"Failed to get runs: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve fermentation runs"
            )
    
    async def get_run_by_id(self, run_id: str) -> Optional[RunClientResponse]:
        """Get specific run by ID."""
        try:
            run_client = await self.repository.get_run_client_by_run_id(run_id)
            if not run_client:
                return None
            
            return RunClientResponse.model_validate(run_client)
            
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve run {run_id}"
            )
    
    async def get_visualization_data(
        self,
        run_id: str,
        parameters: Optional[List[str]] = None,
        start_timestamp: Optional[float] = None,
        end_timestamp: Optional[float] = None,
        limit: Optional[int] = None
    ) -> VisualizationData:
        """Get data for visualization with optional filtering."""
        try:
            # Get run information
            run_client = await self.repository.get_run_client_by_run_id(run_id)
            if not run_client:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run {run_id} not found"
                )
            
            # Get time series data
            time_series_data = await self.repository.get_time_series_data(
                run_id=run_id,
                parameters=parameters,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                limit=limit
            )
            
            # Get available parameters
            available_parameters = await self.repository.get_run_parameters(run_id)
            
            # Get time range
            time_range = await self.repository.get_run_time_range(run_id)
            
            # Get statistics
            statistics = await self.repository.get_run_statistics(run_id)
            
            # Convert to response format
            from app.schemas.fermentation import RunTimeSeriesDataResponse
            data_points = [
                RunTimeSeriesDataResponse.model_validate(data_point)
                for data_point in time_series_data
            ]
            
            return VisualizationData(
                run_info=RunClientResponse.model_validate(run_client),
                data_points=data_points,
                parameters=available_parameters,
                time_range=time_range,
                statistics=statistics["parameters"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get visualization data for run {run_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve visualization data for run {run_id}"
            )
    
    async def get_run_statistics(self, run_id: str) -> RunStatistics:
        """Get comprehensive statistics for a run."""
        try:
            # Check if run exists
            run_exists = await self.repository.run_exists(run_id)
            if not run_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run {run_id} not found"
                )
            
            # Get statistics from repository
            stats = await self.repository.get_run_statistics(run_id)
            
            # Get run client for additional info
            run_client = await self.repository.get_run_client_by_run_id(run_id)
            
            # Calculate sampling frequencies
            sampling_frequencies = {}
            for parameter, param_stats in stats["parameters"].items():
                if stats["duration_hours"] > 0 and param_stats["count"] > 0:
                    frequency = param_stats["count"] / stats["duration_hours"]
                    sampling_frequencies[parameter] = round(frequency, 2)
                else:
                    sampling_frequencies[parameter] = 0.0
            
            # Prepare data quality metrics
            data_quality = {
                "total_points": run_client.total_data_points or 0,
                "outlier_percentage": round(
                    (stats["total_outliers"] / max(run_client.total_data_points or 1, 1)) * 100, 2
                ),
                "parameters_count": len(stats["parameters"]),
                "time_coverage_hours": round(stats["duration_hours"], 2)
            }
            
            return RunStatistics(
                run_id=run_id,
                total_data_points=run_client.total_data_points or 0,
                duration_hours=round(stats["duration_hours"], 2),
                parameters=stats["parameters"],
                data_quality=data_quality,
                outliers_detected=stats["total_outliers"],
                sampling_frequency=sampling_frequencies
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get statistics for run {run_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve statistics for run {run_id}"
            )
    
    async def delete_run(self, run_id: str) -> Dict[str, Any]:
        """Delete a fermentation run and all associated data."""
        try:
            # Check if run exists
            run_exists = await self.repository.run_exists(run_id)
            if not run_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run {run_id} not found"
                )
            
            # Delete run and data
            deleted = await self.repository.delete_run_and_data(run_id)
            
            if deleted:
                await self.session.commit()
                logger.info(f"Successfully deleted run {run_id}")
                return {
                    "success": True,
                    "message": f"Run {run_id} deleted successfully"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete run {run_id}"
                )
                
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete run {run_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete run {run_id}"
            )
    
    async def get_pump_options(self) -> PumpOptions:
        """Get available pump parameter options."""
        return PumpOptions()
    
    async def validate_run_access(self, run_id: str) -> RunClient:
        """Validate run exists and return run client."""
        run_client = await self.repository.get_run_client_by_run_id(run_id)
        if not run_client:
            raise HTTPException(
                status_code=404,
                detail=f"Run {run_id} not found"
            )
        return run_client