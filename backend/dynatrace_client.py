import requests
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from config import settings


class DynatraceClient:
    def __init__(self):
        self.base_url = settings.tenant_url.rstrip("/")
        self.api_token = settings.api_token
        self.headers = {
            "Authorization": f"Api-Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def validate_connection(self) -> bool:
        """Validate connection to Dynatrace API"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v2/environments/default",
                headers=self.headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Connection validation error: {e}")
            return False

    def get_all_metrics(self) -> Dict[str, Any]:
        """Fetch all available metrics from Dynatrace API v2"""
        try:
            url = f"{self.base_url}/api/v2/metrics"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            metrics_data = response.json()
            self.save_metrics_to_file(metrics_data)
            return metrics_data
        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return {}

    def save_metrics_to_file(self, metrics_data: Dict[str, Any]) -> str:
        """Save metrics to JSON file"""
        try:
            output_dir = "data"
            os.makedirs(output_dir, exist_ok=True)

            file_path = os.path.join(output_dir, "metrics.json")
            with open(file_path, "w") as f:
                json.dump(metrics_data, f, indent=2)

            print(f"Metrics saved to {file_path}")
            return file_path
        except Exception as e:
            print(f"Error saving metrics: {e}")
            return ""

    def load_metrics_from_file(self) -> list:
        """Load metrics from saved JSON file"""
        try:
            file_path = os.path.join("data", "metrics.json")
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    data = json.load(f)
                    # Extract metric keys for combobox
                    if isinstance(data, dict) and "metrics" in data:
                        return data["metrics"]
                    return []
            return []
        except Exception as e:
            print(f"Error loading metrics: {e}")
            return []

    def get_metric_data(
        self,
        metric_key: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch metric data for a specific metric"""
        try:
            url = f"{self.base_url}/api/v2/timeseries"
            params = {
                "metric": metric_key,
            }

            if start_time:
                params["from"] = start_time
            if end_time:
                params["to"] = end_time

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching metric data: {e}")
            return {}

    def get_host_availability(self) -> Dict[str, Any]:
        """Get host availability metrics"""
        try:
            url = f"{self.base_url}/api/v2/timeseries"
            params = {
                "metric": "builtin:host.availability",
                "resolution": "1m",
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching host availability: {e}")
            return {}

    def get_application_availability(self) -> Dict[str, Any]:
        """Get application availability metrics"""
        try:
            url = f"{self.base_url}/api/v2/timeseries"
            params = {
                "metric": "builtin:apps.other.availability",
                "resolution": "1m",
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching application availability: {e}")
            return {}

    def get_service_availability(self) -> Dict[str, Any]:
        """Get service availability metrics"""
        try:
            url = f"{self.base_url}/api/v2/timeseries"
            params = {
                "metric": "builtin:service.requestCount.total",
                "resolution": "1m",
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching service availability: {e}")
            return {}

    def get_metric_time_series(
        self,
        metric_key: str,
        start_timestamp: int,
        end_timestamp: int,
        resolution: str = "1m",
    ) -> Dict[str, Any]:
        """Get metric time series data with custom time range"""
        try:
            url = f"{self.base_url}/api/v2/timeseries"
            params = {
                "metric": metric_key,
                "from": start_timestamp,
                "to": end_timestamp,
                "resolution": resolution,
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching time series: {e}")
            return {}
