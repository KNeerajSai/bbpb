"""
Repository layer for fermentation data database operations.
Provides optimized database queries with proper error handling.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, and_, or_, case
from sqlalchemy.orm import selectinload
import logging

from app.models.fermentation import RunClient, RunTimeSeriesData
from app.schemas.fermentation import TimeSeriesDataPoint, PumpSelection

logger = logging.getLogger(__name__)


class FermentationRepository:
    """Repository for fermentation data database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_run_client(
        self,
        run_id: str,
        client_name: str,
        original_filename: str,
        file_size_bytes: int,
        pump_selection: PumpSelection,
        total_data_points: int = 0
    ) -> RunClient:
        """Create a new run client record."""
        try:
            run_client = RunClient(
                run_id=run_id,
                client_name=client_name,
                original_filename=original_filename,
                file_size_bytes=file_size_bytes,
                total_data_points=total_data_points,
                processing_status="processing",
                pump1_parameter=pump_selection.pump1 if isinstance(pump_selection.pump1, str) else pump_selection.pump1.value,
                pump2_parameter=pump_selection.pump2 if isinstance(pump_selection.pump2, str) else pump_selection.pump2.value
            )
            
            self.session.add(run_client)
            await self.session.flush()  # Get ID without committing
            
            logger.info(f"Created run client: {run_id} for {client_name}")
            return run_client
            
        except Exception as e:
            logger.error(f"Failed to create run client {run_id}: {e}")
            raise
    
    async def get_run_client_by_run_id(self, run_id: str) -> Optional[RunClient]:
        """Get run client by run ID."""
        try:
            stmt = select(RunClient).where(RunClient.run_id == run_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get run client {run_id}: {e}")
            raise
    
    async def get_all_run_clients(
        self, 
        limit: int = 100, 
        offset: int = 0,
        client_name_filter: Optional[str] = None
    ) -> List[RunClient]:
        """Get all run clients with optional filtering."""
        try:
            stmt = select(RunClient)
            
            # Apply filters
            if client_name_filter:
                stmt = stmt.where(RunClient.client_name.ilike(f"%{client_name_filter}%"))
            
            # Apply ordering and pagination
            stmt = stmt.order_by(desc(RunClient.created_at)).limit(limit).offset(offset)
            
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get run clients: {e}")
            raise
    
    async def update_run_client_processing_complete(
        self, 
        run_id: str, 
        total_data_points: int
    ) -> Optional[RunClient]:
        """Update run client when processing is complete."""
        try:
            run_client = await self.get_run_client_by_run_id(run_id)
            if not run_client:
                return None
            
            run_client.total_data_points = total_data_points
            run_client.processing_status = "completed"
            run_client.updated_at = datetime.utcnow()
            
            await self.session.flush()
            
            logger.info(f"Updated run client {run_id}: {total_data_points} data points processed")
            return run_client
            
        except Exception as e:
            logger.error(f"Failed to update run client {run_id}: {e}")
            raise
    
    async def create_time_series_data_bulk(
        self, 
        run_id: str, 
        data_points: List[TimeSeriesDataPoint]
    ) -> int:
        """Bulk insert time series data points for optimal performance."""
        try:
            # Prepare bulk insert data
            insert_data = [
                {
                    "run_id": run_id,
                    "timestamp": point.timestamp,
                    "parameter": point.parameter,
                    "process_value": point.process_value,
                    "units": point.units,
                    "is_outlier": point.is_outlier,
                    "data_quality_score": point.data_quality_score,
                    "created_at": datetime.utcnow()
                }
                for point in data_points
            ]
            
            # Use bulk insert for performance
            await self.session.execute(
                RunTimeSeriesData.__table__.insert(),
                insert_data
            )
            
            logger.info(f"Bulk inserted {len(data_points)} time series data points for run {run_id}")
            return len(data_points)
            
        except Exception as e:
            logger.error(f"Failed to bulk insert time series data for run {run_id}: {e}")
            raise
    
    async def get_time_series_data(
        self,
        run_id: str,
        parameters: Optional[List[str]] = None,
        start_timestamp: Optional[float] = None,
        end_timestamp: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[RunTimeSeriesData]:
        """Get time series data with optional filtering."""
        try:
            stmt = select(RunTimeSeriesData).where(RunTimeSeriesData.run_id == run_id)
            
            # Apply parameter filter
            if parameters:
                stmt = stmt.where(RunTimeSeriesData.parameter.in_(parameters))
            
            # Apply time range filter
            if start_timestamp is not None:
                stmt = stmt.where(RunTimeSeriesData.timestamp >= start_timestamp)
            if end_timestamp is not None:
                stmt = stmt.where(RunTimeSeriesData.timestamp <= end_timestamp)
            
            # Order by timestamp for time series visualization
            stmt = stmt.order_by(asc(RunTimeSeriesData.timestamp))
            
            # Apply limit if specified
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get time series data for run {run_id}: {e}")
            raise
    
    async def get_run_parameters(self, run_id: str) -> List[str]:
        """Get unique parameters for a run."""
        try:
            stmt = select(RunTimeSeriesData.parameter.distinct()).where(
                RunTimeSeriesData.run_id == run_id
            )
            result = await self.session.execute(stmt)
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get parameters for run {run_id}: {e}")
            raise
    
    async def get_run_time_range(self, run_id: str) -> Dict[str, float]:
        """Get time range (min, max) for a run."""
        try:
            stmt = select(
                func.min(RunTimeSeriesData.timestamp).label("min_time"),
                func.max(RunTimeSeriesData.timestamp).label("max_time")
            ).where(RunTimeSeriesData.run_id == run_id)
            
            result = await self.session.execute(stmt)
            row = result.fetchone()
            
            return {
                "min": float(row.min_time) if row.min_time is not None else 0.0,
                "max": float(row.max_time) if row.max_time is not None else 0.0
            }
        except Exception as e:
            logger.error(f"Failed to get time range for run {run_id}: {e}")
            raise
    
    async def get_run_statistics(self, run_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a run."""
        try:
            # Get basic statistics per parameter
            stmt = select(
                RunTimeSeriesData.parameter,
                func.count(RunTimeSeriesData.id).label("count"),
                func.avg(RunTimeSeriesData.process_value).label("mean"),
                func.min(RunTimeSeriesData.process_value).label("min"),
                func.max(RunTimeSeriesData.process_value).label("max"),
                # SQLite doesn't have stddev, so we'll calculate variance manually or use 0 as placeholder
                (func.max(RunTimeSeriesData.process_value) - func.min(RunTimeSeriesData.process_value)).label("range"),
                func.sum(case((RunTimeSeriesData.is_outlier == True, 1), else_=0)).label("outliers")
            ).where(
                RunTimeSeriesData.run_id == run_id
            ).group_by(RunTimeSeriesData.parameter)
            
            result = await self.session.execute(stmt)
            rows = result.fetchall()
            
            statistics = {}
            total_outliers = 0
            
            for row in rows:
                param_stats = {
                    "count": row.count,
                    "mean": float(row.mean) if row.mean else 0.0,
                    "min": float(row.min) if row.min else 0.0,
                    "max": float(row.max) if row.max else 0.0,
                    "range": float(row.range) if row.range else 0.0,
                    "outliers": row.outliers or 0
                }
                statistics[row.parameter] = param_stats
                total_outliers += param_stats["outliers"]
            
            # Get time range for duration calculation
            time_range = await self.get_run_time_range(run_id)
            duration_hours = (time_range["max"] - time_range["min"]) / 3600.0  # Assuming timestamps are in seconds
            
            return {
                "parameters": statistics,
                "total_outliers": total_outliers,
                "duration_hours": duration_hours,
                "time_range": time_range
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics for run {run_id}: {e}")
            raise
    
    async def delete_run_and_data(self, run_id: str) -> bool:
        """Delete run and all associated time series data."""
        try:
            # Delete time series data first (due to foreign key constraint)
            delete_data_stmt = RunTimeSeriesData.__table__.delete().where(
                RunTimeSeriesData.run_id == run_id
            )
            await self.session.execute(delete_data_stmt)
            
            # Delete run client
            delete_run_stmt = RunClient.__table__.delete().where(
                RunClient.run_id == run_id
            )
            result = await self.session.execute(delete_run_stmt)
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"Deleted run {run_id} and associated data")
                return True
            else:
                logger.warning(f"No run found with ID {run_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete run {run_id}: {e}")
            raise
    
    async def run_exists(self, run_id: str) -> bool:
        """Check if a run exists."""
        try:
            stmt = select(func.count(RunClient.id)).where(RunClient.run_id == run_id)
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check if run exists {run_id}: {e}")
            raise