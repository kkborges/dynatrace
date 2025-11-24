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
            max_pages = 20  # Limit pages to prevent excessive API calls
            start_time = time_module.time()
            max_duration = 120  # 2 minute timeout
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

                print(f"Fetching page {page_count + 1}...")
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

                # If we got no builtin metrics this page, stop (means we've moved beyond builtin metrics)
                if not page_metrics:
                    print(f"No builtin metrics found in page {page_count + 1}. Stopping pagination.")
                    break

                all_metrics.extend(page_metrics)
                page_count += 1

                elapsed = time_module.time() - start_time
                print(f"Page {page_count}: Found {len(page_metrics)} new builtin metrics, total: {len(all_metrics)} ({elapsed:.1f}s)")

                # Check if there are more pages
                next_page_key = data.get("nextPageKey")
                if not next_page_key:
                    print(f"Pagination complete. No nextPageKey after {page_count} pages.")
                    break

            print(f"Metrics fetch complete: {len(all_metrics)} unique builtin metrics in {page_count} pages, {time_module.time() - start_time:.1f}s total")

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
                        print(f"  Result[0].data type: {type(data['result'][0]['data'])}, length: {len(data['result'][0]['data']) if isinstance(data['result'][0]['data'], list) else 'N/A'}")

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
        """Get application availability metrics (success rate)"""
        try:
            # If no time range provided, use last hour
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            # Try to get success rate metric first (best indicator of availability)
            # If not available, fall back to server errors (inverse indicator)
            print("Fetching application availability...")
            try:
                # Fetch successful requests
                successful_data = self.get_metric_data(
                    "builtin:app.web.httpRequests.successful",
                    start_timestamp,
                    end_timestamp,
                    "1m"
                )

                # Fetch overall requests
                overall_data = self.get_metric_data(
                    "builtin:app.web.httpRequests.overall",
                    start_timestamp,
                    end_timestamp,
                    "1m"
                )

                # Calculate success rate as percentage
                return self._calculate_success_rate(successful_data, overall_data)
            except:
                # Fall back to just overall requests if success metric not available
                print("Couldn't calculate success rate, using overall requests as fallback")
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
        """Get service availability metrics (success rate)"""
        try:
            # If no time range provided, use last hour
            if start_timestamp is None or end_timestamp is None:
                import time
                now = int(time.time() * 1000)
                start_timestamp = now - (60 * 60 * 1000)  # Last hour
                end_timestamp = now

            # Try to calculate availability from error rate
            print("Fetching service availability...")
            try:
                # Fetch total requests
                total_data = self.get_metric_data(
                    "builtin:service.requestCount.total",
                    start_timestamp,
                    end_timestamp,
                    "1m"
                )

                # Fetch error count
                error_data = self.get_metric_data(
                    "builtin:service.errorCount.total",
                    start_timestamp,
                    end_timestamp,
                    "1m"
                )

                # Calculate success rate from error count
                return self._calculate_availability_from_errors(total_data, error_data)
            except:
                # Fall back to just request count if error metric not available
                print("Couldn't calculate from errors, using request count as fallback")
                return self.get_metric_data(
                    "builtin:service.requestCount.total",
                    start_timestamp,
                    end_timestamp,
                    "1m"
                )
        except Exception as e:
            print(f"Error fetching service availability: {e}")
            return {}

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
