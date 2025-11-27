from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class MetricRequest(BaseModel):
    metric_key: str
    start_timestamp: int
    end_timestamp: int
    resolution: str = "1m"


class DashboardMetric(BaseModel):
    metric_key: str
    chart_type: str
    start_timestamp: int
    end_timestamp: int
    resolution: str = "1m"
    dimension: Optional[str] = None  # Selected dimension to display
    filter_entity: Optional[str] = None  # Filter by specific entity name
    split_by_dimension: bool = False  # Whether to split chart by dimension values


class DashboardConfig(BaseModel):
    metrics: List[DashboardMetric]
    dashboard_name: str


class SavedDashboard(BaseModel):
    """Dashboard saved to server or exported as JSON"""
    id: Optional[str] = None  # UUID for server-stored dashboards
    name: str
    description: Optional[str] = None
    metrics: List[DashboardMetric]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TimeRange(BaseModel):
    type: str  # "1m", "5m", "15m", "30m", "1h", "today", "yesterday", "30days", "custom"
    start_time: Optional[int] = None
    end_time: Optional[int] = None


class MetricData(BaseModel):
    metric_key: str
    data: Dict[str, Any]


class AvailabilityMetrics(BaseModel):
    availability: Dict[str, Any]
    cpu_usage: Dict[str, Any]
    memory_usage: Dict[str, Any]
    network_connectivity: Dict[str, Any]


class DimensionInfo(BaseModel):
    """Information about available dimensions in metric data"""
    dimension_name: str
    values: List[str]  # Unique values for this dimension
    entity_names: Optional[List[str]] = None  # Entity names if applicable


class TestResult(BaseModel):
    metric_key: str
    status: str
    data_points: Optional[int] = None
    error: Optional[str] = None
    dimensions: Optional[List[str]] = None  # Available dimensions in the data
