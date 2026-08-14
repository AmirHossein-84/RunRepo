"""Parser and validator for GitHub URLs, shorthands, branches, and local paths."""

import os
import re
from pathlib import Path
from urllib.parse import urlparse
from runrepo.repository.models import RepositorySource, RepositoryTarget


class GitHubUrlParser:
    """Deterministic parser converting user input strings into structured RepositoryTarget models."""

    OWNER_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9_-]*[a-zA-Z0-9])?$")
    REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")
    BRANCH_PATTERN = re.compile(r"^[a-zA-Z0-9_./-]+$")

    @classmethod
    def is_local_path(cls, input_str: str) -> bool:
        """Determine if an input string refers to a local directory or file."""
        if not input_str or not input_str.strip():
            return True

        # Check relative prefixes
        if input_str.startswith((".", "/", "\\")) or (len(input_str) > 1 and input_str[1] == ":"):
            return True

        # Check if it directly exists on filesystem
        try:
            path = Path(input_str).resolve()
            if path.exists():
                return True
        except Exception:
            pass

        return False

    @classmethod
    def _validate_owner_repo(cls, owner: str, name: str) -> None:
        """Validate owner and repo name against malicious characters or path traversal."""
        if not cls.OWNER_PATTERN.match(owner):
            raise ValueError(f"Invalid GitHub repository owner name: '{owner}'")
        if not cls.REPO_NAME_PATTERN.match(name) or name in (".", "..") or ".." in name:
            raise ValueError(f"Invalid GitHub repository name: '{name}'")

    @classmethod
    def parse(cls, input_str: str) -> RepositoryTarget:
        """Parse an input string into a structured RepositoryTarget."""
        clean_input = input_str.strip()

        # 1. Local filesystem path
        if cls.is_local_path(clean_input):
            local_p = Path(clean_input).resolve()
            return RepositoryTarget(
                source=RepositorySource.LOCAL,
                raw_input=clean_input,
                name=local_p.name or "repository",
                local_path=local_p,
            )

        # 2. SSH URL (e.g. git@github.com:owner/repo.git)
        ssh_match = re.match(r"^git@github\.com:([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$", clean_input)
        if ssh_match:
            owner, name = ssh_match.group(1), ssh_match.group(2)
            cls._validate_owner_repo(owner, name)
            return RepositoryTarget(
                source=RepositorySource.GITHUB_SSH,
                raw_input=clean_input,
                owner=owner,
                name=name,
                clone_url=f"https://github.com/{owner}/{name}.git",
            )

        # 3. HTTP / HTTPS URL
        if clean_input.startswith(("https://github.com/", "http://github.com/", "github.com/")):
            url_str = clean_input if clean_input.startswith("http") else f"https://{clean_input}"
            parsed = urlparse(url_str)
            parts = [p for p in parsed.path.strip("/").split("/") if p]

            if len(parts) >= 2:
                owner = parts[0]
                name = parts[1]
                if name.endswith(".git"):
                    name = name[:-4]

                branch: str | None = None
                # Support /tree/<branch> or /blob/<branch>
                if len(parts) >= 4 and parts[2] in ("tree", "blob"):
                    branch = "/".join(parts[3:])

                cls._validate_owner_repo(owner, name)
                if branch and not cls.BRANCH_PATTERN.match(branch):
                    raise ValueError(f"Invalid branch name: '{branch}'")

                return RepositoryTarget(
                    source=RepositorySource.GITHUB_HTTPS,
                    raw_input=clean_input,
                    owner=owner,
                    name=name,
                    branch=branch,
                    clone_url=f"https://github.com/{owner}/{name}.git",
                )
            raise ValueError(f"Malformed GitHub URL: '{clean_input}'. Expected 'https://github.com/owner/repo'.")

        # 4. Shorthand (e.g. owner/repo or owner/repo#branch)
        if "/" in clean_input and not clean_input.startswith(("http://", "https://", "git@")):
            branch = None
            if "#" in clean_input:
                repo_part, branch = clean_input.split("#", 1)
            else:
                repo_part = clean_input

            parts = repo_part.strip().split("/")
            if len(parts) == 2:
                owner, name = parts[0].strip(), parts[1].strip()
                if name.endswith(".git"):
                    name = name[:-4]

                cls._validate_owner_repo(owner, name)
                if branch and not cls.BRANCH_PATTERN.match(branch):
                    raise ValueError(f"Invalid branch name: '{branch}'")

                return RepositoryTarget(
                    source=RepositorySource.GITHUB_SHORTHAND,
                    raw_input=clean_input,
                    owner=owner,
                    name=name,
                    branch=branch,
                    clone_url=f"https://github.com/{owner}/{name}.git",
                )
            raise ValueError(f"Invalid GitHub repository reference: '{clean_input}'. Expected 'owner/repo'.")

        raise ValueError(
            f"Unrecognized repository format: '{clean_input}'. "
            f"Provide a local directory path, GitHub URL, or 'owner/repo' shorthand."
        )
