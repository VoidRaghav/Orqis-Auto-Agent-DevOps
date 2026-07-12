"""Tests for Redis SCAN helper."""

from __future__ import annotations

import asyncio

from orqis.backend import store


def test_scan_keys_uses_scan_not_keys(monkeypatch):
    calls: list[tuple] = []

    class FakeRedis:
        async def scan(self, cursor=0, match=None, count=100):
            calls.append((cursor, match, count))
            if cursor == 0:
                return 0, ["orqis:install:1", "orqis:install:2"]
            return 0, []

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(store, "get_redis", fake_get_redis)
    keys = asyncio.run(store.scan_keys("orqis:install:*"))
    assert keys == ["orqis:install:1", "orqis:install:2"]
    assert calls
    assert calls[0][1] == "orqis:install:*"
