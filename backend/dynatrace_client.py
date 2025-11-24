import requests
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from config import settings
from entity_manager import EntityManager


class DynatraceClient:
    def __init__(self):
        self.base_url = settings.tenant_url.rstrip("/")
        self.api_token = settings.api_token
        self.headers = {
            "Authorization": f"Api-Token {self.api_token}",
            "Content-Type": "application/json",
        }
        self.entity_manager = EntityManager()

    def validate_connection(self) -> bool:
        """Validate connection to Dynatrace API by fetching metrics"""
        try:
            url = f"{self.base_url}/api/v2/metrics"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Connection validation error: {e}")
            return False

    def get_all_metrics(self) -> Dict[str, Any]:
        """Fetch all available metrics from Dynatrace API v2 with pagination"""
        try:
            all_metrics = []
            next_page_key: Optional[str] = None
            url = f"{self.base_url}/api/v2/metrics"

            while True:
                params = {}
                if next_page_key:
                    params["pageKey"] = next_page_key

                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                metrics = data.get("metrics", [])
                all_metrics.extend(metrics)

                print(f"Fetched {len(metrics)} metrics, total so far: {len(all_metrics)}")

                # Check if there are more pages
                next_page_key = data.get("nextPageKey")
                if not next_page_key:
                    break

            # Create the final structure with all metrics
            metrics_data = {
                "totalCount": data.get("totalCount", len(all_metrics)),
                "metrics": all_metrics,
            }

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

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch entity details by ID"""
        try:
            url = f"{self.base_url}/api/v2/entities/{entity_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            entity_data = response.json()
            # Save to entity manager
            display_name = entity_data.get("displayName", entity_id)
            entity_type = entity_data.get("type", "")
            self.entity_manager.add_entity(entity_id, display_name, entity_type)

            return entity_data
        except Exception as e:
            print(f"Error fetching entity {entity_id}: {e}")
            return None

    def get_metric_data(
        self,
        metric_key: str,
        start_timestamp: int,
        end_timestamp: int,
        resolution: str = "1m",
    ) -> Dict[str, Any]:
        """Fetch metric data for a specific metric using metrics/query endpoint"""
        try:
            url = f"{self.base_url}/api/v2/metrics/query"
            params = {
                "metricSelector": metric_key,
                "resolution": resolution,
                "from": start_timestamp,
                "to": end_timestamp,
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Resolve entity IDs to display names
            self._resolve_entity_ids(data)

            return data
        except Exception as e:
            print(f"Error fetching metric data: {e}")
            return {}

    def _resolve_entity_ids(self, metric_data: Dict[str, Any]) -> None:
        """Resolve entity IDs to display names in metric data"""
        try:
            results = metric_data.get("result", [])
            for result in results:
                # Check if there's an entityId field
                if "entityId" in result:
                    entity_id = result["entityId"]
                    # Get or fetch the entity name
                    if entity_id not in self.entity_manager.get_all_entities():
                        self._fetch_entity_async(entity_id)
                    # Add the display name
                    result["entityName"] = self.entity_manager.get_entity_name(entity_id)
        except Exception as e:
            print(f"Error resolving entity IDs: {e}")

    def _fetch_entity_async(self, entity_id: str) -> None:
        """Fetch entity in background without blocking"""
        try:
            self.get_entity(entity_id)
            # Save entities after updating
            self.entity_manager.save_entities()
        except Exception as e:
            print(f"Error fetching entity async {entity_id}: {e}")

    def get_host_availability(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Get host availability metrics"""
        try:
            # If no time range provided, use last hour
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            return self.get_metric_data(
                "builtin:host.availability",
                start_timestamp,
                end_timestamp,
                "1m"
            )
        except Exception as e:
            print(f"Error fetching host availability: {e}")
            return {}

    def get_application_availability(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Get application availability metrics"""
        try:
            # If no time range provided, use last hour
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            return self.get_metric_data(
                "builtin:app.web.httpRequests.overall",
                start_timestamp,
                end_timestamp,
                "1m"
            )
        except Exception as e:
            print(f"Error fetching application availability: {e}")
            return {}

    def get_service_availability(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Get service availability metrics"""
        try:
            # If no time range provided, use last hour
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            return self.get_metric_data(
                "builtin:service.requestCount.total",
                start_timestamp,
                end_timestamp,
                "1m"
            )
        except Exception as e:
            print(f"Error fetching service availability: {e}")
            return {}
