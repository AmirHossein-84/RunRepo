"""Resolver converting MonorepoInfo into structured SubprojectInfo representations."""

from pathlib import Path
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectScript,
    RuntimeInfo,
    SubprojectInfo,
)
from runrepo.monorepo.models import MonorepoInfo, WorkspacePackage


class MonorepoResolver:
    """Transforms discovered monorepo workspace packages into SubprojectInfo domain models."""

    @classmethod
    def resolve_subprojects(cls, monorepo_info: MonorepoInfo, root_pm: str | None = None) -> list[SubprojectInfo]:
        """Convert discovered workspace packages into structured SubprojectInfo list."""
        subprojects: list[SubprojectInfo] = []

        for pkg in monorepo_info.packages:
            scripts: list[ProjectScript] = []
            for name, cmd in pkg.scripts.items():
                scripts.append(
                    ProjectScript(
                        name=name,
                        command=cmd,
                        evidence=[
                            DetectionEvidence(
                                source=f"{pkg.path}/package.json",
                                confidence=Confidence.HIGH,
                                details=f"Script '{name}' defined in workspace package",
                            )
                        ],
                    )
                )

            frameworks: list[FrameworkInfo] = []
            if pkg.framework:
                frameworks.append(
                    FrameworkInfo(
                        name=pkg.framework,
                        category=FrameworkCategory.FULLSTACK if pkg.framework == "Next.js" else FrameworkCategory.OTHER,
                        evidence=[
                            DetectionEvidence(
                                source=f"{pkg.path}/package.json",
                                confidence=Confidence.HIGH,
                                details=f"Framework {pkg.framework} detected in package dependencies",
                            )
                        ],
                    )
                )

            runtimes: list[RuntimeInfo] = [
                RuntimeInfo(
                    name="node",
                    evidence=[
                        DetectionEvidence(
                            source=f"{pkg.path}/package.json",
                            confidence=Confidence.HIGH,
                        )
                    ],
                )
            ]

            pms: list[PackageManagerInfo] = []
            if root_pm:
                pms.append(PackageManagerInfo(name=root_pm))

            subprojects.append(
                SubprojectInfo(
                    name=pkg.name,
                    path=pkg.path,
                    languages=["javascript", "typescript"] if pkg.scripts or pkg.dependencies else [],
                    runtimes=runtimes,
                    package_managers=pms,
                    frameworks=frameworks,
                    scripts=scripts,
                    evidence=[
                        DetectionEvidence(
                            source=f"{pkg.path}",
                            confidence=Confidence.HIGH,
                            details=f"Workspace package detected ({monorepo_info.workspace_type.value})",
                        )
                    ],
                )
            )

        return subprojects
