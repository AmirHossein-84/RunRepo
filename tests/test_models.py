"""Unit tests for RunRepo domain models and serialization."""

import json
from runrepo.models import (
    Confidence,
    DatabaseRequirement,
    DatabaseType,
    DependencyInfo,
    DetectionEvidence,
    DockerComposeService,
    DockerInfo,
    EnvVarCategory,
    EnvironmentVariable,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectInfo,
    ProjectScript,
    ProjectType,
    RuntimeInfo,
    SubprojectInfo,
)


def test_detection_evidence_model():
    ev = DetectionEvidence(
        source=".nvmrc",
        detail="22.14.0",
        confidence=Confidence.HIGH,
        path=".nvmrc",
    )
    assert ev.source == ".nvmrc"
    assert ev.detail == "22.14.0"
    assert ev.confidence == Confidence.HIGH
    assert ev.path == ".nvmrc"


def test_project_info_serialization():
    evidence = [
        DetectionEvidence(source="package.json", detail="engines.node: >=18", confidence=Confidence.HIGH)
    ]
    runtime = RuntimeInfo(name="node", version=">=18", evidence=evidence)
    pm = PackageManagerInfo(name="pnpm", lockfile="pnpm-lock.yaml", evidence=evidence)
    fw = FrameworkInfo(name="Next.js", category=FrameworkCategory.FULLSTACK, evidence=evidence)
    script = ProjectScript(name="dev", command="next dev", evidence=evidence)
    db = DatabaseRequirement(name=DatabaseType.POSTGRESQL, orm="prisma", evidence=evidence)
    env_var = EnvironmentVariable(
        name="DATABASE_URL",
        category=EnvVarCategory.DATABASE,
        is_required=True,
        evidence=evidence,
    )

    project = ProjectInfo(
        path="/test/repo",
        name="my-app",
        project_type=ProjectType.WEB_APPLICATION,
        languages=["JavaScript", "TypeScript"],
        runtimes=[runtime],
        package_managers=[pm],
        frameworks=[fw],
        scripts=[script],
        databases=[db],
        environment_variables=[env_var],
    )

    serialized = project.model_dump_json()
    data = json.loads(serialized)

    assert data["name"] == "my-app"
    assert data["project_type"] == "web_application"
    assert data["languages"] == ["JavaScript", "TypeScript"]
    assert len(data["runtimes"]) == 1
    assert data["runtimes"][0]["evidence"][0]["source"] == "package.json"
    assert data["databases"][0]["name"] == "postgresql"
    assert data["environment_variables"][0]["category"] == "database"


def test_subproject_preservation():
    sp = SubprojectInfo(
        name="web",
        path="apps/web",
        languages=["TypeScript"],
        runtimes=[RuntimeInfo(name="node", version="20")],
        frameworks=[FrameworkInfo(name="Next.js", category=FrameworkCategory.FULLSTACK)],
    )

    project = ProjectInfo(
        path="/repo",
        name="mono",
        is_monorepo=True,
        subprojects=[sp],
    )

    assert len(project.subprojects) == 1
    assert project.subprojects[0].path == "apps/web"
    assert project.subprojects[0].name == "web"
