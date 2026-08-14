"""Unit tests for ScanCache in-memory and mtime memoization."""

import json
from runrepo.core.cache import ScanCache


def test_scan_cache_json_mtime_invalidation(tmp_path):
    cache = ScanCache()
    target_json = tmp_path / "package.json"
    
    target_json.write_text(json.dumps({"name": "initial"}), encoding="utf-8")
    data1 = cache.read_json(target_json)
    assert data1["name"] == "initial"

    # Cached read
    data2 = cache.read_json(target_json)
    assert data2["name"] == "initial"

    # Modify file and verify cache invalidation
    target_json.write_text(json.dumps({"name": "updated"}), encoding="utf-8")
    data3 = cache.read_json(target_json)
    assert data3["name"] == "updated"


def test_scan_cache_clear(tmp_path):
    cache = ScanCache()
    target_json = tmp_path / "data.json"
    target_json.write_text(json.dumps({"key": "val"}), encoding="utf-8")

    cache.read_json(target_json)
    assert len(cache._json_cache) == 1

    cache.clear()
    assert len(cache._json_cache) == 0
