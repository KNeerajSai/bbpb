"""
Pydantic schemas for fermentation data API requests and responses.
Provides comprehensive validation and serialization for all endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, validator


class PumpParameter(str, Enum):
    """Enumeration of valid pump parameters."""
    # Pump1 options
    GLUCOSE = "Glucose"
    GLYCEROL = "Glycerol"
    
    # Pump2 options  
    BASE = "Base"
    ACID = "Acid"


class ProcessingStatus(str, Enum):
    """Enumeration of file processing statuses."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PumpSelection(BaseModel):
    """Schema for user pump parameter selection."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        validate_assignment=True
    )
    
    pump1: PumpParameter = Field(
        description="Selected parameter for Pump1 (Glucose or Glycerol)"
    )
    pump2: PumpParameter = Field(
        description="Selected parameter for Pump2 (Base or Acid)"
    )
    
    @validator("pump1")
    def validate_pump1(cls, v):
        """Validate Pump1 parameter selection."""
        if v not in [PumpParameter.GLUCOSE, PumpParameter.GLYCEROL]:
            raise ValueError("Pump1 must be either 'Glucose' or 'Glycerol'")
        return v
    
    @validator("pump2") 
    def validate_pump2(cls, v):
        """Validate Pump2 parameter selection."""
        if v not in [PumpParameter.BASE, PumpParameter.ACID]:
            raise ValueError("Pump2 must be either 'Base' or 'Acid'")
        return v


class TimeSeriesDataPoint(BaseModel):
    """Schema for a single time series data point."""
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=False
    )
    
    timestamp: float = Field(
        ge=0.0,
        description="Timestamp value from the CSV file"
    )
    parameter: str = Field(
        min_length=1,
        max_length=100,
        description="Parameter name (pH, Temperature, or pump parameter)"
    )
    process_value: float = Field(
        description="Process value for the parameter at the given timestamp"
    )
    units: str = Field(
        min_length=1,
        max_length=50,
        description="Units of measurement for the process value"
    )
    is_outlier: bool = Field(
        default=False,
        description="Flag indicating if this data point is an outlier"
    )
    data_quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality score for this data point (0.0 to 1.0)"
    )


class RunClientBase(BaseModel):
    """Base schema for run client data."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    run_id: str = Field(
        min_length=1,
        max_length=100,
        description="Unique identifier for the fermentation run"
    )
    client_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the client"
    )


class RunClientResponse(RunClientBase):
    """Schema for run client API responses."""
    id: int = Field(description="Database primary key")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: Optional[datetime] = Field(description="Last update timestamp")
    original_filename: Optional[str] = Field(description="Original CSV filename")
    file_size_bytes: Optional[int] = Field(description="File size in bytes")
    total_data_points: Optional[int] = Field(description="Total number of data points")
    processing_status: ProcessingStatus = Field(description="Processing status")
    pump1_parameter: Optional[str] = Field(description="Selected Pump1 parameter")
    pump2_parameter: Optional[str] = Field(description="Selected Pump2 parameter")
    
    model_config = ConfigDict(from_attributes=True)


class RunTimeSeriesDataResponse(BaseModel):
    """Schema for time series data API responses."""
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True
    )
    
    id: int = Field(description="Database primary key")
    run_id: str = Field(description="Associated run identifier")
    timestamp: float = Field(description="Timestamp value")
    parameter: str = Field(description="Parameter name")
    process_value: float = Field(description="Process value")
    units: str = Field(description="Units of measurement")
    created_at: datetime = Field(description="Creation timestamp")
    is_outlier: bool = Field(description="Outlier flag")
    data_quality_score: Optional[float] = Field(description="Data quality score")


class FileUploadResponse(BaseModel):
    """Schema for file upload API response."""
    model_config = ConfigDict(validate_assignment=True)
    
    success: bool = Field(description="Upload success status")
    message: str = Field(description="Response message")
    run_id: str = Field(description="Generated or extracted run ID")
    client_name: str = Field(description="Extracted client name")
    total_data_points: int = Field(
        ge=0,
        description="Number of data points processed"
    )
    processing_time_seconds: float = Field(
        ge=0.0,
        description="Time taken to process the file"
    )
    file_info: Dict[str, Any] = Field(description="File metadata information")
    pump_configuration: PumpSelection = Field(description="Selected pump parameters")


class VisualizationData(BaseModel):
    """Schema for visualization data API response."""
    model_config = ConfigDict(validate_assignment=True)
    
    run_info: RunClientResponse = Field(description="Run information")
    data_points: List[RunTimeSeriesDataResponse] = Field(
        description="Time series data points"
    )
    parameters: List[str] = Field(description="Available parameters")
    time_range: Dict[str, float] = Field(
        description="Time range information (min, max)"
    )
    statistics: Dict[str, Dict[str, float]] = Field(
        description="Statistical summary for each parameter"
    )
    
    @validator("time_range")
    def validate_time_range(cls, v):
        """Validate time range structure."""
        required_keys = {"min", "max"}
        if not required_keys.issubset(v.keys()):
            raise ValueError("Time range must contain 'min' and 'max' keys")
        if v["min"] > v["max"]:
            raise ValueError("Time range min cannot be greater than max")
        return v


class RunStatistics(BaseModel):
    """Schema for run statistics API response."""
    model_config = ConfigDict(validate_assignment=True)
    
    run_id: str = Field(description="Run identifier")
    total_data_points: int = Field(ge=0, description="Total data points")
    duration_hours: float = Field(ge=0.0, description="Run duration in hours")
    parameters: Dict[str, Dict[str, float]] = Field(
        description="Statistics for each parameter"
    )
    data_quality: Dict[str, Any] = Field(description="Data quality metrics")
    outliers_detected: int = Field(ge=0, description="Number of outliers detected")
    sampling_frequency: Dict[str, float] = Field(
        description="Average sampling frequency per parameter"
    )


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    model_config = ConfigDict(validate_assignment=True)
    
    error: bool = Field(default=True, description="Error flag")
    message: str = Field(description="Error message")
    error_code: str = Field(description="Error code for client handling")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Error timestamp in ISO format"
    )


class HealthCheckResponse(BaseModel):
    """Schema for health check API response."""
    model_config = ConfigDict(validate_assignment=True)
    
    status: str = Field(description="Service status")
    timestamp: datetime = Field(description="Health check timestamp")
    version: str = Field(description="Application version")
    database: str = Field(description="Database connectivity status")
    uptime_seconds: float = Field(description="Application uptime in seconds")


class PumpOptions(BaseModel):
    """Schema for pump options API response."""
    model_config = ConfigDict(validate_assignment=True)
    
    pump1_options: List[str] = Field(
        default=[PumpParameter.GLUCOSE.value, PumpParameter.GLYCEROL.value],
        description="Available options for Pump1"
    )
    pump2_options: List[str] = Field(
        default=[PumpParameter.BASE.value, PumpParameter.ACID.value],
        description="Available options for Pump2"
    )


# Request schemas
class FileUploadRequest(BaseModel):
    """Schema for file upload request metadata."""
    model_config = ConfigDict(validate_assignment=True)
    
    pump_selection: PumpSelection = Field(description="Pump parameter selection")
    filename: str = Field(description="Original filename")
    file_size: int = Field(ge=0, description="File size in bytes")


class RunDeleteRequest(BaseModel):
    """Schema for run deletion request."""
    model_config = ConfigDict(validate_assignment=True)
    
    confirm: bool = Field(
        default=False,
        description="Confirmation flag for deletion"
    )
    
    @validator("confirm")
    def validate_confirm(cls, v):
        """Validate confirmation flag."""
        if not v:
            raise ValueError("Deletion must be confirmed")
        return v