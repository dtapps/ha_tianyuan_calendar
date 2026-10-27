"""缓存服务测试：命中/过期/并发单飞/LRU 淘汰/异常不落缓存。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from custom_components.tianyuan_calendar_duo import cache_service as 缓存模块
from custom_components.tianyuan_calendar_duo.cache_service import CacheService


async def test_同键重复调用只构建一次() -> None:
    调用次数 = 0

    def 构建器() -> str:
        nonlocal 调用次数
        调用次数 += 1
        return "值"

    服务 = CacheService()
    assert await 服务.get_or_set("k", 构建器) == "值"
    assert await 服务.get_or_set("k", 构建器) == "值"
    assert 调用次数 == 1


async def test_不同键各自构建() -> None:
    服务 = CacheService()
    assert await 服务.get_or_set("a", lambda: 1) == 1
    assert await 服务.get_or_set("b", lambda: 2) == 2
    assert len(服务._cache) == 2


async def test_支持异步构建器() -> None:
    async def 构建器() -> str:
        await asyncio.sleep(0)
        return "异步值"

    服务 = CacheService()
    assert await 服务.get_or_set("k", 构建器) == "异步值"
    assert await 服务.get_or_set("k", 构建器) == "异步值"


async def test_过期后重新构建(monkeypatch: pytest.MonkeyPatch) -> None:
    时钟 = [1000.0]
    monkeypatch.setattr(缓存模块.time, "time", lambda: 时钟[0])
    调用次数 = 0

    def 构建器() -> str:
        nonlocal 调用次数
        调用次数 += 1
        return f"第{调用次数}次"

    服务 = CacheService()
    assert await 服务.get_or_set("k", 构建器, ttl=10) == "第1次"

    时钟[0] += 5  # 未过期
    assert await 服务.get_or_set("k", 构建器, ttl=10) == "第1次"

    时钟[0] += 100  # 过期
    assert await 服务.get_or_set("k", 构建器, ttl=10) == "第2次"
    assert 调用次数 == 2


async def test_None默认也会缓存() -> None:
    调用次数 = 0

    def 构建器() -> None:
        nonlocal 调用次数
        调用次数 += 1
        return None

    服务 = CacheService()
    assert await 服务.get_or_set("k", 构建器) is None
    assert await 服务.get_or_set("k", 构建器) is None
    assert 调用次数 == 1


async def test_cache_none为假时不缓存None() -> None:
    调用次数 = 0

    def 构建器() -> None:
        nonlocal 调用次数
        调用次数 += 1
        return None

    服务 = CacheService()
    assert await 服务.get_or_set("k", 构建器, cache_none=False) is None
    assert await 服务.get_or_set("k", 构建器, cache_none=False) is None
    assert 调用次数 == 2
    assert "k" not in 服务._cache


async def test_构建器抛异常时向上传播且不落缓存() -> None:
    def 构建器() -> str:
        raise RuntimeError("构建失败")

    服务 = CacheService()
    with pytest.raises(RuntimeError, match="构建失败"):
        await 服务.get_or_set("k", 构建器)

    assert "k" not in 服务._cache
    # 再次调用仍会重新构建（未污染缓存）
    with pytest.raises(RuntimeError):
        await 服务.get_or_set("k", 构建器)


async def test_并发同键只构建一次() -> None:
    调用次数 = 0

    async def 构建器() -> str:
        nonlocal 调用次数
        调用次数 += 1
        await asyncio.sleep(0.01)
        return "并发值"

    服务 = CacheService()
    结果 = await asyncio.gather(*[服务.get_or_set("k", 构建器) for _ in range(5)])

    assert 结果 == ["并发值"] * 5
    assert 调用次数 == 1


async def test_锁在调用结束后被清理() -> None:
    服务 = CacheService()
    await 服务.get_or_set("k", lambda: 1)
    assert "k" not in 服务._locks


async def test_超出容量按LRU淘汰最旧项() -> None:
    服务 = CacheService(capacity=2)
    await 服务.get_or_set("a", lambda: 1)
    await 服务.get_or_set("b", lambda: 2)
    await 服务.get_or_set("a", lambda: 1)  # 命中并把 a 移到队尾
    await 服务.get_or_set("c", lambda: 3)

    assert set(服务._cache) == {"a", "c"}


async def test_淘汰时优先清掉已过期项(monkeypatch: pytest.MonkeyPatch) -> None:
    时钟 = [1000.0]
    monkeypatch.setattr(缓存模块.time, "time", lambda: 时钟[0])
    服务 = CacheService(capacity=2)

    await 服务.get_or_set("短期", lambda: "旧", ttl=1)
    时钟[0] += 10
    await 服务.get_or_set("长期", lambda: "新", ttl=1000)
    await 服务.get_or_set("第三个", lambda: "再新", ttl=1000)

    assert "短期" not in 服务._cache
    assert set(服务._cache) == {"长期", "第三个"}


async def test_invalidate与clear() -> None:
    服务 = CacheService()
    await 服务.get_or_set("a", lambda: 1)
    await 服务.get_or_set("b", lambda: 2)

    服务.invalidate("a")
    assert set(服务._cache) == {"b"}
    服务.invalidate("不存在的键")  # 不抛异常

    服务.clear()
    assert 服务._cache == {}
    assert 服务._locks == {}


async def test_命中时会更新LRU顺序() -> None:
    服务 = CacheService(capacity=2)
    await 服务.get_or_set("a", lambda: 1)
    await 服务.get_or_set("b", lambda: 2)
    await 服务.get_or_set("a", lambda: 1)

    assert list(服务._cache) == ["b", "a"]


async def test_构建值可以是任意对象() -> None:
    值: Any = {"嵌套": [1, 2, 3]}
    服务 = CacheService()
    assert await 服务.get_or_set("k", lambda: 值) is 值
