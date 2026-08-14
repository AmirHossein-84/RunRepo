"""Unit tests for RepositoryManager cache listing, size calculation, and safe cleanup."""

from pathlib import Path
from runrepo.repository.manager import RepositoryManager


def test_list_cached_repositories(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    repo_a = cache_dir / "owner_repo-a"
    repo_a.mkdir()
    (repo_a / "README.md").write_text("Hello A", encoding="utf-8")
    (repo_a / ".git").mkdir()
    (repo_a / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    repo_b = cache_dir / "owner_repo-b"
    repo_b.mkdir()
    (repo_b / "file.txt").write_text("Hello B content 12345", encoding="utf-8")

    mgr = RepositoryManager(cache_dir=cache_dir)
    metadata = mgr.list_cached()

    assert metadata.total_repositories == 2
    assert metadata.total_size_bytes > 0
    assert len(metadata.repositories) == 2

    repo_names = [r.name for r in metadata.repositories]
    assert "owner_repo-a" in repo_names
    assert "owner_repo-b" in repo_names


def test_clean_cache_by_target(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    (cache_dir / "facebook_react").mkdir()
    (cache_dir / "vercel_next.js").mkdir()

    mgr = RepositoryManager(cache_dir=cache_dir)
    removed = mgr.clean_cache(target="facebook/react")

    assert "facebook_react" in removed
    assert not (cache_dir / "facebook_react").exists()
    assert (cache_dir / "vercel_next.js").exists()


def test_clean_cache_all(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    (cache_dir / "org_repo1").mkdir()
    (cache_dir / "org_repo2").mkdir()

    mgr = RepositoryManager(cache_dir=cache_dir)
    removed = mgr.clean_cache()

    assert len(removed) == 2
    assert not (cache_dir / "org_repo1").exists()
    assert not (cache_dir / "org_repo2").exists()
