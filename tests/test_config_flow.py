"""TianYuan Calendar 配置流测试。"""
from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.tianyuan_calendar_duo.const import (
    DOMAIN,
    CONF_CUSTOM_LONGITUDE,
    CONF_CUSTOM_LATITUDE,
    CONF_REFRESH_INTERVAL,
    CONF_ENABLE_MORE,
    CONF_ENABLE_CARD,
    CONF_ENABLE_QIHUANG,
    CONF_ENABLE_SHUSHU,
    CONF_ENABLE_SHENGRI,
    CONF_CALC_MODE,
    MODE_ST,
)


async def test_user_flow_minimal(hass: HomeAssistant) -> None:
    """初次安装：填经纬度与刷新频率即可完成."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "天元 (39.90°N, 120.00°E)"
    assert result2["data"] == {}
    opts = result2["options"]
    assert opts[CONF_ENABLE_MORE] is False
    assert opts[CONF_ENABLE_QIHUANG] is False
    assert opts[CONF_ENABLE_SHUSHU] is False


async def test_options_flow_birthdays_step_routing(hass: HomeAssistant) -> None:
    """选项流：开启生日开关应路由进入生日管理子页面（开关仅作为进入门控）。"""
    # 先建立条目
    entry_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    created = await hass.config_entries.flow.async_configure(
        entry_result["flow_id"],
        {CONF_CUSTOM_LONGITUDE: 120.0, CONF_REFRESH_INTERVAL: 1},
    )
    entry_id = created["result"].entry_id

    # 选项流：开启生日开关 -> 应进入 birthdays 子步骤
    opts_result = await hass.config_entries.options.async_init(entry_id)
    assert opts_result["type"] == data_entry_flow.FlowResultType.FORM
    assert opts_result["step_id"] == "init"

    routed = await hass.config_entries.options.async_configure(
        opts_result["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
            CONF_CALC_MODE: MODE_ST,
            CONF_ENABLE_MORE: False,
            CONF_ENABLE_QIHUANG: False,
            CONF_ENABLE_SHUSHU: False,
            CONF_ENABLE_SHENGRI: True,
        },
    )
    assert routed["type"] == data_entry_flow.FlowResultType.FORM
    assert routed["step_id"] == "birthdays"


async def test_user_flow_allows_multiple_instances(hass: HomeAssistant) -> None:
    """支持添加多个实例：第二个实例也应成功创建，且标题按坐标区分."""
    # 第一个实例
    r1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    c1 = await hass.config_entries.flow.async_configure(
        r1["flow_id"],
        {CONF_CUSTOM_LATITUDE: 39.9, CONF_CUSTOM_LONGITUDE: 116.4, CONF_REFRESH_INTERVAL: 1},
    )
    assert c1["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert c1["title"] == "天元 (39.90°N, 116.40°E)"

    # 第二个实例（不同坐标）
    r2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    c2 = await hass.config_entries.flow.async_configure(
        r2["flow_id"],
        {CONF_CUSTOM_LATITUDE: 22.5, CONF_CUSTOM_LONGITUDE: 114.1, CONF_REFRESH_INTERVAL: 5},
    )
    assert c2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert c2["title"] == "天元 (22.50°N, 114.10°E)"

    # 两个实例并存，且 unique_id 不会冲突（由 entry.entry_id 区分）
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_options_flow_persists_latitude(hass: HomeAssistant) -> None:
    """选项流：纬度配置应被正确保存."""
    # 先完成用户流，创建初始实例
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    created = await hass.config_entries.flow.async_configure(
        init["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = created["result"]
    assert entry.options[CONF_CUSTOM_LATITUDE] == 39.9
    assert entry.options[CONF_CUSTOM_LONGITUDE] == 120.0

    # 通过选项流修改纬度并验证持久化
    init_options = await hass.config_entries.options.async_init(entry.entry_id)
    updated = await hass.config_entries.options.async_configure(
        init_options["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 23.1,
            CONF_CUSTOM_LONGITUDE: 113.3,
            CONF_REFRESH_INTERVAL: 2,
            CONF_CALC_MODE: MODE_ST,
            CONF_ENABLE_MORE: False,
            CONF_ENABLE_CARD: False,
            CONF_ENABLE_QIHUANG: False,
            CONF_ENABLE_SHUSHU: False,
        },
    )
    assert updated["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CUSTOM_LATITUDE] == 23.1
    assert entry.options[CONF_CUSTOM_LONGITUDE] == 113.3

    # options 流会触发条目重载（reload），重载是异步调度、尚未完成；
    # 必须先等其结束（状态回到 LOADED），否则紧接着的卸载会因处于
    # SETUP_IN_PROGRESS 而抛 OperationNotAllowed。
    await hass.async_block_till_done()

    # 清理：卸载实例以取消 coordinator 的定时刷新定时器，避免遗留 timer 导致测试报错
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
