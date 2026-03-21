from giae.analysis.cache import DiskCache


def test_cache_put_get(tmp_path):
    cache_file = tmp_path / "test_cache.db"
    cache = DiskCache(cache_file=cache_file)

    namespace = "test_ns"
    key = "test_key"
    data = {"result": "success", "hits": [1, 2, 3]}

    cache.put(namespace, key, data)
    retrieved = cache.get(namespace, key)

    assert retrieved == data


def test_cache_miss(tmp_path):
    cache_file = tmp_path / "test_cache.db"
    cache = DiskCache(cache_file=cache_file)

    assert cache.get("none", "none") is None


def test_cache_expiration(tmp_path):
    cache_file = tmp_path / "test_cache.db"
    # Set TTL to -1 to force immediate expiration
    cache = DiskCache(cache_file=cache_file, ttl_seconds=-1)

    cache.put("ns", "key", {"data": 1})
    assert cache.get("ns", "key") is None


def test_cache_clear(tmp_path):
    cache_file = tmp_path / "test_cache.db"
    cache = DiskCache(cache_file=cache_file)

    cache.put("ns1", "k1", 1)
    cache.put("ns2", "k2", 2)

    assert cache.clear("ns1") == 1
    assert cache.get("ns1", "k1") is None
    assert cache.get("ns2", "k2") == 2

    cache.clear()
    assert cache.get("ns2", "k2") is None


def test_cache_stats(tmp_path):
    cache_file = tmp_path / "test_cache.db"
    cache = DiskCache(cache_file=cache_file)

    cache.put("uniprot", "k1", 1)
    cache.put("uniprot", "k2", 2)
    cache.put("interpro", "k3", 3)

    stats = cache.stats()
    assert stats["uniprot"] == 2
    assert stats["interpro"] == 1
