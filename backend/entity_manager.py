import os
import json
from typing import Dict, Optional


class EntityManager:
    """Manages entity ID to display name mappings"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.entities_file = os.path.join(data_dir, "entities.json")
        self.entities_cache = self._load_entities()

    def _load_entities(self) -> Dict[str, Dict]:
        """Load entities from file"""
        try:
            if os.path.exists(self.entities_file):
                with open(self.entities_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading entities: {e}")
        return {}

    def save_entities(self) -> None:
        """Save entities to file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.entities_file, "w") as f:
                json.dump(self.entities_cache, f, indent=2)
            print(f"Entities saved to {self.entities_file}")
        except Exception as e:
            print(f"Error saving entities: {e}")

    def add_entity(self, entity_id: str, display_name: str, entity_type: str = "") -> None:
        """Add or update entity mapping"""
        self.entities_cache[entity_id] = {
            "displayName": display_name,
            "type": entity_type,
        }

    def get_entity_name(self, entity_id: str) -> str:
        """Get entity display name by ID"""
        if entity_id in self.entities_cache:
            return self.entities_cache[entity_id]["displayName"]
        return entity_id

    def get_all_entities(self) -> Dict[str, Dict]:
        """Get all entities"""
        return self.entities_cache

    def clear_entities(self) -> None:
        """Clear all entities"""
        self.entities_cache = {}
        self.save_entities()
