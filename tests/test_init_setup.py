"""集成入口测试：真实 setup/unload、设备按需创建与清理、卡片资源注册、私有实体回收。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.tianyuan_calendar_duo import _cleanup_private_entities
from custom_components.tianyuan_calendar_duo.const import (
    CONF_CUSTOM_LATITUDE,
    CONF_CUSTOM_LONGITUDE,
    CONF_ENABLE_CARD,
    CONF_ENABLE_QIHUANG,
    CONF_ENABLE_SHUSHU,
    CONF_REFRESH_INTERVAL,
    DOMAIN,
    QIHUANG_PRIVATE_KEYS,
    SHUSHU_PRIVATE_KEYS,
)

输入 = {
    CONF_CUSTOM_LATITUDE: 39.9,
    CONF_CUSTOM_LONGITUDE: 116.4,
    CONF_REFRESH_INTERVAL: 1,
}


async def _建条目(hass: HomeAssistant, **覆盖选项):
    流程 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    创建 = await hass.config_entries.flow.async_configure(流程["flow_id"], dict(输入))
    entry = 创建["result"]
    if 覆盖选项:
        hass.config_entries.async_update_entry(
            entry, options={**dict(entry.options), **覆盖选项}
        )
    await hass.async_block_till_done()
    return entry


def _设备标识(hass: HomeAssistant, entry) -> set[str]:
    """返回该条目下所有设备的标识后缀（主设备为空串）。"""
    reg = dr.async_get(hass)
    结果 = set()
    for device in dr.async_entries_for_config_entry(reg, entry.entry_id):
        for domain, ident in device.identifiers:
            if domain == DOMAIN and ident == entry.entry_id:
                结果.add("")
            elif domain == DOMAIN and ident.startswith(f"{entry.entry_id}_"):
                结果.add(ident.split("_", 1)[1])
    return 结果


def _前端URL(hass: HomeAssistant) -> frozenset[str]:
    return frozenset(hass.data[DATA_EXTRA_MODULE_URL].urls)


async def test_建条目后自动完成setup(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)

    assert entry.state is not None
    assert entry.state.name == "LOADED"
    assert entry.runtime_data is not None
    assert entry.runtime_data.version  # 来自 manifest


async def test_默认只注册主设备(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)

    assert _设备标识(hass, entry) == {""}


async def test_开启子功能注册子设备(hass: HomeAssistant) -> None:
    entry = await _建条目(hass, **{CONF_ENABLE_QIHUANG: True, CONF_ENABLE_SHUSHU: True})

    assert _设备标识(hass, entry) == {"", "qihuang", "shushu"}


async def test_关闭子功能会移除子设备(hass: HomeAssistant) -> None:
    """先开后关：重新加载后子设备必须被清理，不留僵尸设备。"""
    entry = await _建条目(hass, **{CONF_ENABLE_QIHUANG: True, CONF_ENABLE_SHUSHU: True})
    assert len(_设备标识(hass, entry)) == 3

    hass.config_entries.async_update_entry(
        entry,
        options={
            **dict(entry.options),
            CONF_ENABLE_QIHUANG: False,
            CONF_ENABLE_SHUSHU: False,
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _设备标识(hass, entry) == {""}


async def test_卡片开关开启时注册静态资源与JS(hass: HomeAssistant) -> None:
    卡片目录 = Path(hass.config.path("custom_components", DOMAIN, "www"))
    卡片目录.mkdir(parents=True, exist_ok=True)
    (卡片目录 / "tianyuan-lunar-card.js").write_text("// card", encoding="utf-8")

    entry = await _建条目(hass, **{CONF_ENABLE_CARD: True})

    assert hass.data[f"{DOMAIN}_assets"] is True
    urls = _前端URL(hass)
    assert any("tianyuan-lunar-card.js" in u for u in urls)
    assert entry.state.name == "LOADED"


async def test_卡片开关关闭时不注册JS(hass: HomeAssistant) -> None:
    await _建条目(hass)

    assert f"{DOMAIN}_assets" not in hass.data
    assert not any("tianyuan-lunar-card" in u for u in _前端URL(hass))


async def test_卡片目录不存在时只落标记(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """www 目录缺失时不注册静态路径，但仍打标记避免反复检查。"""
    monkeypatch.setattr(
        "custom_components.tianyuan_calendar_duo.os",
        SimpleNamespace(path=SimpleNamespace(exists=lambda _p: False)),
    )

    await _建条目(hass, **{CONF_ENABLE_CARD: True})

    assert hass.data[f"{DOMAIN}_assets"] is True
    assert not any("tianyuan-lunar-card" in u for u in _前端URL(hass))


async def test_第二个条目不会重复注册静态路径(hass: HomeAssistant) -> None:
    卡片目录 = Path(hass.config.path("custom_components", DOMAIN, "www"))
    卡片目录.mkdir(parents=True, exist_ok=True)

    await _建条目(hass, **{CONF_ENABLE_CARD: True})
    首次 = _前端URL(hass)
    await _建条目(hass, **{CONF_ENABLE_CARD: True})

    assert _前端URL(hass) == 首次


async def test_无权限时回收岐黄与术数私有实体(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)
    reg = er.async_get(hass)
    岐黄键 = next(iter(QIHUANG_PRIVATE_KEYS))
    术数键 = next(iter(SHUSHU_PRIVATE_KEYS))

    岐黄实体 = reg.async_get_or_create(
        "select", DOMAIN, f"{entry.entry_id}_{岐黄键}", config_entry=entry
    )
    术数实体 = reg.async_get_or_create(
        "text", DOMAIN, f"{entry.entry_id}_{术数键}", config_entry=entry
    )

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert reg.async_get(岐黄实体.entity_id) is None
    assert reg.async_get(术数实体.entity_id) is None


async def test_非本条目前缀的实体不被回收(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)
    reg = er.async_get(hass)
    键 = next(iter(QIHUANG_PRIVATE_KEYS))
    他人实体 = reg.async_get_or_create(
        "select", DOMAIN, f"other_entry_{键}", config_entry=entry
    )

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert reg.async_get(他人实体.entity_id) is not None


async def test_开关开启且有权限时不回收私有实体(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)
    reg = er.async_get(hass)
    键 = next(iter(QIHUANG_PRIVATE_KEYS))
    实体 = reg.async_get_or_create(
        "select", DOMAIN, f"{entry.entry_id}_{键}", config_entry=entry
    )
    开关已开的条目 = SimpleNamespace(
        entry_id=entry.entry_id, data={}, options={CONF_ENABLE_QIHUANG: True}
    )

    _cleanup_private_entities(hass, 开关已开的条目, has_pro_access=True)

    assert reg.async_get(实体.entity_id) is not None


async def test_开关开启但无权限时仍回收私有实体(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)
    reg = er.async_get(hass)
    键 = next(iter(QIHUANG_PRIVATE_KEYS))
    实体 = reg.async_get_or_create(
        "select", DOMAIN, f"{entry.entry_id}_{键}", config_entry=entry
    )
    开关已开的条目 = SimpleNamespace(
        entry_id=entry.entry_id, data={}, options={CONF_ENABLE_QIHUANG: True}
    )

    _cleanup_private_entities(hass, 开关已开的条目, has_pro_access=False)

    assert reg.async_get(实体.entity_id) is None


async def test_回收时实体已消失不抛异常(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """实体在遍历与删除之间被别的路径移除时，清理逻辑必须静默跳过。"""
    entry = await _建条目(hass)
    键 = next(iter(QIHUANG_PRIVATE_KEYS))
    状态 = {"尝试删除": False}

    class 假注册表:
        def async_remove(self, entity_id: str) -> None:
            状态["尝试删除"] = True
            raise KeyError(entity_id)

    monkeypatch.setattr(
        "custom_components.tianyuan_calendar_duo.er.async_get",
        lambda _hass: 假注册表(),
    )
    monkeypatch.setattr(
        "custom_components.tianyuan_calendar_duo.er.async_entries_for_config_entry",
        lambda _reg, entry_id: [
            type(
                "条目",
                (),
                {"unique_id": f"{entry_id}_{键}", "entity_id": "select.ghost"},
            )()
        ],
    )

    _cleanup_private_entities(hass, entry, has_pro_access=False)

    assert 状态["尝试删除"] is True


async def test_unload_entry(hass: HomeAssistant) -> None:
    entry = await _建条目(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()
    assert entry.state.name == "NOT_LOADED"
    # 卸载后刷新定时器应已取消，再次 block 不会报错
    await hass.async_block_till_done()
