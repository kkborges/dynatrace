import json
import os
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from backend.models import SavedDashboard, DashboardMetric


class DashboardManager:
    """Manages saved dashboards stored as JSON files"""

    def __init__(self):
        self.data_dir = "data"
        self.dashboards_file = os.path.join(self.data_dir, "dashboards.json")
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _load_dashboards(self) -> Dict[str, dict]:
        """Load all dashboards from JSON file"""
        try:
            if os.path.exists(self.dashboards_file):
                with open(self.dashboards_file, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading dashboards: {e}")
            return {}

    def _save_dashboards(self, dashboards: Dict[str, dict]):
        """Save dashboards to JSON file"""
        try:
            with open(self.dashboards_file, "w") as f:
                json.dump(dashboards, f, indent=2, default=str)
            print(f"Dashboards saved to {self.dashboards_file}")
        except Exception as e:
            print(f"Error saving dashboards: {e}")
            raise

    def create_dashboard(self, name: str, description: Optional[str], metrics: List[DashboardMetric]) -> SavedDashboard:
        """Create and save a new dashboard"""
        try:
            dashboard_id = str(uuid.uuid4())
            now = datetime.now()

            dashboard = SavedDashboard(
                id=dashboard_id,
                name=name,
                description=description,
                metrics=metrics,
                created_at=now,
                updated_at=now,
            )

            dashboards = self._load_dashboards()
            dashboards[dashboard_id] = json.loads(dashboard.model_dump_json(default=str))

            self._save_dashboards(dashboards)
            print(f"Dashboard '{name}' created with ID: {dashboard_id}")
            return dashboard
        except Exception as e:
            print(f"Error creating dashboard: {e}")
            raise

    def update_dashboard(self, dashboard_id: str, name: str, description: Optional[str], metrics: List[DashboardMetric]) -> SavedDashboard:
        """Update an existing dashboard"""
        try:
            dashboards = self._load_dashboards()

            if dashboard_id not in dashboards:
                raise ValueError(f"Dashboard with ID '{dashboard_id}' not found")

            now = datetime.now()
            dashboard = SavedDashboard(
                id=dashboard_id,
                name=name,
                description=description,
                metrics=metrics,
                created_at=dashboards[dashboard_id].get("created_at"),
                updated_at=now,
            )

            dashboards[dashboard_id] = json.loads(dashboard.model_dump_json(default=str))
            self._save_dashboards(dashboards)
            print(f"Dashboard '{name}' (ID: {dashboard_id}) updated")
            return dashboard
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            raise

    def get_dashboard(self, dashboard_id: str) -> Optional[SavedDashboard]:
        """Get a specific dashboard by ID"""
        try:
            dashboards = self._load_dashboards()
            if dashboard_id in dashboards:
                dashboard_data = dashboards[dashboard_id]
                return SavedDashboard(**dashboard_data)
            return None
        except Exception as e:
            print(f"Error getting dashboard: {e}")
            return None

    def list_dashboards(self) -> List[SavedDashboard]:
        """List all saved dashboards"""
        try:
            dashboards = self._load_dashboards()
            result = []
            for dashboard_data in dashboards.values():
                try:
                    dashboard = SavedDashboard(**dashboard_data)
                    result.append(dashboard)
                except Exception as e:
                    print(f"Error parsing dashboard: {e}")
                    continue
            return result
        except Exception as e:
            print(f"Error listing dashboards: {e}")
            return []

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard by ID"""
        try:
            dashboards = self._load_dashboards()
            if dashboard_id in dashboards:
                del dashboards[dashboard_id]
                self._save_dashboards(dashboards)
                print(f"Dashboard (ID: {dashboard_id}) deleted")
                return True
            return False
        except Exception as e:
            print(f"Error deleting dashboard: {e}")
            raise

    def export_dashboard(self, dashboard_id: str) -> Optional[str]:
        """Export dashboard as JSON string for download"""
        try:
            dashboard = self.get_dashboard(dashboard_id)
            if not dashboard:
                return None
            return dashboard.model_dump_json(indent=2, default=str)
        except Exception as e:
            print(f"Error exporting dashboard: {e}")
            return None

    def import_dashboard(self, dashboard_json: str, override_id: bool = False) -> SavedDashboard:
        """Import dashboard from JSON string"""
        try:
            data = json.loads(dashboard_json)

            # If override_id is True, generate a new ID
            if override_id or not data.get("id"):
                data["id"] = str(uuid.uuid4())

            dashboard = SavedDashboard(**data)

            dashboards = self._load_dashboards()
            dashboards[dashboard.id] = json.loads(dashboard.model_dump_json(default=str))
            self._save_dashboards(dashboards)

            print(f"Dashboard imported with ID: {dashboard.id}")
            return dashboard
        except Exception as e:
            print(f"Error importing dashboard: {e}")
            raise
