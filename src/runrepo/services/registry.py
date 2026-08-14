"""Infrastructure registry tracking RunRepo-owned Docker containers, volumes, and networks."""

import json
from pathlib import Path
import platformdirs
from runrepo.services.models import OwnedResource, ResourceType, ServiceType


class InfrastructureRegistry:
    """Persistent user-level storage tracking infrastructure resources created by RunRepo."""

    def __init__(self, state_dir: Path | None = None) -> None:
        if state_dir is not None:
            self.state_dir = Path(state_dir)
        else:
            base_dir = Path(platformdirs.user_data_dir("runrepo", appauthor=False))
            self.state_dir = base_dir / "infrastructure"

        self.registry_file = self.state_dir / "registry.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self) -> list[dict]:
        if not self.registry_file.exists():
            return []
        try:
            content = self.registry_file.read_text(encoding="utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            # Handle corrupt registry file gracefully by falling back to empty list
            return []

    def _save_data(self, data: list[dict]) -> None:
        self._ensure_dir()
        try:
            self.registry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def register_resource(self, resource: OwnedResource) -> None:
        """Register a newly created RunRepo-owned resource."""
        data = self._load_data()
        # Remove existing if same ID or name
        filtered = [item for item in data if item.get("id") != resource.id and item.get("name") != resource.name]
        filtered.append(resource.model_dump())
        self._save_data(filtered)

    def unregister_resource(self, resource_id_or_name: str) -> None:
        """Unregister a resource after cleanup."""
        data = self._load_data()
        filtered = [
            item
            for item in data
            if item.get("id") != resource_id_or_name and item.get("name") != resource_id_or_name
        ]
        self._save_data(filtered)

    def list_resources(
        self,
        repo_path: str | Path | None = None,
        resource_type: ResourceType | None = None,
        service_type: ServiceType | None = None,
    ) -> list[OwnedResource]:
        """List tracked resources with optional repository path or type filters."""
        data = self._load_data()
        resources: list[OwnedResource] = []
        normalized_repo_path = str(Path(repo_path).resolve()) if repo_path else None

        for item in data:
            try:
                res = OwnedResource.model_validate(item)
                if normalized_repo_path and str(Path(res.project_path).resolve()) != normalized_repo_path:
                    continue
                if resource_type and res.resource_type != resource_type:
                    continue
                if service_type and res.service_type != service_type:
                    continue
                resources.append(res)
            except Exception:
                continue

        return resources

    def get_resource(self, resource_id_or_name: str) -> OwnedResource | None:
        """Retrieve a specific resource by container ID or name."""
        data = self._load_data()
        for item in data:
            if item.get("id") == resource_id_or_name or item.get("name") == resource_id_or_name:
                try:
                    return OwnedResource.model_validate(item)
                except Exception:
                    pass
        return None
