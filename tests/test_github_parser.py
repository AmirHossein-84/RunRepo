"""Unit tests for GitHubUrlParser supporting HTTPS, SSH, shorthands, branches, and security checks."""

import pytest
from pathlib import Path
from runrepo.repository.github import GitHubUrlParser
from runrepo.repository.models import RepositorySource


def test_parse_local_path(tmp_path):
    target = GitHubUrlParser.parse(str(tmp_path))
    assert target.source == RepositorySource.LOCAL
    assert target.local_path == tmp_path.resolve()


def test_parse_relative_local_path():
    target = GitHubUrlParser.parse("./src/runrepo")
    assert target.source == RepositorySource.LOCAL


def test_parse_github_https_urls():
    # Standard URL
    t1 = GitHubUrlParser.parse("https://github.com/facebook/react")
    assert t1.source == RepositorySource.GITHUB_HTTPS
    assert t1.owner == "facebook"
    assert t1.name == "react"
    assert t1.clone_url == "https://github.com/facebook/react.git"
    assert t1.branch is None

    # .git extension
    t2 = GitHubUrlParser.parse("https://github.com/expressjs/express.git")
    assert t2.source == RepositorySource.GITHUB_HTTPS
    assert t2.owner == "expressjs"
    assert t2.name == "express"
    assert t2.clone_url == "https://github.com/expressjs/express.git"

    # Branch via tree
    t3 = GitHubUrlParser.parse("https://github.com/fastapi/fastapi/tree/master")
    assert t3.source == RepositorySource.GITHUB_HTTPS
    assert t3.owner == "fastapi"
    assert t3.name == "fastapi"
    assert t3.branch == "master"

    # Nested branch via tree
    t4 = GitHubUrlParser.parse("https://github.com/vercel/next.js/tree/canary/packages/next")
    assert t4.source == RepositorySource.GITHUB_HTTPS
    assert t4.owner == "vercel"
    assert t4.name == "next.js"
    assert t4.branch == "canary/packages/next"


def test_parse_github_shorthand():
    # Simple shorthand
    t1 = GitHubUrlParser.parse("pallets/flask")
    assert t1.source == RepositorySource.GITHUB_SHORTHAND
    assert t1.owner == "pallets"
    assert t1.name == "flask"
    assert t1.clone_url == "https://github.com/pallets/flask.git"
    assert t1.branch is None

    # Shorthand with branch
    t2 = GitHubUrlParser.parse("django/django#main")
    assert t2.source == RepositorySource.GITHUB_SHORTHAND
    assert t2.owner == "django"
    assert t2.name == "django"
    assert t2.branch == "main"


def test_parse_github_ssh_urls():
    t1 = GitHubUrlParser.parse("git@github.com:torvalds/linux.git")
    assert t1.source == RepositorySource.GITHUB_SSH
    assert t1.owner == "torvalds"
    assert t1.name == "linux"
    assert t1.clone_url == "https://github.com/torvalds/linux.git"


def test_parse_security_rejections():
    # Malicious path traversal
    with pytest.raises(ValueError, match="Invalid GitHub repository"):
        GitHubUrlParser.parse("facebook/../../etc/passwd")

    # Invalid characters / command injection
    with pytest.raises(ValueError, match="Unrecognized repository format|Invalid GitHub repository"):
        GitHubUrlParser.parse("owner;rm -rf /;repo")

    # Invalid branch characters
    with pytest.raises(ValueError, match="Invalid branch name"):
        GitHubUrlParser.parse("owner/repo#branch;bad_cmd")
