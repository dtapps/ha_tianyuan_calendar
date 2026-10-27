"""诊断导出测试：配置条目与设备诊断、系统令牌脱敏。"""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.tianyuan_calendar_duo.const import CONF_SYS_TOKEN, DOMAIN
from custom_components.tianyuan_calendar_duo.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


def _条目(**kwargs) -> SimpleNamespace:
    coordinator = SimpleNamespace(data=kwargs.pop("data", {"农历": None, "阳历": None}))
    默认 = {
        "version": "1.2.3",
        "options": {CONF_SYS_TOKEN: "绝密令牌"},
        "runtime_data": coordinator,
    }
    默认.update(kwargs)
    return SimpleNamespace(**默认)


async def test_诊断包含域名版本与数据键() -> None:
    条目 = _条目(options={CONF_SYS_TOKEN: "绝密令牌", "custom_latitude": 39.9})

    诊断 = await async_get_config_entry_diagnostics(None, 条目)

    assert 诊断["domain"] == DOMAIN
    assert 诊断["version"] == "1.2.3"
    assert 诊断["data_keys"] == ["农历", "阳历"]
    assert 诊断["options"]["custom_latitude"] == 39.9


async def test_系统令牌被脱敏() -> None:
    诊断 = await async_get_config_entry_diagnostics(
        None, _条目(options={CONF_SYS_TOKEN: "绝密令牌"})
    )

    assert 诊断["options"][CONF_SYS_TOKEN] != "绝密令牌"
    assert "绝密令牌" not in str(诊断)


async def test_协调器无数据时省略data_keys() -> None:
    诊断 = await async_get_config_entry_diagnostics(None, _条目(data={}))
    assert "data_keys" not in 诊断

    诊断空 = await async_get_config_entry_diagnostics(None, _条目(data=None))
    assert "data_keys" not in 诊断空


async def test_设备诊断转调配置条目诊断() -> None:
    条目 = _条目()

    设备诊断 = await async_get_device_diagnostics(
        None, 条目, SimpleNamespace(id="dev1")
    )

    assert 设备诊断 == await async_get_config_entry_diagnostics(None, 条目)
