from pydantic import BaseModel
from typing import List, Optional, Dict, Any


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


class DashboardConfig(BaseModel):
    metrics: List[DashboardMetric]
    dashboard_name: str


class TimeRange(BaseModel):
    type: str  # "1m", "5m", "15m", "30m", "1h", "today", "yesterday", "30days", "custom"
    start_time: Optional[int] = None
    end_time: Optional[int] = None


class MetricData(BaseModel):
    metric_key: str
    data: Dict[str, Any]


class AvailabilityMetrics(BaseModel):
    hosts: Dict[str, Any]
    applications: Dict[str, Any]
    services: Dict[str, Any]
