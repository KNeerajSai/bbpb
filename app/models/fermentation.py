"""
Database models for fermentation data storage.
Implements the required schema with optimized indexes for time-series data.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Float, DateTime, Index, ForeignKey, Text, Integer, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class RunClient(Base):
    """
    Model for storing fermentation run client information.
    Each run has a unique run_id and associated client name.
    """
    __tablename__ = "run_client"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Business Key - Unique Run Identifier
    run_id: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False, 
        index=True,
        comment="Unique identifier for the fermentation run (e.g., R001001)"
    )
    
    # Client Information
    client_name: Mapped[str] = mapped_column(
        String(255), 
        nullable=False, 
        index=True,
        comment="Name of the client (e.g., ClientABC)"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False,
        comment="Timestamp when the record was created"
    )
    
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        comment="Timestamp when the record was last updated"
    )
    
    # File Processing Metadata
    original_filename: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="Original filename of the uploaded CSV file"
    )
    
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Size of the uploaded file in bytes"
    )
    
    total_data_points: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Total number of data points processed from the file"
    )
    
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="processing",
        comment="Status of file processing: processing, completed, failed"
    )
    
    # Pump Configuration
    pump1_parameter: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="User-selected parameter for Pump1 (Glucose or Glycerol)"
    )
    
    pump2_parameter: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="User-selected parameter for Pump2 (Base or Acid)"
    )
    
    # Relationships
    time_series_data: Mapped[List["RunTimeSeriesData"]] = relationship(
        "RunTimeSeriesData",
        back_populates="run_client",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<RunClient(run_id='{self.run_id}', client_name='{self.client_name}')>"
    
    @property
    def is_processing_complete(self) -> bool:
        """Check if processing is completed."""
        return self.processing_status == "completed"
    
    @property
    def has_data(self) -> bool:
        """Check if run has time series data."""
        return self.total_data_points is not None and self.total_data_points > 0


class RunTimeSeriesData(Base):
    """
    Model for storing time-series fermentation data points.
    Optimized for time-series queries with appropriate indexes.
    """
    __tablename__ = "run_time_series_data"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key to RunClient
    run_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("run_client.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the fermentation run"
    )
    
    # Time Series Data
    timestamp: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
        comment="Timestamp value from the CSV file"
    )
    
    parameter: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Parameter name (pH, Temperature, or user-selected pump parameters)"
    )
    
    process_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Process value for the parameter at the given timestamp"
    )
    
    units: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Units of measurement for the process value"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Timestamp when the record was created"
    )
    
    # Data Quality Flags
    is_outlier: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Flag indicating if this data point is identified as an outlier"
    )
    
    data_quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Quality score for this data point (0.0 to 1.0)"
    )
    
    # Relationships
    run_client: Mapped["RunClient"] = relationship(
        "RunClient",
        back_populates="time_series_data"
    )
    
    def __repr__(self) -> str:
        return (f"<RunTimeSeriesData(run_id='{self.run_id}', "
                f"timestamp={self.timestamp}, parameter='{self.parameter}', "
                f"value={self.process_value})>")
    
    @property
    def formatted_timestamp(self) -> str:
        """Get formatted timestamp for display."""
        return f"{self.timestamp:.3f}"
    
    @property
    def formatted_value_with_units(self) -> str:
        """Get formatted value with units for display."""
        return f"{self.process_value:.2f} {self.units}"


# Database Indexes for Optimal Performance
# Composite index for time-series queries (run_id, timestamp, parameter)
Index(
    "idx_run_time_series_composite",
    RunTimeSeriesData.run_id,
    RunTimeSeriesData.timestamp,
    RunTimeSeriesData.parameter
)

# Index for parameter-based filtering
Index(
    "idx_run_time_series_parameter",
    RunTimeSeriesData.run_id,
    RunTimeSeriesData.parameter
)

# Index for time-range queries
Index(
    "idx_run_time_series_timestamp_range",
    RunTimeSeriesData.run_id,
    RunTimeSeriesData.timestamp.desc()
)

# Index for client-based queries
Index(
    "idx_run_client_name",
    RunClient.client_name,
    RunClient.created_at.desc()
)