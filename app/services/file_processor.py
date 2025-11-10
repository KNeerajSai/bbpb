"""
File processing service for handling CSV uploads and data parsing.
Implements robust data validation, cleaning, and error handling.
"""

import io
import re
import time
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd
import numpy as np
from fastapi import HTTPException, UploadFile

from app.schemas.fermentation import PumpSelection, TimeSeriesDataPoint
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class FileProcessorService:
    """Service for processing uploaded CSV files with comprehensive validation."""
    
    def __init__(self):
        self.required_parameters = {"pH", "Temperature", "Pump1", "Pump2"}
        self.expected_columns = ["Time Stamp", "Parameter", "Process value", "Units"]
        self.max_file_size = settings.max_file_size
        self.allowed_extensions = settings.allowed_file_extensions
    
    async def process_uploaded_file(
        self, 
        file: UploadFile, 
        pump_selection: PumpSelection
    ) -> Tuple[str, str, List[TimeSeriesDataPoint], Dict[str, Any]]:
        """
        Process uploaded CSV file and return parsed data.
        
        Args:
            file: Uploaded CSV file
            pump_selection: User-selected pump parameters
            
        Returns:
            Tuple of (client_name, run_id, data_points, file_metadata)
            
        Raises:
            HTTPException: If file processing fails
        """
        start_time = time.time()
        
        try:
            # Validate file
            await self._validate_file(file)
            
            # Extract metadata from filename
            client_name, run_id = self._extract_metadata_from_filename(file.filename)
            
            # Read and process file content
            file_content = await file.read()
            data_points = await self._parse_csv_content(
                file_content, pump_selection, client_name, run_id
            )
            
            # Generate file metadata
            file_metadata = self._generate_file_metadata(
                file, len(data_points), time.time() - start_time
            )
            
            logger.info(
                f"Successfully processed file {file.filename}: "
                f"{len(data_points)} data points in {file_metadata['processing_time']:.2f}s"
            )
            
            return client_name, run_id, data_points, file_metadata
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing file {file.filename}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal error processing file: {str(e)}"
            )
    
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file meets requirements."""
        # Check file extension
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_path = Path(file.filename)
        if file_path.suffix.lower() not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed extensions: {', '.join(self.allowed_extensions)}"
            )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)     # Reset to beginning
        
        if file_size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {self.max_file_size / 1_000_000:.1f}MB"
            )
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    def _extract_metadata_from_filename(self, filename: str) -> Tuple[str, str]:
        """
        Extract client name and run ID from filename.
        Expected format: ClientName_RunID_*.csv
        """
        # Remove file extension and clean filename
        base_name = Path(filename).stem
        
        # Pattern to match ClientName_RunID_... format
        pattern = r'^([^_]+)_([^_]+)_.*$'
        match = re.match(pattern, base_name)
        
        if not match:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename format. Expected: ClientName_RunID_*.csv"
            )
        
        client_name = match.group(1).strip()
        run_id = match.group(2).strip()
        
        # Validate extracted values
        if not client_name or not run_id:
            raise HTTPException(
                status_code=400,
                detail="Client name and run ID cannot be empty"
            )
        
        # Additional validation for run ID format
        if not re.match(r'^R\d+$', run_id, re.IGNORECASE):
            logger.warning(f"Run ID '{run_id}' doesn't follow expected format (R followed by numbers)")
        
        logger.info(f"Extracted metadata: Client={client_name}, RunID={run_id}")
        return client_name, run_id
    
    async def _parse_csv_content(
        self, 
        file_content: bytes, 
        pump_selection: PumpSelection,
        client_name: str,
        run_id: str
    ) -> List[TimeSeriesDataPoint]:
        """Parse CSV content and return validated data points."""
        try:
            # Read CSV with robust encoding handling
            df = self._read_csv_robust(file_content)
            
            # Validate and clean CSV structure
            df = self._validate_and_clean_csv(df, client_name, run_id)
            
            # Process pump parameters
            df = self._process_pump_parameters(df, pump_selection)
            
            # Convert to data points with validation
            data_points = self._convert_to_data_points(df)
            
            # Perform data quality checks
            data_points = self._perform_data_quality_checks(data_points)
            
            return data_points
            
        except Exception as e:
            logger.error(f"CSV parsing failed: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse CSV file: {str(e)}"
            )
    
    def _read_csv_robust(self, file_content: bytes) -> pd.DataFrame:
        """Read CSV with multiple encoding attempts and error handling."""
        encodings = ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    io.BytesIO(file_content),
                    encoding=encoding,
                    skipinitialspace=True,
                    na_values=['', ' ', 'NA', 'N/A', 'null', 'NULL'],
                    dtype=str  # Read all as string initially
                )
                logger.info(f"Successfully read CSV with encoding: {encoding}")
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Failed to read with encoding {encoding}: {e}")
                continue
        
        raise ValueError("Could not read CSV file with any supported encoding")
    
    def _validate_and_clean_csv(self, df: pd.DataFrame, client_name: str, run_id: str) -> pd.DataFrame:
        """Validate CSV structure and clean data."""
        if df.empty:
            raise ValueError("CSV file is empty")
        
        # Handle Boston Bioprocess format with metadata rows and sparse columns
        # Look for the header row containing "Time Stamp", "Parameter", "Process value", "Units"
        header_row_idx = None
        for i, row in df.iterrows():
            if any('Time Stamp' in str(val) for val in row if pd.notna(val)):
                header_row_idx = i
                break
        
        if header_row_idx is not None:
            # Skip to data rows after header
            df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
            
            # Handle sparse format where data is in columns 0,2,4,6 (timestamp, empty, parameter, empty, process_value, empty, units)
            if df.shape[1] >= 7:  # Boston Bioprocess sparse format
                # Extract only the non-empty columns: 0=timestamp, 2=parameter, 4=process_value, 6=units
                cleaned_data = []
                for _, row in df.iterrows():
                    if (len(row) >= 7 and 
                        pd.notna(row.iloc[0]) and str(row.iloc[0]).strip() != '' and
                        pd.notna(row.iloc[2]) and str(row.iloc[2]).strip() != '' and
                        pd.notna(row.iloc[4]) and str(row.iloc[4]).strip() != '' and
                        pd.notna(row.iloc[6]) and str(row.iloc[6]).strip() != ''):
                        
                        cleaned_data.append({
                            'timestamp': str(row.iloc[0]).strip(),
                            'parameter': str(row.iloc[2]).strip(),
                            'process_value': str(row.iloc[4]).strip(),
                            'units': str(row.iloc[6]).strip()
                        })
                
                if not cleaned_data:
                    raise ValueError("No valid data rows found in Boston Bioprocess format")
                
                # Create new DataFrame with cleaned data
                df = pd.DataFrame(cleaned_data)
            else:
                # Standard format - use existing logic
                # Clean column names and map them
                df.columns = df.columns.astype(str).str.strip()
                
                if len(df.columns) < 4:
                    raise ValueError("CSV must have at least 4 columns: Time Stamp, Parameter, Process value, Units")
                
                column_mapping = self._map_columns(df.columns)
                df = df.rename(columns=column_mapping)
                
                try:
                    df = df[['timestamp', 'parameter', 'process_value', 'units']].copy()
                except KeyError as e:
                    raise ValueError(f"Missing required columns: {e}")
                
                # Remove empty rows
                df = df.dropna(subset=['timestamp', 'parameter', 'process_value', 'units'])
        else:
            raise ValueError("Could not find header row with Time Stamp, Parameter, Process value, Units")
        
        if df.empty:
            raise ValueError("No valid data rows found in CSV")
        
        return df
    
    def _map_columns(self, columns: List[str]) -> Dict[str, str]:
        """Map CSV columns to standardized names."""
        column_mapping = {}
        
        for i, col in enumerate(columns[:4]):
            col_lower = col.lower()
            if i == 0 or 'time' in col_lower or 'stamp' in col_lower:
                column_mapping[col] = 'timestamp'
            elif i == 1 or 'parameter' in col_lower or 'param' in col_lower:
                column_mapping[col] = 'parameter'
            elif i == 2 or 'value' in col_lower or 'process' in col_lower:
                column_mapping[col] = 'process_value'
            elif i == 3 or 'unit' in col_lower:
                column_mapping[col] = 'units'
        
        return column_mapping
    
    def _process_pump_parameters(self, df: pd.DataFrame, pump_selection: PumpSelection) -> pd.DataFrame:
        """Replace pump parameters with user-selected values."""
        # Handle both string values and enum objects
        pump1_value = pump_selection.pump1 if isinstance(pump_selection.pump1, str) else pump_selection.pump1.value
        pump2_value = pump_selection.pump2 if isinstance(pump_selection.pump2, str) else pump_selection.pump2.value
        
        parameter_mapping = {
            'Pump1': pump1_value,
            'Pump2': pump2_value
        }
        
        df['parameter'] = df['parameter'].replace(parameter_mapping)
        
        # Validate required parameters are present
        unique_parameters = set(df['parameter'].unique())
        expected_parameters = {
            'pH', 'Temperature', 
            pump1_value, 
            pump2_value
        }
        
        missing_parameters = expected_parameters - unique_parameters
        if missing_parameters:
            logger.warning(f"Missing expected parameters: {missing_parameters}")
        
        return df
    
    def _convert_to_data_points(self, df: pd.DataFrame) -> List[TimeSeriesDataPoint]:
        """Convert DataFrame to validated TimeSeriesDataPoint objects."""
        data_points = []
        
        for _, row in df.iterrows():
            try:
                # Convert and validate data types
                timestamp_str = str(row['timestamp']).strip()
                
                # Handle different timestamp formats
                if timestamp_str.replace('.', '').isdigit():  # Decimal format like 0.009, 0.026
                    # Keep as-is for simple time values from CSV
                    timestamp = float(timestamp_str)
                else:
                    # ISO datetime format
                    timestamp_dt = pd.to_datetime(timestamp_str, utc=True)
                    timestamp = timestamp_dt.timestamp()
                
                process_value = float(row['process_value'])
                parameter = str(row['parameter']).strip()
                units = str(row['units']).strip()
                
                # Create data point with validation
                data_point = TimeSeriesDataPoint(
                    timestamp=timestamp,
                    parameter=parameter,
                    process_value=process_value,
                    units=units
                )
                
                data_points.append(data_point)
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid data row: {row.to_dict()}, Error: {e}")
                continue
        
        if not data_points:
            raise ValueError("No valid data points found in CSV")
        
        return data_points
    
    def _perform_data_quality_checks(self, data_points: List[TimeSeriesDataPoint]) -> List[TimeSeriesDataPoint]:
        """Perform data quality checks and flag outliers."""
        # Group by parameter for quality analysis
        parameter_groups = {}
        for point in data_points:
            if point.parameter not in parameter_groups:
                parameter_groups[point.parameter] = []
            parameter_groups[point.parameter].append(point)
        
        # Detect outliers using IQR method
        for parameter, points in parameter_groups.items():
            values = [p.process_value for p in points]
            if len(values) < 4:  # Need at least 4 points for IQR
                continue
            
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            for point in points:
                if point.process_value < lower_bound or point.process_value > upper_bound:
                    point.is_outlier = True
                
                # Calculate quality score based on proximity to median
                median_value = np.median(values)
                deviation = abs(point.process_value - median_value)
                max_deviation = max(abs(lower_bound - median_value), abs(upper_bound - median_value))
                
                if max_deviation > 0:
                    quality_score = max(0.0, 1.0 - (deviation / max_deviation))
                    point.data_quality_score = min(1.0, quality_score)
                else:
                    point.data_quality_score = 1.0
        
        return data_points
    
    def _generate_file_metadata(
        self, 
        file: UploadFile, 
        data_point_count: int, 
        processing_time: float
    ) -> Dict[str, Any]:
        """Generate comprehensive file metadata."""
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        return {
            "original_filename": file.filename,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / 1_000_000, 2),
            "content_type": file.content_type,
            "data_points_processed": data_point_count,
            "processing_time": round(processing_time, 3),
            "average_points_per_second": round(data_point_count / max(processing_time, 0.001), 2)
        }