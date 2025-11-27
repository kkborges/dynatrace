from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional, List
from datetime import datetime, timedelta
import time
import threading

from config import settings
from dynatrace_client import DynatraceClient
from models import (
    MetricRequest,
    DashboardConfig,
    TimeRange,
    DashboardMetric,
    AvailabilityMetrics,
)


app = FastAPI(
    title="Dynatrace Metrics Dashboard",
    description="API for managing Dynatrace metrics and dashboards",
    version="1.0.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Dynatrace client
dynatrace_client = DynatraceClient()


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/api/test/availability/dashboard")
async def get_test_availability_dashboard():
    """Test endpoint returning mock dashboard data for debugging"""
    print("TEST ENDPOINT CALLED - Returning mock dashboard data")
    # Mock data in the exact format that Dynatrace API returns
    mock_availability = {
        "totalCount": 1,
        "resolution": "1m",
        "result": [
            {
                "metricId": "builtin:host.availability",
                "dataPointCountRatio": 1.0,
                "dimensionCountRatio": 1.0,
                "data": [
                    {
                        "dimensions": [],
                        "timestamps": [1732634400000, 1732634460000, 1732634520000],
                        "values": [[99.5], [99.3], [99.8]]
                    }
                ]
            }
        ]
    }

    mock_cpu = {
        "totalCount": 1,
        "resolution": "1m",
        "result": [
            {
                "metricId": "builtin:host.cpu.usage",
                "dataPointCountRatio": 1.0,
                "dimensionCountRatio": 1.0,
                "data": [
                    {
                        "dimensions": [],
                        "timestamps": [1732634400000, 1732634460000, 1732634520000],
                        "values": [[45.2], [47.1], [43.8]]
                    }
                ]
            }
        ]
    }

    mock_memory = {
        "totalCount": 1,
        "resolution": "1m",
        "result": [
            {
                "metricId": "builtin:host.mem.usage",
                "dataPointCountRatio": 1.0,
                "dimensionCountRatio": 1.0,
                "data": [
                    {
                        "dimensions": [],
                        "timestamps": [1732634400000, 1732634460000, 1732634520000],
                        "values": [[72.5], [73.1], [71.8]]
                    }
                ]
            }
        ]
    }

    mock_network = {
        "totalCount": 1,
        "resolution": "1m",
        "result": [
            {
                "metricId": "builtin:host.net.nic.connectivity",
                "dataPointCountRatio": 1.0,
                "dimensionCountRatio": 1.0,
                "data": [
                    {
                        "dimensions": [],
                        "timestamps": [1732634400000, 1732634460000, 1732634520000],
                        "values": [[98.9], [99.1], [98.5]]
                    }
                ]
            }
        ]
    }

    return {
        "availability": mock_availability,
        "cpu_usage": mock_cpu,
        "memory_usage": mock_memory,
        "network_connectivity": mock_network,
    }


@app.get("/api/dynatrace/validate")
async def validate_dynatrace_connection():
    """Validate Dynatrace API connection"""
    try:
        is_valid = dynatrace_client.validate_connection()
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid Dynatrace credentials")
        return {"status": "connected", "tenant_url": settings.tenant_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection validation error: {str(e)}")


@app.post("/api/metrics/refresh")
async def refresh_metrics(background_tasks: BackgroundTasks):
    """Refresh all metrics from Dynatrace API (async)"""
    try:
        # Check if refresh is already in progress
        if hasattr(refresh_metrics, '_is_running') and refresh_metrics._is_running:
            return {
                "status": "in_progress",
                "message": "Metrics refresh is already in progress. Please wait..."
            }

        # Start async refresh in background
        refresh_metrics._is_running = True

        def refresh_in_background():
            try:
                print("Starting metrics refresh in background...")
                metrics = dynatrace_client.get_all_metrics()
                metrics_count = len(metrics.get("metrics", []))
                print(f"Metrics refresh completed: {metrics_count} metrics")
                refresh_metrics._is_running = False
            except Exception as e:
                print(f"Error in background metrics refresh: {e}")
                refresh_metrics._is_running = False

        # Run in background thread to not block the response
        thread = threading.Thread(target=refresh_in_background, daemon=True)
        thread.start()

        return {
            "status": "started",
            "message": "Metrics refresh started in background. Check metrics list after a moment."
        }
    except Exception as e:
        refresh_metrics._is_running = False
        raise HTTPException(status_code=500, detail=f"Error starting metrics refresh: {str(e)}")


@app.get("/api/metrics/list")
async def get_metrics_list():
    """Get list of available metrics from saved file"""
    try:
        metrics = dynatrace_client.load_metrics_from_file()
        return {"metrics": metrics, "count": len(metrics)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading metrics: {str(e)}")


@app.get("/api/metrics/validate/{metric_key}")
async def validate_metric(metric_key: str):
    """Validate if a metric exists and is queryable"""
    try:
        # Load cached metrics
        metrics = dynatrace_client.load_metrics_from_file()

        # Check if metric exists in cache (metrics are now transformed with 'key' field)
        metric_exists = any(
            (isinstance(m, dict) and (m.get("key") == metric_key or m.get("metricId") == metric_key))
            for m in metrics
        )

        if not metric_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Metric '{metric_key}' not found. Please refresh metrics first."
            )

        return {
            "metric_key": metric_key,
            "valid": True,
            "message": "Metric is valid and queryable"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating metric: {str(e)}")


@app.post("/api/metrics/data")
async def get_metric_data(request: MetricRequest):
    """Get metric data for a specific metric"""
    try:
        data = dynatrace_client.get_metric_data(
            metric_key=request.metric_key,
            start_timestamp=request.start_timestamp,
            end_timestamp=request.end_timestamp,
            resolution=request.resolution,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metric data: {str(e)}")


@app.get("/api/availability/dashboard")
async def get_availability_dashboard():
    """Get host metrics for main dashboard"""
    try:
        availability_data = dynatrace_client.get_host_availability()
        cpu_data = dynatrace_client.get_host_cpu_usage()
        memory_data = dynatrace_client.get_host_memory_usage()
        network_data = dynatrace_client.get_host_network_connectivity()

        print("Dashboard metrics fetched successfully")
        print(f"  Availability: {len(availability_data.get('result', []))} results")
        print(f"  CPU Usage: {len(cpu_data.get('result', []))} results")
        print(f"  Memory Usage: {len(memory_data.get('result', []))} results")
        print(f"  Network Connectivity: {len(network_data.get('result', []))} results")

        return {
            "availability": availability_data,
            "cpu_usage": cpu_data,
            "memory_usage": memory_data,
            "network_connectivity": network_data,
        }
    except Exception as e:
        print(f"ERROR in get_availability_dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}")


@app.post("/api/dashboard/test")
async def test_dashboard_metrics(config: DashboardConfig):
    """Test dashboard configuration by fetching all metric data"""
    try:
        test_results = []

        for metric in config.metrics:
            try:
                data = dynatrace_client.get_metric_data(
                    metric_key=metric.metric_key,
                    start_timestamp=metric.start_timestamp,
                    end_timestamp=metric.end_timestamp,
                    resolution=metric.resolution,
                )

                test_results.append({
                    "metric_key": metric.metric_key,
                    "status": "success",
                    "data_points": len(data.get("result", [])) if "result" in data else 0,
                })
            except Exception as e:
                test_results.append({
                    "metric_key": metric.metric_key,
                    "status": "error",
                    "error": str(e),
                })

        return {"test_results": test_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing dashboard: {str(e)}")


@app.get("/api/time-range/calculate")
async def calculate_time_range(
    type: str = Query(...),
    custom_start: Optional[int] = Query(None),
    custom_end: Optional[int] = None,
):
    """Calculate start and end timestamps for different time ranges"""
    try:
        now = int(time.time() * 1000)  # Current time in milliseconds

        if type == "1m":
            start = now - (1 * 60 * 1000)
        elif type == "5m":
            start = now - (5 * 60 * 1000)
        elif type == "15m":
            start = now - (15 * 60 * 1000)
        elif type == "30m":
            start = now - (30 * 60 * 1000)
        elif type == "1h":
            start = now - (1 * 60 * 60 * 1000)
        elif type == "today":
            start = int(datetime.now().replace(hour=0, minute=1, second=0, microsecond=0).timestamp() * 1000)
        elif type == "yesterday":
            yesterday = datetime.now() - timedelta(days=1)
            start = int(yesterday.replace(hour=0, minute=1, second=0, microsecond=0).timestamp() * 1000)
            now = int(yesterday.replace(hour=23, minute=59, second=59, microsecond=0).timestamp() * 1000)
        elif type == "30days":
            start = now - (30 * 24 * 60 * 60 * 1000)
        elif type == "custom":
            if custom_start is None:
                raise HTTPException(status_code=400, detail="custom_start is required for custom time range")
            start = custom_start
            now = custom_end if custom_end else now
        else:
            raise HTTPException(status_code=400, detail=f"Invalid time range type: {type}")

        return {
            "type": type,
            "start_timestamp": start,
            "end_timestamp": now,
            "start_datetime": datetime.fromtimestamp(start / 1000).isoformat(),
            "end_datetime": datetime.fromtimestamp(now / 1000).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating time range: {str(e)}")


@app.get("/api/chart-types")
async def get_chart_types():
    """Get available chart types"""
    return {
        "chart_types": [
            {"id": "line", "name": "Line Chart", "category": "common"},
            {"id": "bar", "name": "Bar Chart", "category": "common"},
            {"id": "area", "name": "Area Chart", "category": "common"},
            {"id": "scatter", "name": "Scatter Plot", "category": "common"},
            {"id": "pie", "name": "Pie Chart", "category": "common"},
            {"id": "gauge", "name": "Gauge Chart", "category": "modern"},
            {"id": "candlestick", "name": "Candlestick Chart", "category": "modern"},
            {"id": "heatmap", "name": "Heatmap", "category": "modern"},
        ]
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Dynatrace Metrics Dashboard API",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=True,
    )
