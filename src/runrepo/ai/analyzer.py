"""AI-powered repository analyzer for resolving README and setup ambiguity."""

from pathlib import Path
from runrepo.ai.gemini import GeminiClient
from runrepo.ai.models import AIAnalysisResult
from runrepo.ai.prompts import (
    REPOSITORY_ANALYSIS_SYSTEM_PROMPT,
    build_repository_analysis_prompt,
)
from runrepo.ai.validator import AIResponseValidator
from runrepo.models import (
    AnalysisWarning,
    Confidence,
    DetectionEvidence,
    EnvironmentVariable,
    EnvVarCategory,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectInfo,
    ProjectScript,
    ProjectType,
)


class AIRepositoryAnalyzer:
    """Enriches ambiguous ProjectInfo using validated Gemini analysis while respecting deterministic precedence."""

    def __init__(self, client: GeminiClient | None = None) -> None:
        self.client = client or GeminiClient()

    def find_readme_content(self, repo_path: Path) -> str | None:
        """Find and read top-level README text."""
        for name in ("README.md", "README.txt", "readme.md", "README", "README.rst"):
            p = repo_path / name
            if p.exists() and p.is_file():
                try:
                    return p.read_text(encoding="utf-8", errors="replace")[:6000]
                except Exception:
                    pass
        return None

    def get_file_tree(self, repo_path: Path, max_files: int = 100) -> list[str]:
        """Collect top-level directory entries ignoring build and version control directories."""
        entries: list[str] = []
        ignored = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", ".idea", ".vscode"}
        try:
            for item in sorted(repo_path.iterdir()):
                if item.name in ignored:
                    continue
                rel = item.relative_to(repo_path)
                if item.is_dir():
                    entries.append(f"{rel}/")
                else:
                    entries.append(str(rel))
                if len(entries) >= max_files:
                    break
        except Exception:
            pass
        return entries

    def analyze_ambiguity(self, repo_path: Path, project_info: ProjectInfo) -> ProjectInfo:
        """Analyze repository ambiguity using Gemini if client is available."""
        if not self.client.is_available():
            return project_info

        readme_text = self.find_readme_content(repo_path)
        file_tree = self.get_file_tree(repo_path)

        # Build prompt
        pm_names = [pm.name for pm in project_info.package_managers]
        fw_names = [fw.name for fw in project_info.frameworks]
        deterministic_summary = {
            "project_type": project_info.project_type.value,
            "frameworks": fw_names,
            "package_managers": pm_names,
            "scripts_count": len(project_info.scripts),
        }

        prompt = build_repository_analysis_prompt(
            repo_name=project_info.name,
            file_tree=file_tree,
            readme_content=readme_text,
            deterministic_facts=deterministic_summary,
        )

        try:
            raw_response = self.client.generate(
                prompt,
                system_instruction=REPOSITORY_ANALYSIS_SYSTEM_PROMPT,
            )
            ai_result = AIResponseValidator.parse_analysis_result(raw_response)
        except Exception as e:
            project_info.warnings.append(
                AnalysisWarning(
                    file_path="README.md",
                    message=f"AI ambiguity analysis skipped/failed: {e}",
                    code="AI_ANALYSIS_ERROR",
                )
            )
            return project_info

        return self.merge_ai_results(project_info, ai_result)

    @classmethod
    def merge_ai_results(cls, project_info: ProjectInfo, ai_result: AIAnalysisResult) -> ProjectInfo:
        """Merge validated AI facts into ProjectInfo preserving deterministic precedence."""
        # 1. Project Type (only if previously UNKNOWN)
        if project_info.project_type == ProjectType.UNKNOWN and ai_result.detected_project_type:
            try:
                matched_type = ProjectType(ai_result.detected_project_type.lower())
                project_info.project_type = matched_type
                project_info.evidence.append(
                    DetectionEvidence(
                        source="README.md (AI-assisted)",
                        confidence=Confidence.LOW,
                        details=f"AI identified project type: {matched_type.value}",
                    )
                )
            except ValueError:
                pass

        # 2. Framework (only if previously missing)
        if not project_info.frameworks and ai_result.detected_framework:
            project_info.frameworks.append(
                FrameworkInfo(
                    name=ai_result.detected_framework,
                    category=FrameworkCategory.OTHER,
                    evidence=[
                        DetectionEvidence(
                            source="README.md (AI-assisted)",
                            confidence=Confidence.LOW,
                            details=f"AI identified framework: {ai_result.detected_framework}",
                        )
                    ],
                )
            )

        # 3. Package Manager (only if previously missing)
        if not project_info.package_managers and ai_result.detected_package_manager:
            pm_name = ai_result.detected_package_manager.lower()
            project_info.package_managers.append(
                PackageManagerInfo(
                    name=pm_name,
                    evidence=[
                        DetectionEvidence(
                            source="README.md (AI-assisted)",
                            confidence=Confidence.LOW,
                            details=f"AI identified package manager: {pm_name}",
                        )
                    ],
                )
            )
        elif project_info.package_managers and ai_result.detected_package_manager:
            # Check for conflict
            ai_pm = ai_result.detected_package_manager.lower()
            det_pms = [pm.name.lower() for pm in project_info.package_managers]
            if ai_pm not in det_pms:
                project_info.warnings.append(
                    AnalysisWarning(
                        file_path="README.md",
                        message=(
                            f"AI suggested package manager '{ai_pm}', but deterministic analysis confirmed "
                            f"{det_pms}. Deterministic fact preserved."
                        ),
                        code="AI_CONFLICT_IGNORED",
                    )
                )

        # 4. Startup Script (only if previously empty)
        if not project_info.scripts and ai_result.suggested_startup_command:
            cmd_str = " ".join(ai_result.suggested_startup_command)
            project_info.scripts.append(
                ProjectScript(
                    name="dev",
                    command=cmd_str,
                    description="AI-extracted startup command from README",
                    evidence=[
                        DetectionEvidence(
                            source="README.md (AI-assisted)",
                            confidence=Confidence.LOW,
                            details="AI extracted startup command",
                        )
                    ],
                )
            )

        # 5. Environment Variables
        existing_var_names = {v.name for v in project_info.environment_variables}
        for env_name in ai_result.detected_environment_variables:
            if env_name not in existing_var_names:
                project_info.environment_variables.append(
                    EnvironmentVariable(
                        name=env_name,
                        default_value=None,
                        is_required=False,
                        category=EnvVarCategory.LOCAL_DEFAULT,
                        evidence=[
                            DetectionEvidence(
                                source="README.md (AI-assisted)",
                                confidence=Confidence.LOW,
                                details="AI identified environment variable in documentation",
                            )
                        ],
                    )
                )
                existing_var_names.add(env_name)

        if ai_result.reasoning_summary:
            project_info.warnings.append(
                AnalysisWarning(
                    file_path="README.md",
                    message=f"AI Analysis Note: {ai_result.reasoning_summary}",
                    code="AI_ANALYSIS_NOTE",
                )
            )

        return project_info
