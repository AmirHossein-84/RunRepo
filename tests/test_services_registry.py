"""Unit tests for InfrastructureRegistry tracking and corruption resilience."""

from runrepo.services.models import OwnedResource, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


def test_registry_register_and_list(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path)
    res = OwnedResource(
        resource_type=ResourceType.CONTAINER,
        id="c1",
        name="test-pg",
        service_type=ServiceType.POSTGRES,
        project_path=str(tmp_path / "repo1"),
        ports=[5432],
    )

    reg.register_resource(res)
    listed = reg.list_resources(repo_path=tmp_path / "repo1")
    assert len(listed) == 1
    assert listed[0].name == "test-pg"

    # Filter by different repo returns empty
    other = reg.list_resources(repo_path=tmp_path / "other")
    assert len(other) == 0


def test_registry_unregister(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path)
    res = OwnedResource(
        resource_type=ResourceType.CONTAINER,
        id="c1",
        name="test-pg",
        service_type=ServiceType.POSTGRES,
        project_path=str(tmp_path / "repo1"),
    )

    reg.register_resource(res)
    assert len(reg.list_resources()) == 1

    reg.unregister_resource("c1")
    assert len(reg.list_resources()) == 0


def test_registry_corrupted_file_recovery(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path)
    # Write invalid JSON content
    (tmp_path / "registry.json").write_text("{corrupt json", encoding="utf-8")

    # Should not crash; gracefully returns empty list
    listed = reg.list_resources()
    assert listed == []

    # Can safely register new items
    res = OwnedResource(
        resource_type=ResourceType.CONTAINER,
        id="c2",
        name="test-redis",
        service_type=ServiceType.REDIS,
        project_path=str(tmp_path),
    )
    reg.register_resource(res)
    assert len(reg.list_resources()) == 1
