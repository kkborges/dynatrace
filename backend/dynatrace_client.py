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
            import time as time_module

            all_metrics = []
            seen_metric_ids = set()  # Track metric IDs to detect duplicates
            next_page_key: Optional[str] = None
            url = f"{self.base_url}/api/v2/metrics"
            page_count = 0
            max_pages = 1000  # Increased limit to fetch all metrics (1000 pages * 500 metrics = 500k max)
            start_time = time_module.time()
            max_duration = 600  # 10 minute timeout
            page_size = 500  # Request 500 metrics per page

            print(f"Starting metrics fetch with max timeout of {max_duration}s, max pages={max_pages}...")

            while page_count < max_pages:
                # Check timeout
                elapsed = time_module.time() - start_time
                if elapsed > max_duration:
                    print(f"Timeout reached ({elapsed:.0f}s). Stopping pagination.")
                    break

                params = {"pageSize": page_size}
                if next_page_key:
                    params["pageKey"] = next_page_key

                print(f"Fetching page {page_count + 1}... (elapsed: {elapsed:.1f}s, total metrics: {len(all_metrics)})")
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                metrics = data.get("metrics", [])

                # If no metrics returned, we've reached the end
                if not metrics:
                    print(f"No metrics in this page. Stopping pagination.")
                    break

                # Filter to only include builtin metrics - check multiple possible key names
                page_metrics = []
                for m in metrics:
                    if not isinstance(m, dict):
                        continue

                    # Try different possible field names for metric identifier
                    metric_id = m.get("metricId") or m.get("key") or m.get("id") or m.get("name", "")

                    # Only include builtin metrics
                    if isinstance(metric_id, str) and metric_id.startswith("builtin:"):
                        # Avoid duplicates within this page
                        if metric_id not in seen_metric_ids:
                            page_metrics.append(m)
                            seen_metric_ids.add(metric_id)

                # Add metrics from this page
                all_metrics.extend(page_metrics)
                page_count += 1

                elapsed = time_module.time() - start_time
                print(f"Page {page_count}: Found {len(page_metrics)} builtin metrics, total: {len(all_metrics)} ({elapsed:.1f}s)")

                # Check if there are more pages
                next_page_key = data.get("nextPageKey")
                if not next_page_key:
                    print(f"Pagination complete. No nextPageKey after {page_count} pages.")
                    break

            elapsed = time_module.time() - start_time
            print(f"Metrics fetch complete: {len(all_metrics)} unique builtin metrics in {page_count} pages, {elapsed:.1f}s total")

            # Create the final structure with all metrics
            metrics_data = {
                "totalCount": len(all_metrics),
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
                        # Transform metrics to expected format
                        return self._transform_metrics(data["metrics"])
                    return []
            return []
        except Exception as e:
            print(f"Error loading metrics: {e}")
            return []

    def _transform_metrics(self, raw_metrics: list) -> list:
        """Transform raw Dynatrace metrics to frontend format"""
        try:
            transformed = []
            for metric in raw_metrics:
                if not isinstance(metric, dict):
                    continue

                # Extract fields from Dynatrace API response
                metric_id = metric.get("metricId") or metric.get("key") or metric.get("id", "")
                display_name = metric.get("displayName") or metric.get("name") or metric_id
                unit = metric.get("unit", "")
                description = metric.get("description", "")

                # Transform to frontend format
                transformed_metric = {
                    "key": metric_id,  # Use metricId as key
                    "name": display_name,  # Use displayName as name
                }

                if unit:
                    transformed_metric["unit"] = unit
                if description:
                    transformed_metric["description"] = description

                transformed.append(transformed_metric)

            return transformed
        except Exception as e:
            print(f"Error transforming metrics: {e}")
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

            # Convert timestamps from milliseconds to ISO 8601 format
            from_iso = self._timestamp_to_iso8601(start_timestamp)
            to_iso = self._timestamp_to_iso8601(end_timestamp)

            params = {
                "metricSelector": metric_key,
                "resolution": resolution,
                "from": from_iso,
                "to": to_iso,
            }

            print(f"Querying metric {metric_key} from {from_iso} to {to_iso}")
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Debug logging
            if "result" in data:
                print(f"  Result count: {len(data['result'])}")
                if data["result"]:
                    print(f"  Result[0] keys: {list(data['result'][0].keys())}")
                    if 'data' in data['result'][0]:
                        data_field = data['result'][0]['data']
                        print(f"  Result[0].data type: {type(data_field)}, length: {len(data_field) if isinstance(data_field, list) else 'N/A'}")
                        if isinstance(data_field, list) and len(data_field) > 0:
                            print(f"  Result[0].data[0] keys: {list(data_field[0].keys()) if isinstance(data_field[0], dict) else 'not a dict'}")
                            # Log sample of the first data element
                            if isinstance(data_field[0], dict):
                                for key in data_field[0].keys():
                                    value = data_field[0][key]
                                    if isinstance(value, list):
                                        print(f"    {key}: list with {len(value)} items")
                                        if len(value) > 0:
                                            print(f"      First item: {value[0]}")
                                    else:
                                        print(f"    {key}: {value}")

            # Resolve entity IDs to display names
            self._resolve_entity_ids(data)

            return data
        except Exception as e:
            print(f"Error fetching metric data for {metric_key}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _timestamp_to_iso8601(self, timestamp_ms: int) -> str:
        """Convert timestamp in milliseconds to ISO 8601 format"""
        try:
            # Convert milliseconds to seconds
            timestamp_sec = timestamp_ms / 1000
            # Create datetime object and format as ISO 8601
            dt = datetime.fromtimestamp(timestamp_sec)
            # Return ISO 8601 format without microseconds
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception as e:
            print(f"Error converting timestamp: {e}")
            # Fallback to current time
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

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
        """Get host availability metric"""
        try:
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

    def get_host_cpu_usage(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Get host CPU usage metric"""
        try:
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            return self.get_metric_data(
                "builtin:host.cpu.usage",
                start_timestamp,
                end_timestamp,
                "1m"
            )
        except Exception as e:
            print(f"Error fetching host CPU usage: {e}")
            return {}

    def get_host_memory_usage(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Get host memory usage metric"""
        try:
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            return self.get_metric_data(
                "builtin:host.mem.usage",
                start_timestamp,
                end_timestamp,
                "1m"
            )
        except Exception as e:
            print(f"Error fetching host memory usage: {e}")
            return {}

    def get_host_network_connectivity(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Get host network connectivity metric"""
        try:
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            return self.get_metric_data(
                "builtin:host.net.nic.connectivity",
                start_timestamp,
                end_timestamp,
                "1m"
            )
        except Exception as e:
            print(f"Error fetching host network connectivity: {e}")
            return {}

    def get_application_availability(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Deprecated - use get_host_cpu_usage instead"""
        return self.get_host_cpu_usage(start_timestamp, end_timestamp)

    def get_service_availability(self, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Deprecated - use get_host_memory_usage instead"""
        return self.get_host_memory_usage(start_timestamp, end_timestamp)

    def _calculate_success_rate(self, successful_data: Dict[str, Any], overall_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate success rate from successful and overall requests"""
        try:
            # Get the latest values from both metrics
            successful_value = self._extract_latest_value(successful_data)
            overall_value = self._extract_latest_value(overall_data)

            if successful_value is not None and overall_value is not None and overall_value > 0:
                success_rate = (successful_value / overall_value) * 100
                # Return in the same structure as metric query response
                return {
                    "result": [{
                        "data": [{
                            "values": [[success_rate]]
                        }]
                    }]
                }
            return overall_data  # Fall back to overall if can't calculate
        except Exception as e:
            print(f"Error calculating success rate: {e}")
            return overall_data

    def _calculate_availability_from_errors(self, total_data: Dict[str, Any], error_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate availability from total requests and error count"""
        try:
            # Get the latest values from both metrics
            total_value = self._extract_latest_value(total_data)
            error_value = self._extract_latest_value(error_data)

            if total_value is not None and error_value is not None and total_value > 0:
                success_rate = ((total_value - error_value) / total_value) * 100
                # Ensure it's between 0 and 100
                success_rate = max(0, min(100, success_rate))
                # Return in the same structure as metric query response
                return {
                    "result": [{
                        "data": [{
                            "values": [[success_rate]]
                        }]
                    }]
                }
            return total_data  # Fall back to total if can't calculate
        except Exception as e:
            print(f"Error calculating availability from errors: {e}")
            return total_data

    def _extract_latest_value(self, data: Dict[str, Any]) -> Optional[float]:
        """Extract the latest value from metric data"""
        try:
            if not isinstance(data, dict) or "result" not in data:
                return None

            results = data.get("result", [])
            if not results:
                return None

            result_item = results[0]

            # Try to extract from nested data structure
            if "data" in result_item and isinstance(result_item["data"], list) and result_item["data"]:
                data_item = result_item["data"][0]
                if "values" in data_item and isinstance(data_item["values"], list) and data_item["values"]:
                    values = data_item["values"]
                    last_value = values[-1]
                    if isinstance(last_value, list) and len(last_value) > 0:
                        return float(last_value[0]) if last_value[0] is not None else None

            # Try direct structure
            if "values" in result_item and isinstance(result_item["values"], list) and result_item["values"]:
                values = result_item["values"]
                last_value = values[-1]
                if isinstance(last_value, list) and len(last_value) > 0:
                    return float(last_value[0]) if last_value[0] is not None else None

            return None
        except Exception as e:
            print(f"Error extracting latest value: {e}")
            return None

    def extract_dimensions_from_metric_data(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract available dimensions and entity names from metric data"""
        try:
            dimensions = {}
            entity_names = set()

            results = metric_data.get("result", [])
            if not results:
                return {"dimensions": [], "entity_names": []}

            result_item = results[0]

            # Get data items - handle both nested and direct structures
            data_items = []
            if "data" in result_item and isinstance(result_item["data"], list):
                data_items = result_item["data"]
            else:
                data_items = [result_item]

            # Extract dimensions from each data item
            for data_item in data_items:
                if not isinstance(data_item, dict):
                    continue

                # Extract dimension information
                if "dimensions" in data_item and isinstance(data_item["dimensions"], list):
                    for dimension in data_item["dimensions"]:
                        if isinstance(dimension, str):
                            # Add dimension if not already present
                            if dimension not in dimensions:
                                dimensions[dimension] = set()

                # Extract dimension map if available
                if "dimensionMap" in data_item and isinstance(data_item["dimensionMap"], dict):
                    for dim_name, dim_values in data_item["dimensionMap"].items():
                        if dim_name not in dimensions:
                            dimensions[dim_name] = set()
                        if isinstance(dim_values, dict):
                            for key, value in dim_values.items():
                                if isinstance(value, str):
                                    dimensions[dim_name].add(value)
                                    entity_names.add(value)

            # Convert sets to sorted lists
            result_dimensions = []
            for dim_name, dim_values in dimensions.items():
                result_dimensions.append({
                    "name": dim_name,
                    "values": sorted(list(dim_values))
                })

            return {
                "dimensions": result_dimensions,
                "entity_names": sorted(list(entity_names))
            }
        except Exception as e:
            print(f"Error extracting dimensions: {e}")
            import traceback
            traceback.print_exc()
            return {"dimensions": [], "entity_names": []}
